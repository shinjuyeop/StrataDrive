#!/usr/bin/env python3
"""Fixed privileged capture only: one OTHER pair, ten FIFO pairs; no build/analysis."""
import argparse
from collections import Counter
import fcntl
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
import traceback

import m4_kernel_capture as capture

PLAN = ["other-loaded"] + ["fifo-monitor-overrun"] * 10
MAX_SECONDS = 360
MAX_BYTES = 3 * 1024**3
# Stop early enough to leave room for all fixed worker files and one trace export.
HEADROOM_BYTES = 512 * 1024**2


def proc_identity(pid):
    path = Path("/proc")/str(pid)
    status = dict(line.split(":", 1) for line in (path/"status").read_text().splitlines() if ":" in line)
    stat = (path/"stat").read_text().rsplit(")", 1)[1].split()
    return dict(pid=pid, ppid=int(status["PPid"]), start_ticks=int(stat[19]),
                uids=list(map(int, status["Uid"].split())), gids=list(map(int, status["Gid"].split())),
                groups=list(map(int, status["Groups"].split())), cap_eff=status["CapEff"].strip(),
                rtprio=list(resource.prlimit(pid, resource.RLIMIT_RTPRIO)),
                affinity=sorted(os.sched_getaffinity(pid)), policy=os.sched_getscheduler(pid),
                priority=os.sched_getparam(pid).sched_priority)


def verify_parent(pid, uid):
    if pid <= 1 or uid <= 0:
        raise ValueError("nonroot live invoking shell required")
    first = proc_identity(pid)
    current, ancestors = os.getpid(), set()
    while current > 1 and current not in ancestors:
        ancestors.add(current)
        current = proc_identity(current)["ppid"]
    if pid not in ancestors or pid == os.getpid():
        raise ValueError("provided PID is not a live ancestor of sudo/collector")
    if first != proc_identity(pid):
        raise ValueError("invoking session changed while validating")
    if first["uids"] != [uid]*4 or int(first["cap_eff"], 16):
        raise ValueError("ancestor identity/capabilities differ from original user")
    if first["rtprio"] != [20, 20]:
        raise ValueError(f"original session must actually have 20/20: {first['rtprio']}")
    if first["policy"] != os.SCHED_OTHER or first["priority"] != 0:
        raise ValueError("original launcher must be OTHER/0")
    if not {0, 1} <= set(first["affinity"]) or not set(first["affinity"])-{0, 1}:
        raise ValueError("original affinity needs CPUs0/1 and a spare collector CPU")
    if len(set(first["gids"])) != 1:
        raise ValueError("original group identity ambiguous")
    return first


def size_bytes(folder):
    total = 0
    for path in folder.rglob("*"):
        try:
            if path.is_file() and not path.is_symlink():
                total += path.stat().st_size
        except FileNotFoundError:
            # Durable epoch publication may rename a temporary file between
            # discovery and stat. The next budget sample observes the new name.
            continue
    return total


def check_budget(folder, started):
    if time.monotonic()-started >= MAX_SECONDS:
        raise RuntimeError("campaign time budget exhausted; remaining attempts NOT RUN")
    if size_bytes(folder) >= MAX_BYTES-HEADROOM_BYTES:
        raise RuntimeError("campaign storage guard reached; remaining attempts NOT RUN")


def validate_other(folder, parent):
    uid, gid = parent["uids"][0], parent["gids"][0]
    with (folder/"analysis.log").open("w") as log:
        result = subprocess.run([sys.executable, str(capture.ROOT/"tools/m4_kernel_analysis.py"),
            str(folder)], user=uid, group=gid, extra_groups=parent["groups"],
            stdout=log, stderr=subprocess.STDOUT, timeout=60, check=False)
    verdict = json.loads((folder/"analysis.json").read_text())
    return result.returncode == 0 and verdict["comparison"]["collection_valid"]


def collect(output, parent, base=capture.TRACEFS):
    started = time.monotonic()
    planned = [dict(pair=i+1, case=case, modes=["off", "on"], status="NOT RUN")
               for i, case in enumerate(PLAN)]
    state = dict(status="RUNNING", pid=os.getpid(), source_base="1a4afe5",
                 planned_pairs=11, planned_workloads=22, profile="normal",
                 max_seconds=MAX_SECONDS, max_bytes=MAX_BYTES, storage_headroom_bytes=HEADROOM_BYTES,
                 parent=parent, collector_before=proc_identity(os.getpid()),
                 scope="intrusive diagnosis, not timing acceptance", m4="NOT CLOSED", attempts=planned)
    capture.write_json(output/"campaign.json", state)
    uid, gid = parent["uids"][0], parent["gids"][0]
    original = None
    try:
        original = capture.check_conflicts(base)
        capture.write_json(output/"global-before.json", original)
        for row in planned:
            check_budget(output, started)
            # Never borrow a different session's values after the caller exits.
            if verify_parent(parent["pid"], uid) != parent:
                raise RuntimeError("original invoking session changed")
            folder = output/f"{row['pair']:02d}-{row['case']}"
            folder.mkdir()
            os.chown(folder, uid, gid)
            row.update(status="RUNNING", directory=folder.name)
            capture.write_json(output/"campaign.json", state)
            try:
                rows = capture.run_pair(folder, row["case"], "normal",
                    (uid, gid, parent["groups"], parent["affinity"]), base,
                    rtprio=parent["rtprio"], budget=lambda: check_budget(output, started))
                row["status"] = "COLLECTED"  # VALID requires subsequent user-mode analysis.
                row["worker_exits"] = [r["worker_exit"] for r in rows]
                if row["pair"] == 1:
                    # Verify marker/buffer/identity changes before spending the FIFO cohort.
                    # Collection is stopped while this unprivileged analysis runs.
                    row["initial_other_valid"] = validate_other(folder, parent)
                    if not row["initial_other_valid"]:
                        raise RuntimeError("initial OTHER trace INVALID; FIFO prerequisite not met")
            except Exception as error:
                row.update(status="INVALID", error=f"{type(error).__name__}: {error}")
                (folder/"campaign-error.txt").write_text(traceback.format_exc())
                # Missing ON stays NOT RUN; no replacement pair or hidden retry.
                capture.check_conflicts(base)
                if capture.snapshot(base) != original:
                    raise RuntimeError("global settings changed; remaining attempts NOT RUN")
                if row["pair"] == 1:
                    raise RuntimeError("initial OTHER collection/validation failed; FIFO NOT RUN")
            finally:
                capture.give_files(folder, uid, gid)
                capture.write_json(output/"campaign.json", state)
        state["status"] = "COLLECTION FINISHED"
    except BaseException as error:
        state.update(status="STOPPED", error=f"{type(error).__name__}: {error}")
        for attempt in planned:
            if attempt["status"] == "RUNNING":
                attempt.update(status="INVALID", error=state["error"])
        (output/"campaign-error.txt").write_text(traceback.format_exc())
    finally:
        try:
            unchanged = original is not None and capture.snapshot(base) == original
        except OSError as error:
            unchanged = False
            state.update(status="STOPPED", cleanup_error=str(error))
        state.update(elapsed_seconds=time.monotonic()-started, bytes=size_bytes(output),
                     global_unchanged=unchanged)
        capture.write_json(output/"campaign.json", state)
    if state["status"] != "COLLECTION FINISHED" or any(
            row["status"] != "COLLECTED" for row in planned) or not state["global_unchanged"]:
        return 2
    return 1 if any(code != 0 for row in planned for code in row["worker_exits"]) else 0


def collection_summary(output, result):
    state = json.loads((output/"campaign.json").read_text())
    invalid = []
    for row in state["attempts"]:
        if row["status"] != "INVALID":
            continue
        detail = dict(pair=row["pair"], error=row.get("error"))
        if row.get("directory"):
            path = output/row["directory"]/"analysis.json"
            if path.exists():
                try:
                    verdict = json.loads(path.read_text())
                    detail["analysis_errors"] = {
                        mode: verdict.get(mode, {}).get("errors", []) for mode in ("off", "on")}
                except (OSError, ValueError) as error:
                    detail["analysis_read_error"] = str(error)
        invalid.append(detail)
    return dict(output=str(output), collection_exit=result, status=state["status"],
                reason=state.get("error"), pair_status_counts=dict(Counter(
                    row["status"] for row in state["attempts"])), invalid_pairs=invalid,
                analysis=("stopped; inspect campaign.json and invalid_pairs; no acceptance verdict"
                          if state["status"] != "COLLECTION FINISHED" else
                          "run tools/m4_kernel_campaign_analysis.py CAPTURE NEW_OUTPUT; no acceptance verdict"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--user-parent", required=True, type=int)
    args = parser.parse_args()
    if os.geteuid() != 0 or int(os.environ.get("SUDO_UID", "0")) == 0:
        parser.error("use sudo from the original nonroot shell")
    uid = int(os.environ["SUDO_UID"])
    parent = verify_parent(args.user_parent, uid)
    output = args.output.absolute()
    if not output.parent.is_dir():
        parser.error("output parent must already exist")
    output = output.parent.resolve()/output.name
    if output.exists() or not output.is_relative_to(capture.ROOT/"build") or output.parent.stat().st_uid != uid:
        parser.error("new output below original user's build/ required")
    if os.sched_getscheduler(0) != os.SCHED_OTHER or os.sched_getparam(0).sched_priority:
        parser.error("collector must remain OTHER/0")
    output.mkdir(mode=0o700)
    os.chown(output, uid, parent["gids"][0])
    lock = os.open("/run/lock/stratadrive-m4-trace.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    # User-mode build/SDK jobs can hold the same workspace lock. No shared root service.
    work_lock = os.open(capture.ROOT/"build/.m4-exclusive.lock",
                       os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    os.fchown(work_lock, uid, parent["gids"][0])
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGALRM):
        signal.signal(sig, capture.interrupted)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(work_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        signal.alarm(MAX_SECONDS)
        os.sched_setaffinity(0, {min(set(parent["affinity"])-{0, 1})})
        result = collect(output, parent)
        print(json.dumps(collection_summary(output, result)))
        return result
    except (Exception, KeyboardInterrupt) as error:
        (output/"error.txt").write_text(traceback.format_exc())
        print(f"Collection stopped: {error}; evidence: {output}", file=sys.stderr)
        return 2
    finally:
        signal.alarm(0)
        capture.give_files(output, uid, parent["gids"][0])
        os.close(lock)
        os.close(work_lock)


if __name__ == "__main__":
    raise SystemExit(main())

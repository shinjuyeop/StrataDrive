#!/usr/bin/env python3
"""Bounded, isolated tracefs OFF/ON diagnostic. Run capture/probe through sudo."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import resource
import runpy
import select
import signal
import subprocess
import sys
import time
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
TRACEFS = Path("/sys/kernel/tracing")
MAX_SECONDS = 12
MAX_TRACE_BYTES = 128 * 1024 * 1024
MAX_BUFFER_KB = 64 * 1024
BUFFER_KB = {0: 16384, 1: 32768}
REQUIRED = ("timer:hrtimer_init", "timer:hrtimer_start", "timer:hrtimer_cancel",
            "timer:hrtimer_expire_entry", "timer:hrtimer_expire_exit",
            "sched:sched_wakeup", "sched:sched_switch",
            "irq:irq_handler_entry", "irq:irq_handler_exit")
OPTIONAL = ("sched:sched_wakeup_new", "sched:sched_migrate_task",
            "irq:softirq_raise", "irq:softirq_entry", "irq:softirq_exit")
CASES = {"other-loaded": ("other", True, "normal"),
         "fifo-monitor-overrun": ("fifo", False, "monitor-overrun")}


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n")


def control(path, value):
    path.write_text(str(value) + "\n")


def snapshot(base):
    # Read only. Never reset a global/foreign instance, even if it appears idle.
    return {name: (base/name).read_text().strip()
            for name in ("tracing_on", "current_tracer", "events/enable", "trace_clock", "tracing_cpumask")}


def check_conflicts(base=TRACEFS, own=None):
    state = snapshot(base)
    if state["current_tracer"] != "nop" or state["events/enable"] != "0":
        raise RuntimeError("global tracer/events already configured; leave the existing trace untouched")
    profiler = base/"function_profile_enabled"
    if profiler.exists() and profiler.read_text().strip() != "0":
        raise RuntimeError("global function profiler already enabled")
    foreign = [p.name for p in (base/"instances").iterdir() if p.name != own]
    if foreign:
        raise RuntimeError(f"existing trace instances: {foreign}; no capture started")
    for proc in Path("/proc").glob("[0-9]*"):
        try:
            name = (proc/"comm").read_text().strip()
        except (FileNotFoundError, ProcessLookupError):
            continue
        if name in ("perf", "trace-cmd", "bpftrace"):
            raise RuntimeError(f"another tracing tool is running: {name} PID{proc.name}")
    return state


def inventory(base=TRACEFS):
    available = set((base/"available_events").read_text().split())
    selected = [e for e in REQUIRED + OPTIONAL if e in available]
    selected += sorted(e for e in available if e.startswith("irq_vectors:")
                       and e.endswith(("_entry", "_exit")))
    relevant = {e for e in available if e.startswith(
        ("timer:", "sched:", "irq:", "irq_vectors:", "ipi:",
         "syscalls:sys_enter_clock_nanosleep", "syscalls:sys_exit_clock_nanosleep",
         "syscalls:sys_enter_nanosleep", "syscalls:sys_exit_nanosleep"))}
    return dict(policy="compact-v2", selected=selected, missing_required=sorted(set(REQUIRED)-available),
                missing_optional=sorted(set(OPTIONAL)-available),
                available=sorted(relevant), available_not_selected=sorted(relevant-set(selected)))


def buffer_sizes(cpus, marker_cpu):
    if marker_cpu in BUFFER_KB or marker_cpu not in cpus or not set(BUFFER_KB) <= set(cpus):
        raise ValueError("marker collector requires a spare traced CPU outside CPUs0/1")
    sizes = {cpu: 256 for cpu in cpus}
    sizes.update(BUFFER_KB)
    sizes[marker_cpu] = 2048  # End marker also needs space in its CPU's ring.
    if sum(sizes.values()) > MAX_BUFFER_KB:
        raise ValueError("requested per-CPU buffers exceed unchanged 64MiB total cap")
    return sizes


class TraceInstance:
    """Only a newly owned instance is mutated. Global settings are never written."""
    def __init__(self, base, folder, events):
        self.base, self.folder, self.events = base, folder, events
        self.path = base/"instances"/("stratadrive-m4-"+uuid.uuid4().hex)
        self.created = False
        self.free_fd = None
        self.markers = []
        self.watch_pid = self.watch_fd = None

    def start(self):
        self.path.mkdir()
        self.created = True  # Also clean up partially configured instances.
        control(self.path/"tracing_on", 0)
        control(self.path/"current_tracer", "nop")
        clocks = (self.path/"trace_clock").read_text().replace("[", "").replace("]", "").split()
        if "mono" not in clocks:
            raise RuntimeError("trace_clock mono unavailable; no timestamp conversion guessed")
        control(self.path/"trace_clock", "mono")
        control(self.path/"events/enable", 0)
        cpus = sorted(int(p.name[3:]) for p in (self.path/"per_cpu").glob("cpu[0-9]*"))
        affinity = os.sched_getaffinity(0)
        if len(affinity) != 1:
            raise RuntimeError("collector marker must be pinned to one spare CPU")
        marker_cpu = next(iter(affinity))
        sizes = buffer_sizes(cpus, marker_cpu)
        control(self.path/"buffer_size_kb", 256)
        for cpu, kb in sizes.items():
            if kb != 256:
                control(self.path/f"per_cpu/cpu{cpu}/buffer_size_kb", kb)
        total = int((self.path/"buffer_total_size_kb").read_text())
        if total > MAX_BUFFER_KB:
            raise RuntimeError(f"kernel buffer exceeds {MAX_BUFFER_KB} KiB: {total}")
        # Capture cross-CPU wake sources too; application owners remain on CPUs0/1.
        bits = sum(1 << cpu for cpu in cpus)
        words = []
        while bits:
            words.append(f"{bits & 0xffffffff:08x}")
            bits >>= 32
        control(self.path/"tracing_cpumask", ",".join(reversed(words)))
        for name, value in (("overwrite", 0), ("context-info", 1), ("irq-info", 1),
                            ("latency-format", 0), ("disable_on_free", 1), ("markers", 1)):
            control(self.path/"options"/name, value)
        for name in ("raw", "hex", "bin", "print-tgid"):
            if (self.path/"options"/name).exists():
                control(self.path/"options"/name, 0)
        # Kernel-assisted fail-stop on fd close, including collector SIGKILL.
        self.free_fd = os.open(self.path/"free_buffer", os.O_WRONLY | os.O_CLOEXEC)
        formats = {}
        for event in self.events:
            d = self.path/"events"/event.replace(":", "/")
            formats[event] = (d/"format").read_text()
            control(d/"enable", 1)
        write_json(self.folder/"event-formats.json", formats)
        write_json(self.folder/"trace-settings.json",
                   dict(state=snapshot(self.path), cpus=cpus, total_buffer_kb=total,
                        policy="compact-v2", owner_buffer_kb=BUFFER_KB,
                        marker_cpu=marker_cpu, requested_buffer_kb=sizes,
                        max_text_bytes=MAX_TRACE_BYTES, worker_timeout_seconds=MAX_SECONDS,
                        trace_watchdog_seconds=MAX_SECONDS+3,
                        clock="CLOCK_MONOTONIC", overwrite=False, instance=str(self.path)))
        control(self.path/"trace", "")
        self.start_watchdog()
        control(self.path/"tracing_on", 1)
        self.mark("begin")

    def start_watchdog(self):
        reader, writer = os.pipe2(os.O_CLOEXEC)
        self.watch_pid = os.fork()
        if self.watch_pid == 0:
            os.close(writer)
            os.close(self.free_fd)
            os.setsid()  # Survives terminal Ctrl-C and collector process death.
            for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
                signal.signal(sig, signal.SIG_IGN)
            try:
                watchdog(reader, self.path, self.folder, MAX_SECONDS+3)
            finally:
                os._exit(0)
        os.close(reader)
        self.watch_fd = writer

    def watch_worker(self, pid):
        if self.watch_fd is not None:
            os.write(self.watch_fd, f"PGID {pid}\n".encode())

    def mark(self, name):
        before = time.monotonic_ns()
        # Unbuffered write keeps a kernel marker failure at the actual write,
        # rather than having TextIO close/flush obscure its original traceback.
        payload = f"SD_M4_CLOCK_{name}\n".encode()
        with (self.path/"trace_marker").open("wb", buffering=0) as marker:
            if marker.write(payload) != len(payload):
                raise OSError("short trace_marker write")
        self.markers.append(dict(name=name, before_ns=before, after_ns=time.monotonic_ns()))

    def stop_and_save(self):
        marker_error = None
        try:
            self.mark("end")
        except OSError as error:
            marker_error = error
        before_stop = (self.path/"tracing_on").read_text().strip()
        control(self.path/"tracing_on", 0)
        stats = {p.parent.name: p.read_text() for p in sorted((self.path/"per_cpu").glob("cpu*/stats"))}
        truncated = bounded_copy(self.path/"trace", self.folder/"kernel.trace", MAX_TRACE_BYTES)
        write_json(self.folder/"trace-integrity.json",
                   dict(clock="mono", markers=self.markers, stats=stats, truncated=truncated,
                        tracing_on_before_stop=before_stop,
                        marker_errors=[] if marker_error is None else [
                            dict(name="end", errno=marker_error.errno, error=str(marker_error))],
                        max_text_bytes=MAX_TRACE_BYTES))
        if marker_error is not None:
            # Keep raw/stats even when a full/disabled ring cannot accept a marker.
            # Missing alignment remains a capture failure; never synthesize it.
            raise marker_error

    def close(self):
        errors = []
        if self.created:
            for file in ("tracing_on", "events/enable"):
                try:
                    control(self.path/file, 0)
                except OSError as error:
                    errors.append(str(error))
        if self.free_fd is not None:
            os.close(self.free_fd)
            self.free_fd = None
        if self.created:
            try:
                self.path.rmdir()  # tracefs removes its virtual files; never shutil.rmtree.
                self.created = False
            except OSError as error:
                errors.append(str(error))
        if self.watch_fd is not None:
            try:
                os.write(self.watch_fd, b"DONE\n")
            except BrokenPipeError:
                errors.append("watchdog already intervened")
            os.close(self.watch_fd)
            self.watch_fd = None
            os.waitpid(self.watch_pid, 0)
        return errors


def watchdog(reader, instance, folder, limit):
    """Independent fail-stop: parent EOF/death or 15s total, including trace export."""
    deadline, group, buffer = time.monotonic()+limit, None, b""
    reason = "watchdog time limit"
    while time.monotonic() < deadline:
        ready, _, _ = select.select([reader], [], [], max(0, deadline-time.monotonic()))
        if not ready:
            break
        chunk = os.read(reader, 4096)
        if not chunk:
            reason = "collector pipe closed without completed cleanup"
            break
        buffer += chunk
        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            if line == b"DONE":
                os.close(reader)
                return
            if line.startswith(b"PGID "):
                group = int(line.split()[1])
    errors = []
    for name in ("tracing_on", "events/enable"):
        try:
            control(instance/name, 0)
        except OSError as error:
            errors.append(str(error))
    if group:
        try:
            os.killpg(group, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        instance.rmdir()
    except OSError as error:
        errors.append(str(error))
    write_json(folder/"watchdog.json", dict(reason=reason, errors=errors, pgid=group))
    os.close(reader)


def bounded_copy(source, dest, limit):
    with source.open("rb") as reader, dest.open("xb") as writer:
        remaining = limit
        while remaining:
            chunk = reader.read(min(65536, remaining))
            if not chunk:
                return False
            writer.write(chunk)
            remaining -= len(chunk)
        return bool(reader.read(1))


def kill_group(process):
    if process is None:
        return
    # Children include the load process. Also clean it if the worker already exited.
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=2)


def worker(folder, case, profile, affinity):
    if os.getuid() == 0 or os.geteuid() == 0:
        raise RuntimeError("workload must never run as root")
    os.sched_setaffinity(0, set(affinity))
    if os.sched_getscheduler(0) != os.SCHED_OTHER or os.sched_getparam(0).sched_priority:
        raise RuntimeError("workload launcher must remain OTHER/0")
    # Fixed runtime output files only; avoid unbounded output on a broken process.
    resource.setrlimit(resource.RLIMIT_FSIZE, (32*1024*1024, 32*1024*1024))
    status = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines() if ":" in line)
    identity = dict(uid=os.getuid(), euid=os.geteuid(), gid=os.getgid(), groups=os.getgroups(),
                    cap_eff=status["CapEff"].strip(), pid=os.getpid(), affinity=sorted(os.sched_getaffinity(0)),
                    policy=os.sched_getscheduler(0), priority=os.sched_getparam(0).sched_priority,
                    rtprio=list(resource.getrlimit(resource.RLIMIT_RTPRIO)),
                    file_limit_bytes=resource.getrlimit(resource.RLIMIT_FSIZE)[0])
    write_json(folder/"worker-identity.json", identity)
    if int(identity["cap_eff"], 16):
        raise RuntimeError("workload has effective capabilities")
    runner = runpy.run_path(str(ROOT/"tests/integration/runtime/check_m4_faults.py"))
    binary = ROOT/runner["PROFILES"][profile]/"actuator_demo"
    source = dict(source_commit=subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        source_digest=runner["BASE"]["fingerprint"](),
        binary=str(binary), binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest())
    write_json(folder/"source.json", source)
    policy, loaded, scenario = CASES[case]
    row = runner["timing_run"](folder/"run", profile, policy, loaded, scenario, 1)
    write_json(folder/"trial.json", row)
    source["source_digest_after"] = runner["BASE"]["fingerprint"]()
    source["binary_sha256_after"] = hashlib.sha256(binary.read_bytes()).hexdigest()
    source["stable"] = (source["source_digest"] == source["source_digest_after"]
                        and source["binary_sha256"] == source["binary_sha256_after"])
    write_json(folder/"source.json", source)
    if not source["stable"]:
        return 2
    return 0 if row["verdict"] == "PASS" else 1


def run_pair(folder, case, profile, identity, base=TRACEFS):
    """No retry: OFF first, ON second, even when OFF reports expected timing FAIL."""
    uid, gid, groups, affinity = identity
    before = check_conflicts(base)
    info = inventory(base)
    write_json(folder/"inventory.json", info)
    write_json(folder/"global-before.json", before)
    if info["missing_required"]:
        raise RuntimeError(f"required events unavailable: {info['missing_required']}")
    rows = []
    for mode in ("off", "on"):
        check_conflicts(base)
        trial = folder/mode
        trial.mkdir()
        os.chown(trial, uid, gid)
        trace = TraceInstance(base, trial, info["selected"]) if mode == "on" else None
        process = None
        row = dict(mode=mode, worker_exit=None, collection="INCOMPLETE", errors=[])
        try:
            if trace:
                trace.start()
            env = {k: v for k, v in os.environ.items()
                   if not k.startswith(("STRATADRIVE_", "SUDO_", "PYTHON", "LD_", "ASAN_", "TSAN_", "UBSAN_"))}
            account = pwd.getpwuid(uid)
            env.update(HOME=account.pw_dir, USER=account.pw_name, LOGNAME=account.pw_name,
                       PYTHONNOUSERSITE="1")
            command = [sys.executable, str(Path(__file__).resolve()), "_worker", str(trial),
                       "--case", case, "--profile", profile, "--affinity", ",".join(map(str, affinity))]
            write_json(trial/"launch.json", dict(argv=command, uid=uid, gid=gid, groups=groups,
                                                affinity=affinity, env_removed="sanitizer/loader/Python/M4 overrides"))
            with (trial/"worker.log").open("xb") as log:
                process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                           user=uid, group=gid, extra_groups=groups, start_new_session=True)
                if trace:
                    trace.watch_worker(process.pid)
                try:
                    row["worker_exit"] = process.wait(timeout=MAX_SECONDS)
                    row["collection"] = "COMPLETE"
                except subprocess.TimeoutExpired:
                    row["collection"] = "TIMEOUT"
                    row["errors"].append("12s hard limit; no retry")
            if trace:
                trace.stop_and_save()
        except BaseException as error:
            row["collection"] = "INCOMPLETE"
            row["errors"].append(f"{type(error).__name__}: {error}")
            (trial/"collector-error.txt").write_text(traceback.format_exc())
            if trace and trace.created and not (trial/"kernel.trace").exists():
                try:
                    trace.stop_and_save()
                except (OSError, RuntimeError) as dump_error:
                    row["errors"].append(f"partial trace export: {dump_error}")
            raise
        finally:
            if trace and trace.created:
                # Stop recording before termination/export/cleanup work.
                try:
                    control(trace.path/"tracing_on", 0)
                except OSError as error:
                    row["errors"].append(str(error))
            kill_group(process)
            if trace:
                row["errors"] += trace.close()
                row["instance_removed"] = not trace.created
            row["global_unchanged"] = snapshot(base) == before
            if not row["global_unchanged"]:
                row["errors"].append("global state changed externally; not overwritten/restored by us")
            try:
                check_conflicts(base)
            except RuntimeError as conflict:
                row["errors"].append(f"concurrent observer: {conflict}")
            rows.append(row)
            write_json(folder/"collection.json", rows)
        if row["collection"] != "COMPLETE" or row["errors"]:
            raise RuntimeError("capture incomplete; inspect collection.json")
    return rows


def interrupted(signum, _frame):
    raise KeyboardInterrupt(f"signal {signum}")


def give_files(output, uid, gid):
    for p in [output, *output.rglob("*")]:
        if not p.is_symlink():
            os.chown(p, uid, gid)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("probe", "capture", "_worker"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--case", choices=CASES, default="other-loaded")
    parser.add_argument("--profile", choices=("normal", "sanitized"), default="normal")
    parser.add_argument("--affinity", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.action == "_worker":
        return worker(args.output, args.case, args.profile, list(map(int, args.affinity.split(","))))
    if os.geteuid() != 0 or not os.environ.get("SUDO_UID"):
        parser.error("use sudo from the original non-root user; _worker never uses sudo")
    uid = int(os.environ["SUDO_UID"])
    account = pwd.getpwuid(uid)
    if uid == 0:
        parser.error("SUDO_UID must identify the original non-root workload user")
    gid = account.pw_gid
    affinity = sorted(os.sched_getaffinity(0))
    if not {0, 1}.issubset(affinity) or not set(affinity)-{0, 1}:
        parser.error("need original CPUs0/1 and a spare CPU for the collector")
    if os.sched_getscheduler(0) != os.SCHED_OTHER or os.sched_getparam(0).sched_priority:
        parser.error("collector must be OTHER/0")
    output = args.output.absolute()
    # New directory only, inside this user's workspace; never chown an existing tree.
    if not output.is_relative_to(ROOT/"build") or output.exists():
        parser.error("output must be a NEW directory below this repository's build/")
    if not output.parent.is_dir():
        parser.error("create the output parent as the original user first")
    output = output.parent.resolve()/output.name
    if not output.is_relative_to(ROOT/"build") or output.parent.stat().st_uid != uid:
        parser.error("output parent must be owned by the invoking user inside build/")
    output.mkdir(mode=0o700)
    os.chown(output, uid, gid)
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, interrupted)
    # Advisory global lock prevents two instances of this collector racing.
    lock = os.open("/run/lock/stratadrive-m4-trace.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        os.sched_setaffinity(0, {min(set(affinity)-{0, 1})})
        write_json(output/"collector.json", dict(uid=uid, gid=gid, kernel=os.uname().release,
            original_affinity=affinity, collector_affinity=sorted(os.sched_getaffinity(0)),
            rtprio=list(resource.getrlimit(resource.RLIMIT_RTPRIO)), case=args.case, profile=args.profile,
            max_seconds_per_trial=MAX_SECONDS, max_trace_bytes=MAX_TRACE_BYTES,
            trace_watchdog_seconds=MAX_SECONDS+3, planned_modes=["off", "on"] if args.action == "capture" else [],
            monotonic_ns=time.monotonic_ns(), system_status="NOT RUN", m4_status="NOT CLOSED"))
        if args.action == "probe":
            write_json(output/"inventory.json", inventory())
            write_json(output/"global-before.json", check_conflicts())
        else:
            rows = run_pair(output, args.case, args.profile,
                            (uid, gid, os.getgrouplist(account.pw_name, gid), affinity))
            give_files(output, uid, gid)
            # Analyze as the original user too. A timing FAIL is retained, not a collector error.
            result = subprocess.run([sys.executable, str(ROOT/"tools/m4_kernel_analysis.py"), str(output)],
                user=uid, group=gid, extra_groups=os.getgrouplist(account.pw_name, gid), timeout=60, check=False)
            if result.returncode:
                return 2
            return 1 if any(r["worker_exit"] != 0 for r in rows) else 0
        return 0
    except (Exception, KeyboardInterrupt) as error:
        (output/"collector-error.txt").write_text(traceback.format_exc())
        write_json(output/"error.json", dict(error=f"{type(error).__name__}: {error}"))
        print(f"Capture stopped: {error}; evidence: {output}", file=sys.stderr)
        return 2
    finally:
        os.close(lock)
        # Do not follow links or recurse outside the directory we just created.
        give_files(output, uid, gid)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Correlate trace_clock=mono events with actual M4 TIDs; never infer missing edges."""
import argparse
from bisect import bisect_right
import csv
import json
from pathlib import Path
import re

LINE = re.compile(r"^.*-(\d+)\s+(?:\(\s*\S+\s*\)\s+)?\[(\d+)\]\s+\S+\s+"
                  r"(\d+)\.(\d+):\s+(.*)$")
EVENT = re.compile(r"([\w:]+):\s*(.*)$")
SYSCALL_ENTRY = re.compile(r"sys_(clock_nanosleep|nanosleep)\((.*)\)$")
SYSCALL_EXIT = re.compile(r"sys_(clock_nanosleep|nanosleep) -> (0x[0-9a-fA-F]+|-?\d+)$")
FIELD = re.compile(r"(\w+)=([^\s]+)")
RESOLUTION_NS = 1000  # ftrace text commonly prints microseconds. Keep rounding uncertainty.


def read_csv(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def save_csv(path, rows):
    if not rows:
        path.write_text("")
        return
    with path.open("w") as stream:
        writer = csv.DictWriter(stream, list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def parse(line):
    match = LINE.match(line)
    if not match:
        return None
    tid, cpu, seconds, fraction, printed = match.groups()
    # The syscall trace pretty-printer does not use the usual "event: payload"
    # form, even though its format file describes colon-separated arguments.
    regular, entry, returned = EVENT.fullmatch(printed), SYSCALL_ENTRY.fullmatch(printed), SYSCALL_EXIT.fullmatch(printed)
    if regular:
        kind, body = regular.groups()
        fields = dict(FIELD.findall(body))
    elif entry:
        name, body = entry.groups()
        kind = "sys_enter_"+name
        fields = dict(re.findall(r"(\w+):\s*([^,\s]+)", body))
    elif returned:
        name, body = returned.groups()
        kind, fields = "sys_exit_"+name, {"ret": body}
    else:
        return None  # Unknown output remains an error, never silently skipped.
    stamp = int(seconds)*1000000000 + int((fraction+"000000000")[:9])
    return dict(tid=int(tid), cpu=int(cpu), ns=stamp, kind=kind.split(":")[-1],
                body=body, fields=fields)


def timer_clock(clock, mode):
    # Linux __hrtimer_init(): relative CLOCK_REALTIME is backed by MONOTONIC.
    # hrtimer_init's trace records the original clock argument, not that base.
    # This is a kernel rule, not a guessed wall-clock -> monotonic offset.
    if clock == "CLOCK_REALTIME" and "REL" in mode.split("|"):
        return "CLOCK_MONOTONIC"
    return clock


def union_length(intervals):
    total, end = 0, -1
    for left, right in sorted(intervals):
        if right > max(left, end):
            total += right-max(left, end)
        end = max(end, right)
    return total


class Intervals:
    def __init__(self, rows):
        self.rows = sorted(rows)
        self.starts = [r[0] for r in self.rows]

    def overlap(self, left, right):
        # These per-TID/per-IRQ-family rows do not overlap within their own family.
        index = max(0, bisect_right(self.starts, left)-1)
        result = []
        for index in range(index, len(self.rows)):
            row = self.rows[index]
            if row[0] >= right:
                break
            if row[1] > left:
                result.append((max(left, row[0]), min(right, row[1]), *row[2:]))
        return result


def collect(trace, tids):
    timers, clocks, callbacks = {}, {}, {}
    cycles = {tid: [] for tid in tids}
    running, off, run_rows, off_rows = {}, {}, {t: [] for t in tids}, {t: [] for t in tids}
    irq_stack, irq_rows = {}, {}
    switch_ins, marker_times = {t: [] for t in tids}, {}
    parsed = unknown = 0
    unknown_examples, event_counts = [], {}
    latest = 0
    with trace.open(errors="replace") as stream:
        for line in stream:
            if line.startswith("#") or not line.strip():
                continue
            event = parse(line)
            if event is None:
                unknown += 1
                if len(unknown_examples) < 8:
                    unknown_examples.append(line.strip()[:512])
                continue
            parsed += 1
            ns, tid, cpu, kind, f = (event[k] for k in ("ns", "tid", "cpu", "kind", "fields"))
            event_counts[kind] = event_counts.get(kind, 0)+1
            latest = max(latest, ns)
            if "SD_M4_CLOCK_" in event["body"]:
                marker_times[event["body"].strip()] = ns
            if kind == "hrtimer_init":
                clocks[f["hrtimer"]] = (f["clockid"], f.get("mode", "UNKNOWN"))
                timers.pop(f["hrtimer"], None)
            elif kind == "hrtimer_start":
                addr = f["hrtimer"]
                clock, mode = clocks.get(addr, ("UNKNOWN", "UNKNOWN"))
                timers[addr] = dict(tid=tid, arm_ns=ns, timer=addr,
                    soft_ns=int(f["softexpires"]), hard_ns=int(f["expires"]),
                    clock=timer_clock(clock, mode), raw_clock=clock, init_mode=mode,
                    function=f.get("function", ""))
            elif kind == "hrtimer_cancel":
                timers.pop(f["hrtimer"], None)
            elif kind == "hrtimer_expire_entry":
                start = timers.pop(f["hrtimer"], None)
                # An expiry must be associated with the latest arm of this address.
                if start and start["tid"] in tids and "hrtimer_wakeup" in start["function"]:
                    callbacks[(cpu, f["hrtimer"])] = dict(
                        **start, callback_ns=ns, callback_now_ns=int(f["now"]), wake_ns=None)
            elif kind == "sched_wakeup":
                target = int(f["pid"])
                if target in off and not off[target][1].startswith("R"):
                    left, state = off[target]
                    off_rows[target].append((left, ns, state))
                    off[target] = (ns, "R(wakeup)")
                for (callback_cpu, _), callback in callbacks.items():
                    if callback_cpu == cpu and callback["tid"] == target:
                        callback["wake_ns"] = ns
            elif kind == "hrtimer_expire_exit":
                callback = callbacks.pop((cpu, f["hrtimer"]), None)
                if callback is not None:
                    callback["callback_exit_ns"] = ns
                    cycles[callback["tid"]].append(callback)
            elif kind == "sched_switch":
                previous, following = int(f["prev_pid"]), int(f["next_pid"])
                if previous in tids:
                    left = running.pop(previous, None)
                    if left:
                        run_rows[previous].append((left[0], ns, left[1]))
                    off[previous] = (ns, f["prev_state"])
                if following in tids:
                    running[following] = (ns, cpu)
                    switch_ins[following].append(ns)
                    left = off.pop(following, None)
                    if left:
                        off_rows[following].append((left[0], ns, left[1]))
            if (kind.startswith(("irq_handler_", "softirq_")) or
                    kind.endswith(("_entry", "_exit")) and kind not in
                    ("hrtimer_expire_entry", "hrtimer_expire_exit", "timer_expire_entry", "timer_expire_exit")
                    and "sys_" not in kind):
                if kind.endswith("_entry"):
                    family = kind[:-6]
                    irq_stack.setdefault((cpu, family), []).append(ns)
                elif kind.endswith("_exit"):
                    family = kind[:-5]
                    stack = irq_stack.get((cpu, family), [])
                    if stack:
                        left = stack.pop()
                        irq_rows.setdefault((cpu, family), []).append((left, ns))
    for tid, (left, cpu) in running.items():
        run_rows[tid].append((left, latest, cpu))
    for tid, (left, state) in off.items():
        off_rows[tid].append((left, latest, state))
    for tid in tids:
        cycles[tid].sort(key=lambda c: c["callback_ns"])
        for cycle in cycles[tid]:
            if cycle["wake_ns"] is not None:
                index = bisect_right(switch_ins[tid], cycle["wake_ns"]-1)
                cycle["switch_ns"] = switch_ins[tid][index] if index < len(switch_ins[tid]) else None
            else:
                cycle["switch_ns"] = None
    return dict(cycles=cycles, runs={k: Intervals(v) for k, v in run_rows.items()},
                off={k: Intervals(v) for k, v in off_rows.items()},
                irqs={k: Intervals(v) for k, v in irq_rows.items()},
                markers=marker_times, parsed=parsed, unknown_lines=unknown,
                unknown_examples=unknown_examples, event_counts=event_counts,
                unclosed_callbacks=len(callbacks), unclosed_irq=sum(map(len, irq_stack.values())),
                open_irq=[(cpu, left) for (cpu, _), stack in irq_stack.items() for left in stack])


def integrity_errors(integrity, data):
    errors = []
    if integrity.get("clock") != "mono":
        errors.append("trace clock is not mono")
    if integrity.get("truncated"):
        errors.append("trace output truncated")
    if integrity.get("marker_errors"):
        errors.append("trace marker write failed")
    if not integrity.get("stats"):
        errors.append("per-CPU trace statistics missing")
    for cpu, text in integrity.get("stats", {}).items():
        for name in ("overrun", "commit overrun", "dropped events"):
            match = re.search(r"^"+name+r":\s*(\d+)", text, re.M)
            if match is None or int(match.group(1)):
                errors.append(f"{cpu}: missing/nonzero {name}")
    markers = integrity.get("markers", [])
    if {m["name"] for m in markers} != {"begin", "end"}:
        errors.append("clock sandwich markers incomplete")
    for marker in markers:
        ns = data["markers"].get("SD_M4_CLOCK_"+marker["name"])
        if ns is None or not marker["before_ns"]-RESOLUTION_NS <= ns <= marker["after_ns"]+RESOLUTION_NS:
            errors.append(f"monotonic alignment failed: {marker['name']}")
    if not data["parsed"] or data["unknown_lines"]:
        errors.append(f"trace absent/unparsed lines: {data['unknown_lines']}")
    if data["unclosed_callbacks"]:
        errors.append("unclosed owner timer callbacks")
    return errors


def job_metrics(job, tid, data, valid):
    begin, end, requested = (int(job[k]) for k in ("start_ns", "end_ns", "requested_wake_ns"))
    row = {**job, "tid": tid, "coverage": "valid" if valid else "INVALID",
           "timer_chain": "NOT OBSERVED", "arm_ns": "", "soft_ns": "", "hard_ns": "",
           "timer_clock": "", "timer_effective_clock": "", "timer_init_mode": "",
           "callback_ns": "", "wake_ns": "", "switch_ns": "", "soft_minus_requested_ns": "",
           "callback_minus_soft_ns": "", "callback_minus_hard_ns": "", "wake_minus_callback_ns": "",
           "switch_minus_wake_ns": "", "body_minus_switch_ns": "",
           "body_wall_ns": end-begin if begin else "", "scheduled_ns": "", "off_cpu_ns": "",
           "runnable_off_cpu_ns": "", "blocked_ns": "", "irq_overlap_ns": ""}
    if not begin or not end:
        return row
    run = data["runs"][tid].overlap(begin, end)
    off = data["off"][tid].overlap(begin, end)
    row["scheduled_ns"] = sum(r-l for l, r, _ in run)
    row["off_cpu_ns"] = sum(r-l for l, r, _ in off)
    row["runnable_off_cpu_ns"] = sum(r-l for l, r, state in off if state.startswith("R"))
    row["blocked_ns"] = sum(r-l for l, r, state in off if not state.startswith("R"))
    irq = []
    for l, r, cpu in run:
        for (irq_cpu, _), intervals in data["irqs"].items():
            if irq_cpu == cpu:
                irq += [(a, b) for a, b in intervals.overlap(l, r)]
    row["irq_overlap_ns"] = union_length(irq)  # union avoids double-counting nested IRQ/softirq/vector events.
    if any(cpu == open_cpu and left < right for _, right, cpu in run for open_cpu, left in data["open_irq"]):
        row["coverage"] = "INCOMPLETE IRQ"
    if abs(row["scheduled_ns"]+row["off_cpu_ns"]-(end-begin)) > 2*RESOLUTION_NS:
        row["coverage"] = "INCOMPLETE SCHEDULER"
    cycles = data["cycles"][tid]
    index = bisect_right(data["cycle_times"][tid], begin+RESOLUTION_NS)-1
    if index < 0:
        return row
    cycle = cycles[index]
    # Never substitute another owner/timer, a prior expired arm, or a wake without its callback.
    if (cycle["clock"] != "CLOCK_MONOTONIC" or cycle["wake_ns"] is None or cycle["switch_ns"] is None
            or not requested-RESOLUTION_NS <= cycle["soft_ns"] <= begin+RESOLUTION_NS
            or cycle["switch_ns"] > begin+RESOLUTION_NS):
        return row
    row["timer_chain"] = "OBSERVED" if valid else "UNTRUSTED"
    row.update(timer_clock=cycle["raw_clock"], timer_effective_clock=cycle["clock"],
               timer_init_mode=cycle["init_mode"])
    row.update({k: cycle[k] for k in ("arm_ns", "soft_ns", "hard_ns", "callback_ns", "wake_ns", "switch_ns")})
    row.update(soft_minus_requested_ns=cycle["soft_ns"]-requested,
               callback_minus_soft_ns=cycle["callback_ns"]-cycle["soft_ns"],
               callback_minus_hard_ns=cycle["callback_ns"]-cycle["hard_ns"],
               wake_minus_callback_ns=cycle["wake_ns"]-cycle["callback_ns"],
               switch_minus_wake_ns=cycle["switch_ns"]-cycle["wake_ns"],
               body_minus_switch_ns=begin-cycle["switch_ns"])
    return row


def analyze_trial(folder):
    trial = json.loads((folder/"trial.json").read_text())
    prefix = folder/"run/result"/("wall-normal" if trial["case"] == "normal" else "wall-fault")
    result = json.loads(prefix.with_suffix(".json").read_text())
    jobs = read_csv(Path(str(prefix)+"-execution.csv"))
    threads = result["threads"]
    if (len(threads) != 10 or len({t["tid"] for t in threads}) != 10
            or {t["owner"] for t in threads} != set(range(10))):
        raise ValueError("missing/duplicate owner TIDs")
    owners = {t["owner"]: t["tid"] for t in threads}
    save_csv(folder/"owner-tids.csv", [dict(owner=t["owner"], tid=t["tid"], cpu=t["cpu"],
        policy=t["policy"], priority=t["priority"], affinity=",".join(map(str, t["affinity"])),
        setup_error=t["setup_error"]) for t in threads])
    source = json.loads((folder/"source.json").read_text())
    identity = json.loads((folder/"worker-identity.json").read_text())
    controls = (all(trial.get(k) is True for k in
                    ("setup_control", "load_control", "grid_control", "growth_control"))
                and trial.get("jobs") == 12110 and result["guards_enabled"]
                and not result["transport_trace_enabled"] and result["duration_ns"] == 2540000000
                and identity["uid"] != 0 and identity["euid"] == identity["uid"]
                and int(identity["cap_eff"], 16) == 0 and source.get("stable") is True
                and trial.get("identity_control", True) is True)
    summary = dict(runtime_verdict=trial["verdict"], runtime_reason=result["reason"],
                   first_active_ns=result["first_active_ns"], deadline_misses=result["deadline_misses"],
                   skipped=result["skipped_opportunities"], scope="intrusive diagnostic, not timing acceptance",
                   trace_status="OFF", errors=[], controls_ok=controls,
                   binary_sha256=source["binary_sha256"], source_digest=source["source_digest"])
    if not (folder/"kernel.trace").exists():
        write_summary(folder, summary)
        return summary
    data = collect(folder/"kernel.trace", set(owners.values()))
    data["cycle_times"] = {tid: [c["callback_ns"] for c in cys] for tid, cys in data["cycles"].items()}
    errors = integrity_errors(json.loads((folder/"trace-integrity.json").read_text()), data)
    rows = [job_metrics(j, owners[int(j["owner"])], data, not errors) for j in jobs]
    save_csv(folder/"owner-jobs.csv", rows)
    by_owner = {owner: [r for r in rows if int(r["owner"]) == owner] for owner in owners}
    misses = []
    for owner, group in by_owner.items():
        for i, row in enumerate(group):
            if int(row["detected_ns"]):
                following = next((r for r in group[i:] if int(r["start_ns"])), None)
                misses.append(dict(owner=owner, tid=owners[owner], slot=row["slot"],
                    release_ns=row["release_ns"], deadline_ns=row["deadline_ns"], detected_ns=row["detected_ns"],
                    start_ns=row["start_ns"], end_ns=row["end_ns"],
                    following_slot=following["slot"] if following else "",
                    following_requested_wake_ns=following["requested_wake_ns"] if following else "",
                    following_timer_chain=following["timer_chain"] if following else "NOT OBSERVED",
                    interpretation="Unexecuted slot: following row is context, not a fictitious wake for this slot"
                    if not int(row["start_ns"]) else "Executed late: inspect owner-jobs row"))
    save_csv(folder/"miss-context.csv", misses)
    if misses:
        earliest = min(int(r["deadline_ns"]) for r in misses)
        window = []
        with (folder/"kernel.trace").open() as stream:
            for line in stream:
                event = parse(line)
                if event and earliest-4000000 <= event["ns"] <= earliest+10000000:
                    window.append({k: event[k] for k in ("ns", "tid", "cpu", "kind", "body")})
                    if len(window) == 20000:
                        break
        save_csv(folder/"first-miss-kernel.csv", window)
        summary["window_at_row_cap"] = len(window) == 20000
    observed = [r for r in rows if r["timer_chain"] == "OBSERVED"]
    untrusted = [r for r in rows if r["timer_chain"] == "UNTRUSTED"]
    incomplete = sum(r["coverage"] != "valid" for r in rows if int(r["start_ns"]))
    if incomplete and not errors:
        errors.append(f"incomplete scheduler/IRQ coverage in {incomplete} jobs")
    metrics = ("soft_minus_requested_ns", "callback_minus_soft_ns", "callback_minus_hard_ns",
               "switch_minus_wake_ns", "body_minus_switch_ns", "body_wall_ns", "off_cpu_ns",
               "runnable_off_cpu_ns", "irq_overlap_ns")
    linked_tids = {r["tid"] for r in observed}
    summary.update(trace_status="INVALID" if errors else "VALID" if linked_tids == set(owners.values()) else "PARTIAL",
                   errors=errors, tids_without_timer_chain=sorted(set(owners.values())-linked_tids),
                   boundary_unclosed_irq=data["unclosed_irq"],
                   text_resolution_ns=RESOLUTION_NS, parsed_events=data["parsed"],
                   unparsed_lines=data["unknown_lines"], unparsed_examples=data["unknown_examples"],
                   event_counts=data["event_counts"],
                   untrusted_chains=len(untrusted),
                   observed_chains=len(observed), executed_jobs=sum(bool(int(r["start_ns"])) for r in rows),
                   maxima_ns={k: max((r[k] for r in observed), default=None) for k in metrics},
                   causal_verdict="Observed intervals only; missing edges remain unknown; no automatic OS/root-cause ruling")
    write_summary(folder, summary)
    return summary


def write_summary(folder, summary):
    (folder/"analysis.json").write_text(json.dumps(summary, indent=2)+"\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    result = {}
    for mode in ("off", "on"):
        try:
            result[mode] = analyze_trial(args.directory/mode)
        except (OSError, ValueError, KeyError) as error:
            result[mode] = dict(trace_status="INCOMPLETE", errors=[str(error)])
    valid = (result["off"]["trace_status"] == "OFF" and result["on"]["trace_status"] == "VALID"
             and all(result[m].get("controls_ok") for m in ("off", "on"))
             and all(result["off"].get(k) == result["on"].get(k) for k in ("source_digest", "binary_sha256")))
    result["comparison"] = dict(collection_valid=valid,
        interpretation="OFF/ON may have different failures; observer effect is not a fix",
        m4="NOT CLOSED", original_failures="retained")
    (args.directory/"analysis.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result, indent=2))
    return 0 if valid else 2


if __name__ == "__main__":
    raise SystemExit(main())

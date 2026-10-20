#!/usr/bin/env python3
"""Read-only first-miss analysis of an already validated capture; writes a new directory."""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location("kernel_analysis", ROOT/"tools/m4_kernel_analysis.py")
kernel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kernel)


def read_json(path):
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("on", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    p, out = args.on, args.output
    summary = read_json(p/"analysis.json")
    if summary["trace_status"] != "VALID" or not summary["controls_ok"]:
        raise ValueError("valid trace and workload controls required")
    out.mkdir(parents=True, exist_ok=False)
    jobs = kernel.read_csv(p/"owner-jobs.csv")
    misses = kernel.read_csv(p/"miss-context.csv")
    first = min(misses, key=lambda r: (int(r["deadline_ns"]), int(r["owner"])))
    sample = next(r for r in jobs if r["owner"] == first["owner"] and r["slot"] == first["following_slot"])
    assert sample["timer_chain"] == "OBSERVED"
    origin = min(int(j["release_ns"]) for j in jobs)-100_000_000
    deadline, detected = int(first["deadline_ns"]), int(first["detected_ns"])
    events = kernel.read_csv(p/"run/result/wall-normal-events.csv")
    override = next(e for e in events if e["kind"] == "override-applied" and int(e["time_ns"]) >= detected)
    threads = read_json(p/"run/result/wall-normal.json")["threads"]
    cpu = next(t["cpu"] for t in threads if t["owner"] == int(first["owner"]))
    worker_pid = read_json(p/"worker-identity.json")["pid"]
    window, children, switches = [], [], []
    left, right = int(first["release_ns"])-1_000_000, deadline+100_000
    for line in (p/"kernel.trace").open():
        e = kernel.parse(line)
        if not e:
            continue
        if e["kind"] == "sched_wakeup_new" and e["tid"] == worker_pid:
            children.append({k: e[k] for k in ("ns", "tid", "cpu", "kind", "body")})
        if left <= e["ns"] <= right:
            window.append({k: e[k] for k in ("ns", "tid", "cpu", "kind", "body")})
            if e["cpu"] == cpu and e["kind"] == "sched_switch":
                switches.append(e)
    wake, switch = int(sample["wake_ns"]), int(sample["switch_ns"])
    data = kernel.collect(p/"kernel.trace", {int(first["tid"])})
    assert not data["unknown_lines"] and not data["unclosed_irq"]
    irq_wait = kernel.union_length([(a, b) for (irq_cpu, _), intervals in data["irqs"].items()
                                   if irq_cpu == cpu for a, b in intervals.overlap(wake, switch)])
    occupants = []
    for previous, following in zip(switches, switches[1:]):
        start, end = max(wake, previous["ns"]), min(switch, following["ns"])
        if start >= end:
            continue
        assert previous["fields"]["next_pid"] == following["fields"]["prev_pid"]
        occupants.append(dict(cpu=cpu, tid=int(previous["fields"]["next_pid"]),
                              start_ns=start, end_ns=end, duration_ns=end-start,
                              switch_in=previous["body"], switch_out=following["body"]))
    kernel.save_csv(out/"first-miss-kernel.csv", window)
    kernel.save_csv(out/"worker-children.csv", children)
    kernel.save_csv(out/"cpu-occupants-during-wait.csv", occupants)
    kernel.save_csv(out/"first-missing-slots.csv",
                    [m for m in misses if int(m["deadline_ns"]) == deadline])
    kernel.save_csv(out/"following-executed-job.csv", [sample])
    timeline = [
        ("missed_slot_release", int(first["release_ns"])),
        ("timer_soft_expiry", int(sample["soft_ns"])),
        ("timer_hard_expiry", int(sample["hard_ns"])),
        ("timer_callback", int(sample["callback_ns"])),
        ("target_wakeup", wake),
        ("newer_slot_release", int(sample["release_ns"])),
        ("cpu_switch_in", switch),
        ("following_slot_body_start", int(sample["start_ns"])),
        ("following_slot_body_end", int(sample["end_ns"])),
        ("missed_slot_deadline", deadline),
        ("independent_detection", detected),
        ("physical_override", int(override["time_ns"])),
    ]
    kernel.save_csv(out/"timeline.csv", [dict(event=name, monotonic_ns=ns,
        runtime_elapsed_ms=(ns-origin)/1e6) for name, ns in timeline])
    report = dict(origin_ns=origin, first_owner=int(first["owner"]), tid=int(first["tid"]),
                  missing_slot=int(first["slot"]), actual_following_slot=int(sample["slot"]),
                  timer_beyond_hard_ns=int(sample["callback_minus_hard_ns"]),
                  runnable_wait_ns=switch-wake, actual_body_ns=int(sample["body_wall_ns"]),
                  irq_overlap_during_wait_ns=irq_wait,
                  detection_after_deadline_ns=detected-deadline,
                  override_after_detection_ns=int(override["time_ns"])-detected,
                  occupants=occupants, scope="this valid OTHER trace only; not FIFO or whole-system acceptance")
    (out/"report.json").write_text(json.dumps(report, indent=2)+"\n")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ms = lambda ns: (ns-origin)/1e6
    fig, ax = plt.subplots(figsize=(10, 3.8), layout="constrained")
    release = int(first["release_ns"])
    ax.broken_barh([(ms(release), 2)], (2.7, .55), facecolors="#c5cbd4")
    ax.text(ms(release)+.08, 2.96, f"slot {first['slot']}: no execution", va="center", fontsize=10)
    ax.broken_barh([(ms(int(sample["release_ns"])), 2)], (1.7, .55), facecolors="#d4e9e0")
    ax.text(ms(int(sample["release_ns"]))+.08, 1.96,
            f"slot {sample['slot']}: newest released", va="center", fontsize=10)
    ax.broken_barh([(ms(wake), (switch-wake)/1e6)], (.7, .55), facecolors="#e8b35c")
    ax.text(ms(wake)+.1, .96, f"Runnable, waiting for CPU: {(switch-wake)/1e6:.3f} ms",
            va="center", fontsize=10)
    ax.scatter([ms(wake), ms(switch)], [.96, .96], color=["#2b6b9a", "#247859"], zorder=4)
    ax.axvline(ms(deadline), color="#b64545", linestyle="--")
    ax.scatter([ms(detected), ms(int(override["time_ns"]))], [.2, -.05], color="#b64545")
    ax.text(ms(release), -.55,
            f"Timer excess: {report['timer_beyond_hard_ns']/1000:.3f} us; body: {report['actual_body_ns']/1000:.3f} us\n"
            f"Deadline -> detect: {report['detection_after_deadline_ns']/1000:.3f} us; "
            f"detect -> override: {report['override_after_detection_ns']/1000:.3f} us",
            fontsize=10, va="top")
    ax.set(xlim=(ms(release)-.15, ms(deadline)+.35), ylim=(-1.05, 3.6),
           yticks=[], xlabel="Elapsed monotonic time from runtime origin (ms)",
           title=f"First missed opportunity: owner {first['owner']} / CPU{cpu} (one valid capture)")
    ax.grid(axis="x", alpha=.2)
    fig.savefig(out/"first-miss.svg")
    svg = out/"first-miss.svg"
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines())+"\n")
    fig.savefig(out/"first-miss.png", dpi=140)
    plt.close(fig)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

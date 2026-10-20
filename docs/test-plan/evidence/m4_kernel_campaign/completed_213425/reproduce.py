#!/usr/bin/env python3
"""Audit all 22 collected workloads; retain separate capture/runtime verdicts."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[5]/"tools"))
import m4_kernel_analysis as kernel


def read(path):
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("analyzed", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    src, out = args.analyzed, args.output
    out.mkdir(parents=True, exist_ok=False)
    results = read(src/"results.json")
    assert len(results) == 11 and all(r["valid"] for r in results)
    rows, maxima, buffers, sources = [], [], [], set()
    for pair in results:
        for mode in ("off", "on"):
            folder = src/f"{pair['pair']:02d}-{pair['case']}"/mode
            normal = pair["case"] == "other-loaded"
            prefix = folder/"run/result"/("wall-normal" if normal else "wall-fault")
            result, trial = read(prefix.with_suffix(".json")), read(folder/"trial.json")
            jobs = kernel.read_csv(Path(str(prefix)+"-execution.csv"))
            events = kernel.read_csv(Path(str(prefix)+"-events.csv"))
            summary = pair["modes"][mode]
            source = read(folder/"source.json")
            sources.add((source["source_commit"], source["source_digest"], source["binary_sha256"]))
            assert source["stable"] and len(jobs) == 12110 and summary["controls_ok"]
            identity = read(folder/"run/runtime-identity.json")
            assert identity["uids"] == [1000]*4 and int(identity["cap_eff"], 16) == 0
            assert identity["rtprio"] == [20, 20] and trial["identity_control"]
            if normal:
                load = read(folder/"run/load.json")
                load_id = read(folder/"run/load-identity.json")
                assert load_id["uids"] == [1000]*4 and int(load_id["cap_eff"], 16) == 0
                assert load_id["rtprio"] == [20, 20]
                assert (load["policy"], load["priority"], load["affinity"]) == (0, 0, [1])
                assert (load["busy_ns"], load["period_ns"]) == (7000000, 10000000)
            priorities = [18, 18, 10, 10, 10, 9, 10, 11, 19, 20]
            for thread in result["threads"]:
                owner = thread["owner"]
                cpu = 0 if owner < 2 or owner >= 8 else 1
                assert thread["setup_error"] == 0 and thread["affinity"] == [cpu]
                assert thread["cpu"] == cpu and thread["policy"] == (0 if normal else 1)
                assert thread["priority"] == (0 if normal else priorities[owner])
            misses = [j for j in jobs if int(j["detected_ns"])]
            row = dict(pair=pair["pair"], mode=mode, runtime=summary["runtime_verdict"],
                       trace=summary["trace_status"], jobs=len(jobs),
                       misses=len(misses), skipped=result["skipped_opportunities"],
                       active_ns=result["first_active_ns"], injection_ns=summary["injection_ns"],
                       pre_injection_misses=summary["missed_before_injection"],
                       detect_after_deadline_ns="", override_after_detect_ns="",
                       gate_latched=result["gate_latched"])
            if not normal:
                assert summary["runtime_verdict"] == "PASS" and not row["pre_injection_misses"]
                assert {(int(j["owner"]), int(j["slot"])) for j in misses} == {
                    (9, slot) for slot in range(550, 554)}
                assert result["first_active_ns"] and result["gate_latched"]
                trip = next(e for e in events if e["kind"] == "deadline-detected")
                override = next(e for e in events if e["kind"] == "override-applied")
                returned = next(e for e in events if e["kind"] == "overrun-ended")
                assert trip["owner"] == "8" and trip["code"] == "9" and override["owner"] == "8"
                assert row["injection_ns"] <= int(trip["time_ns"]) < int(returned["time_ns"])
                row["detect_after_deadline_ns"] = int(trip["time_ns"])-int(trip["deadline_ns"])
                row["override_after_detect_ns"] = int(override["time_ns"])-int(trip["time_ns"])
            rows.append(row)
            if mode == "on":
                assert summary["trace_status"] == "VALID"
                assert summary["observed_chains"] == summary["executed_jobs"]
                integrity = read(folder/"trace-integrity.json")
                assert not integrity["marker_errors"] and not integrity["truncated"]
                for cpu, text in integrity["stats"].items():
                    stats = dict(line.split(": ", 1) for line in text.splitlines())
                    assert all(int(stats[k]) == 0 for k in ("overrun", "commit overrun", "dropped events"))
                    buffers.append(dict(pair=pair["pair"], cpu=cpu, bytes=int(stats["bytes"]),
                                        entries=int(stats["entries"]), dropped=0))
                maxima.append(dict(pair=pair["pair"], **summary["maxima_ns"]))
    assert len(sources) == 1
    kernel.save_csv(out/"workloads.csv", rows)
    kernel.save_csv(out/"kernel-maxima.csv", maxima)
    kernel.save_csv(out/"buffer-usage.csv", buffers)

    # First planned FIFO ON, chosen by order, not by best response.
    folder = src/"02-fifo-monitor-overrun/on"
    jobs = kernel.read_csv(folder/"owner-jobs.csv")
    events = kernel.read_csv(folder/"run/result/wall-fault-events.csv")
    job = next(j for j in jobs if j["owner"] == "9" and j["slot"] == "550")
    origin = min(int(j["release_ns"]) for j in jobs)-100000000
    timeline = [(name, int(job[field])) for name, field in (
        ("original_slot_release", "release_ns"), ("timer_soft_expiry", "soft_ns"),
        ("timer_hard_expiry", "hard_ns"), ("timer_callback", "callback_ns"),
        ("target_wakeup", "wake_ns"), ("switch_in", "switch_ns"),
        ("body_start", "start_ns"), ("original_completion_deadline", "deadline_ns"),
        ("body_end", "end_ns"))]
    kinds = {"overrun-injected", "overrun-ended", "deadline-detected",
             "override-applied", "gate-closed-observed", "zone-protection-ack",
             "leaf-protection-selected"}
    kernel.save_csv(out/"fifo-events.csv", [e for e in events if e["kind"] in kinds])
    timeline += [(e["kind"]+"_owner"+e["owner"], int(e["time_ns"]))
                 for e in events if e["kind"] in kinds]
    kernel.save_csv(out/"fifo-timeline.csv", [dict(event=name, monotonic_ns=ns,
        elapsed_ms=(ns-origin)/1e6) for name, ns in sorted(timeline, key=lambda v: v[1])])
    kernel.save_csv(out/"fifo-injected-job.csv", [job])
    # These sampled model rows carry a separate Central observation timestamp.
    # They do not replace the exact watchdog detection/override events above.
    model = kernel.read_csv(folder/"run/result/wall-fault.csv")
    kernel.save_csv(out/"fifo-model-response.csv",
                    [r for r in model if 1190 <= float(r["elapsed_ms"]) <= 1500])
    fifo = [r for r in rows if r["pair"] != 1]
    ranges = {key: dict(min=min(r[key] for r in fifo), max=max(r[key] for r in fifo))
              for key in ("detect_after_deadline_ns", "override_after_detect_ns")}
    report = dict(source=list(sources)[0], workloads=22, valid_pairs=11,
                  runtime_pass=20, runtime_fail=2, fifo_pre_injection_misses=0,
                  fifo_expected_misses=80, fifo_ranges_ns=ranges,
                  fifo_representative={k: job[k] for k in (
                      "tid", "callback_minus_hard_ns", "switch_minus_wake_ns",
                      "body_wall_ns", "scheduled_ns", "off_cpu_ns",
                      "runnable_off_cpu_ns", "blocked_ns", "irq_overlap_ns")},
                  m4="NOT CLOSED", historical_fifo_cause="OPEN; not reproduced",
                  scope="diagnosis only; no new acceptance threshold")
    (out/"report.json").write_text(json.dumps(report, indent=2)+"\n")
    plot(out, src, origin, job, events)
    print(json.dumps(report, indent=2))


def plot(out, src, origin, job, events):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 1, figsize=(10, 6.5), layout="constrained")
    other = read(src/"other-detail/report.json")
    sample = kernel.read_csv(src/"other-detail/following-executed-job.csv")[0]
    stamps = {r["event"]: int(r["monotonic_ns"])
              for r in kernel.read_csv(src/"other-detail/timeline.csv")}
    base = other["origin_ns"]
    ms = lambda ns: (ns-base)/1e6
    release, wake, switch = (stamps[k] for k in ("missed_slot_release", "target_wakeup", "cpu_switch_in"))
    ax = axes[0]
    ax.broken_barh([(ms(wake), (switch-wake)/1e6)], (0.7, .5), facecolors="#e5ac45")
    ax.broken_barh([(ms(release), 2)], (1.6, .5), facecolors="#ced3db")
    ax.text(ms(wake)+.05, .95, f"CPU wait {(switch-wake)/1e6:.3f} ms", va="center")
    ax.text(ms(release)+.05, 1.85, f"Slot {other['missing_slot']}: no execution", va="center")
    ax.scatter([ms(stamps["following_slot_body_start"])], [.4], color="#247859", label="Following body")
    ax.axvline(ms(stamps["missed_slot_deadline"]), color="#b64545", linestyle="--", label="Original deadline")
    ax.set(xlim=(min(ms(wake), ms(release))-.15, ms(stamps["physical_override"])+.25),
           ylim=(0, 2.5), yticks=[], xlabel="Runtime elapsed monotonic ms",
           title=f"OTHER: timer excess {other['timer_beyond_hard_ns']/1000:.3f} us; "
                 f"following slot {sample['slot']} body {other['actual_body_ns']/1000:.3f} us")
    # The wake predates slot70's release. Do not clip it or relabel it as slot70's timer.
    ax = axes[1]
    ms = lambda ns: (ns-origin)/1e6
    begin, end = int(job["start_ns"]), int(job["end_ns"])
    trip = next(e for e in events if e["kind"] == "deadline-detected")
    override = next(e for e in events if e["kind"] == "override-applied")
    ax.broken_barh([(ms(begin), (end-begin)/1e6)], (.8, .5), facecolors="#82b5d1")
    ax.text(ms(begin)+.1, 1.05, "Monitor: injected sleep (6 ms blocked)", va="center")
    deadline, detected, applied = int(job["deadline_ns"]), int(trip["time_ns"]), int(override["time_ns"])
    ax.axvline(ms(deadline), color="#b64545", linestyle="--", label="Original deadline")
    ax.scatter([ms(detected)], [.5], color="#b64545", label="Physical detects")
    ax.scatter([ms(applied)], [.25], color="#247859", label="Physical overrides")
    ax.set(xlim=(1199.8, 1206.4), ylim=(0, 1.9), yticks=[], xlabel="Runtime elapsed monotonic ms",
           title=f"FIFO first ON: Physical detects +{(detected-deadline)/1000:.3f} us; "
                 f"override +{(applied-detected)/1000:.3f} us later")
    for ax in axes:
        ax.grid(axis="x", alpha=.2)
        ax.legend(loc="upper left", fontsize=8, frameon=False, ncol=3)
    fig.savefig(out/"representative-timelines.svg")
    fig.savefig(out/"representative-timelines.png", dpi=140)
    plt.close(fig)


if __name__ == "__main__":
    main()

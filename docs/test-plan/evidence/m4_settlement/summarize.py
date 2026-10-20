#!/usr/bin/env python3
"""Rebuild small review CSVs/plots from the retained raw directories (no tests run).

python3 summarize.py build/m4-settlement docs/test-plan/evidence/m4_settlement
For an offline review, extract development.tar.gz and final/verification.tar.gz
into one raw root; extract timing48/raw.tar.gz there as well.
"""
import csv
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

raw, out = map(Path, sys.argv[1:])


def read(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def save(path, rows):
    with path.open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


timeline, physical = [], []
cases = ("rear-19p8ms", "both-12ms", "live-pending", "sustained-pending", "pending-timeout")
for phase, directory in (("before", raw/"before"), ("after", raw/"full/normal")):
    for case in cases:
        folder = directory/"delivery-causal"/case
        path = folder/"logical-normal-transport.csv"
        if not path.exists():
            continue
        events = read(path)
        command_tokens = {e["token"] for e in events
                          if e["original_source_ns"] == "2001000000" and e["operation"] == "3"}
        seen = set()
        for event in events:
            if event["original_source_ns"] != "2001000000" or event["token"] not in command_tokens:
                continue
            key = (event["stage"], event["owner"], event["token"])
            if key in seen:
                continue  # First occurrence only; complete trace remains in archive.
            seen.add(key)
            row = {"phase": phase, "case": case,
                   "elapsed_ms": (int(event["time_ns"])-1000000000)/1e6, **event}
            timeline.append(row)
            if event["stage"] == "central-enqueued" and event["operation"] == "3":
                for marker, field in (("contract/root-source", "original_source_ns"),
                                      ("contract/envelope-deadline", "envelope_deadline_ns"),
                                      ("contract/inner-expiry", "inner_deadline_ns")):
                    timeline.append({**row, "stage": marker, "time_ns": event[field],
                                     "elapsed_ms": (int(event[field])-1000000000)/1e6})
                if event["peer"] == "0":
                    stamp = int(event["original_source_ns"])+20000000
                    timeline.append({**row, "stage": "contract/next-nominal-allocation",
                                     "time_ns": str(stamp), "elapsed_ms": (stamp-1000000000)/1e6})
        for event in read(folder/"logical-normal-events.csv"):
            if event["kind"] == "command-expired":
                empty = {key: "" for key in timeline[0]}
                timeline.append({**empty, "phase": phase, "case": case,
                                 "elapsed_ms": event["elapsed_ms"], "time_ns": event["time_ns"],
                                 "stage": "observed/command-expired", "owner": event["owner"],
                                 "epoch": event["epoch"], "original_source_ns": event["source_ns"],
                                 "inner_deadline_ns": event["deadline_ns"], "outcome": event["code"]})
        result = json.loads((folder/"logical-normal.json").read_text())
        for key in ("first_fault_ns", "all_protected_ns"):
            if result[key]:
                empty = {key: "" for key in timeline[0]}
                timeline.append({**empty, "phase": phase, "case": case,
                                 "stage": "observed/"+key, "time_ns": result[key]+1000000000,
                                 "elapsed_ms": result[key]/1e6})
        for row in read(folder/"logical-normal.csv"):
            if 980 <= float(row["elapsed_ms"]) <= 1250:
                physical.append({"phase": phase, "case": case, **row})
save(out/"command-timeline.csv", timeline)
save(out/"physical-window.csv", physical)

fig, axes = plt.subplots(3, 1, figsize=(10, 8), constrained_layout=True)
for ax, case in zip(axes, cases[:3]):
    for phase, y, color in (("before", 1, "#a33b35"), ("after", 0, "#176c89")):
        rows = [r for r in timeline if r["phase"] == phase and r["case"] == case]
        fault = next((r for r in rows if r["stage"] == "observed/first_fault_ns"), None)
        markers = {"central-enqueued": ("o", "TX"), "central-result-accepted": ("s", "result"),
                   "central-result-rejected": ("x", "late result"),
                   "observed/first_fault_ns": ("X", "Central protection"),
                   "observed/command-expired": ("D", "applied expiry"),
                   "leaf-output-published": ("^", "output"),
                   "contract/next-nominal-allocation": ("|", "due"),
                   "contract/envelope-deadline": ("|", "deadline")}
        for row in rows:
            if row["stage"] not in markers:
                continue
            if row["stage"] == "leaf-output-published" and row["outcome"] != "1":
                continue
            if (row["stage"] == "observed/command-expired" and fault
                    and float(row["elapsed_ms"]) > float(fault["elapsed_ms"])):
                continue  # Post-protection expiry is retained in CSV, not a causal marker.
            marker, label = markers[row["stage"]]
            x = float(row["elapsed_ms"])
            offset = .2 if row["peer"] == "1" or row["owner"] == "4" else -.2
            ax.scatter(x, y+offset, color=color, marker=marker, s=36)
        if fault:
            ax.text(float(fault["elapsed_ms"])+.15, y+.32,
                    f"Central protection {float(fault['elapsed_ms']):g}", fontsize=8)
    ax.set(title=case, xlim=(1000, 1033), ylim=(-.4, 1.55), yticks=[0, 1], yticklabels=["after", "before"],
           xlabel="Logical elapsed ms (same clock; origin = 1 s)")
    ax.grid(axis="x", alpha=.25)
fig.suptitle("Settlement boundaries: o TX, s result, x late, ^ output, D applied expiry, | due/deadline\n"
             "Original build has no output-publication trace; publication is not physical response", fontsize=11)
fig.savefig(out/"command-timeline.svg")
fig.savefig(raw/"command-timeline.png", dpi=130)
plt.close(fig)

failures = []
cohort = json.loads((raw/"timing48/cohort.json").read_text())
for run in cohort:
    if run["verdict"] != "FAIL":
        continue
    prefix = raw/"timing48"/run["raw"]/"result/wall-normal"
    events = read(Path(str(prefix)+"-events.csv"))
    jobs = read(Path(str(prefix)+"-execution.csv"))
    origin = int(jobs[0]["release_ns"])-100000000
    detect = next(e for e in events if e["kind"] == "deadline-detected")
    first = next(j for j in jobs if j["owner"] == detect["code"]
                 and j["deadline_ns"] == detect["deadline_ns"])
    apply = next(e for e in events if e["kind"] == "override-applied")
    preceding = [j for j in jobs if j["owner"] == first["owner"]
                 and int(j["slot"]) < int(first["slot"]) and int(j["end_ns"])]
    previous = preceding[-1] if preceding else None
    following = next((j for j in jobs if j["owner"] == first["owner"]
                      and int(j["slot"]) > int(first["slot"]) and int(j["start_ns"])), None)
    result = json.loads(prefix.with_suffix(".json").read_text())
    failures.append({
        "raw": run["raw"], "verdict": run["verdict"], "reason": result["reason"],
        "first_owner": first["owner"], "first_slot": first["slot"],
        "release_ms": (int(first["release_ns"])-origin)/1e6,
        "deadline_ms": (int(first["deadline_ns"])-origin)/1e6,
        "start_ns": first["start_ns"], "end_ns": first["end_ns"],
        "detect_ms": (int(detect["time_ns"])-origin)/1e6,
        "override_ms": (int(apply["time_ns"])-origin)/1e6,
        "previous_body_ms": (int(previous["end_ns"])-int(previous["start_ns"]))/1e6 if previous else "",
        "previous_cpu_ms": int(previous["cpu_ns"])/1e6 if previous else "",
        "following_requested_wake_delay_ms":
            (int(following["start_ns"])-int(following["requested_wake_ns"]))/1e6 if following else "",
        "deadline_misses": run["deadline_misses"], "skipped": run["skipped"],
        "setup_control": run["setup_control"], "load_control": run["load_control"],
        "grid_control": run["grid_control"], "causal_status": "kernel interval unobserved / OPEN"})
save(out/"timing48/failures.csv", failures)

fig, ax = plt.subplots(figsize=(9, 4), constrained_layout=True)
for policy, offset, color in (("other", -.16, "#b05738"), ("fifo", .16, "#167389")):
    for i, profile in enumerate(("normal", "sanitized")):
        samples = [r for r in cohort if r["policy"] == policy and r["profile"] == profile]
        passed = sum(r["verdict"] == "PASS" for r in samples)
        ax.bar(i+offset, passed, width=.3, color=color, label=policy if i == 0 else None)
        ax.bar(i+offset, len(samples)-passed, width=.3, bottom=passed, color="#eee",
               edgecolor=color, hatch="//")
        ax.text(i+offset, passed/2, f"{passed}/{len(samples)} PASS", ha="center", color="white", fontsize=9)
ax.set(xticks=[0, 1], xticklabels=["Normal", "ASan/UBSan"], ylim=(0, 14),
       ylabel="Runs (all planned runs retained)",
       title="97afb35: unchanged 48-run wall timing cohort\nHatched = FAIL; historical FIFO failures remain OPEN")
ax.legend()
fig.savefig(out/"timing48/cohort.svg")
fig.savefig(raw/"timing-cohort.png", dpi=130)

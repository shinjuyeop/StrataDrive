#!/usr/bin/env python3
"""Offline campaign analysis in a new directory; never alter collected originals."""
import argparse
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def split_misses(jobs, events):
    injected = [int(e["time_ns"]) for e in events
                if e["kind"] == "overrun-injected" and e["owner"] == "9"]
    injection = min(injected, default=0)
    misses = [j for j in jobs if int(j["detected_ns"])]
    # A missed opportunity whose deadline was BEFORE injection cannot be
    # attributed to that injection, even if detected after injection.
    before = [j for j in misses if injection and int(j["deadline_ns"]) <= injection]
    after = [j for j in misses if injection and int(j["deadline_ns"]) > injection]
    return dict(injection_ns=injection, missed_before_injection=len(before),
                missed_after_injection=len(after),
                missed_without_observed_injection=len(misses) if not injection else 0,
                first_detection_ns=min((int(j["detected_ns"]) for j in misses), default=0),
                post_injection_note="temporal grouping only; not proof all later misses were intentional")


def read_csv(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def copy_input(source, target):
    # Trace is large and is only opened read-only by the analyzer. All potentially
    # regenerated CSV/JSONs must be copied, not hard-linked to collected originals.
    if str(source).endswith("/kernel.trace"):
        os.link(source, target)
    else:
        shutil.copy2(source, target)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error("analysis must run as original user")
    plan = json.loads((args.capture/"campaign.json").read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(args.capture/"campaign.json", args.output/"source-campaign.json")
    rows = []
    for attempt in plan["attempts"]:
        folder = args.output/f"{attempt['pair']:02d}-{attempt['case']}"
        row = dict(pair=attempt["pair"], case=attempt["case"], collection=attempt["status"],
                   valid=False, error="", modes={})
        try:
            if "directory" not in attempt:
                raise ValueError("planned attempt NOT RUN")
            shutil.copytree(args.capture/attempt["directory"], folder, copy_function=copy_input)
            with (folder/"offline-analysis.log").open("w") as log:
                code = subprocess.run([sys.executable, str(ROOT/"tools/m4_kernel_analysis.py"),
                    str(folder)], stdout=log, stderr=subprocess.STDOUT, timeout=60).returncode
            result = json.loads((folder/"analysis.json").read_text())
            row["valid"] = code == 0 and result["comparison"]["collection_valid"] and attempt["status"] == "COLLECTED"
            for mode in ("off", "on"):
                prefix = folder/mode/"run/result"/("wall-normal" if attempt["case"] == "other-loaded" else "wall-fault")
                events = read_csv(Path(str(prefix)+"-events.csv"))
                jobs = read_csv(Path(str(prefix)+"-execution.csv"))
                row["modes"][mode] = {**result[mode], **split_misses(jobs, events)}
        except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
            row.update(valid=False, error=str(error))
        rows.append(row)
        (args.output/"results.json").write_text(json.dumps(rows, indent=2)+"\n")
    flat = [dict(pair=r["pair"], case=r["case"], collection=r["collection"],
                 valid=r["valid"], mode=m, runtime=v.get("runtime_verdict"),
                 injection_ns=v["injection_ns"], pre=v["missed_before_injection"],
                 post=v["missed_after_injection"], no_injection=v["missed_without_observed_injection"])
            for r in rows for m, v in r["modes"].items()]
    if flat:
        with (args.output/"summary.csv").open("w") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(flat[0])); writer.writeheader(); writer.writerows(flat)
    # Missing/invalid collection and workload failure are distinct, both nonzero.
    return 2 if len(rows) != 11 or not all(r["valid"] for r in rows) else (
        1 if any(v.get("runtime_verdict") != "PASS" for r in rows for v in r["modes"].values()) else 0)


if __name__ == "__main__":
    raise SystemExit(main())

"""Check the selected person views against included and size-excluded instance masks."""

import argparse
from collections import Counter
import gzip
import json
from pathlib import Path

from person_pair_errors import false_positives
from person_support_replay import CACHE, PREVIOUS, choose, frames, read, rows
from quality_benchmark_v3 import measure


def audit(data, minimum):
    flagged = Counter()
    false = Counter()
    outcomes = Counter()
    for row, truth, _ in data:
        chosen, use, flags = choose(row["full"], row["zoom"], minimum)
        objects = [o for o in truth["objects"] if o["class_id"] == 0]
        raw = measure(row["zoom"], objects, truth["excluded"])
        selected = measure(chosen, objects, truth["excluded"])
        reasons = dict(false_positives(row["zoom"], truth))
        false.update(reason for _, reason in false_positives(chosen, truth))
        for i, flag in enumerate(flags):
            if flag["small"] and not flag["confirmed"]:
                flagged[reasons.get(i, "eligible_person")] += 1
        if not use:
            outcomes["fallback_frames"] += 1
            outcomes["eligible_people_only_in_zoom"] += len(raw[1] - selected[1])
            outcomes["eligible_people_only_in_full"] += len(selected[1] - raw[1])
    return dict(
        unconfirmed_small_zoom=flagged, selected_strict_fp=false, fallback=outcomes
    )


def fresh_rows(work):
    ds = work / "Town05_Opt/dataset"
    with gzip.open(work / "fresh.jsonl.gz", "rt") as stream:
        for line, gt, scene in zip(
            stream,
            read(ds / "labels.json"),
            read(ds / "plan.json")["scenes"],
            strict=True,
        ):
            row = json.loads(line)
            if (
                row["rgb"] != gt["rgb_sha256"]
                or row["scene"] != gt["id"]
                or gt["id"] != scene["id"]
            ):
                raise ValueError("unpaired fresh observations")
            yield row, gt, scene


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path)
    args = parser.parse_args()
    minimum = read(args.work / "selection.json")["minimum"]
    records = {
        name: audit(
            rows(PREVIOUS / (name + ".jsonl.gz"), frames(CACHE, "validation", paired)),
            minimum,
        )
        for name, paired in (("archive-validation", False), ("pairs-validation", True))
    }
    records["Town05"] = audit(fresh_rows(args.work), minimum)
    print(json.dumps(records, indent=2))

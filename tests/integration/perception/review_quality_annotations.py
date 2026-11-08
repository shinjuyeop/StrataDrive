#!/usr/bin/env python3
"""Post-hoc v2 label diagnosis on consumed v1 data; never an acceptance decision."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import read_json, local_path
from evaluate import counts, rates
from quality_annotation import SEMANTICS_BY_CLASS, visible_boxes_v2
from quality_benchmark import CLASSES, require, total, write_new


def review(root, output):
    output.mkdir(parents=True, exist_ok=False)
    selected = read_json(root / "candidate-selection.json")["selected"]
    results = {}
    for partition in ("development", "holdout"):
        capture_path = root / f"{partition}-01/dataset/capture.json"
        capture = read_json(capture_path)
        old_truth = read_json(root / f"{partition}-data/evaluation-only-gt.json")
        require(
            old_truth["capture_sha256"] == sha256_file(capture_path), "capture identity"
        )
        rows = []
        for original, old in zip(capture["frames"], old_truth["frames"]):
            require(
                original["scene"] == old["scene"] and original["frame"] == old["frame"],
                "annotation source identity",
            )
            instance = local_path(capture_path.parent, original["instance"]["path"])
            require(
                sha256_file(instance) == original["instance"]["sha256"], "instance hash"
            )
            included, excluded = visible_boxes_v2(instance.read_bytes())
            # Bicycle/motorcycle/vehicle masks must not change under the person fix.
            for field, objects in (("objects", included), ("excluded", excluded)):
                new_vehicles = [
                    {k: v for k, v in o.items() if k != "semantic_tags"}
                    for o in objects
                    if o["class_id"] != 0
                ]
                require(
                    new_vehicles == [o for o in old[field] if o["class_id"] != 0],
                    "v2 unexpectedly changed vehicle annotations",
                )
            rows.append(
                dict(
                    scene=original["scene"],
                    frame=original["frame"],
                    objects=included,
                    excluded=excluded,
                )
            )
        require(len(rows) == len(old_truth["frames"]) == 81, "annotation denominator")
        labels = dict(
            schema="m10-rider-visible-gt-v2",
            partition=partition,
            status="POST_HOC_DIAGNOSTIC_ONLY",
            capture_sha256=sha256_file(capture_path),
            semantic_tags_by_coco_class=SEMANTICS_BY_CLASS,
            frames=rows,
        )
        label_path = output / f"{partition}-labels-v2.json"
        write_new(label_path, labels)
        candidates = (
            ["baseline", "vehicle-nms-v1", "center-refine-v1"]
            if partition == "development"
            else ["baseline", selected]
        )
        results[partition] = {}
        for candidate in candidates:
            run_path = root / f"{partition}-{candidate}/result.json"
            run = read_json(run_path)
            require(len(run["rows"]) == len(rows), "prediction denominator")
            totals = {str(c): dict(tp=0, fp=0, fn=0) for c in CLASSES}
            for gt, prediction in zip(rows, run["rows"]):
                require(
                    prediction["scene"] == gt["scene"]
                    and prediction["frame"] == gt["frame"],
                    "prediction source identity",
                )
                measured = counts(
                    prediction["detections"] if prediction["model_valid"] else [],
                    gt["objects"],
                )
                for cls in totals:
                    for key in totals[cls]:
                        totals[cls][key] += measured[cls][key]
            results[partition][candidate] = dict(
                micro=total(totals),
                per_class=rates(totals),
                run_sha256=sha256_file(run_path),
                labels_sha256=sha256_file(label_path),
            )
    result = dict(
        schema="m10-rider-annotation-review-v2",
        status="POST_HOC_DIAGNOSTIC_ONLY",
        runtime_promotion=False,
        new_holdout=False,
        scope="All images and predictions were already inspected under v1. No revised quality PASS or candidate nomination; fresh prospectively frozen validation required.",
        implementation_sha256=sha256_file(
            Path(__file__).with_name("quality_annotation.py")
        ),
        scores=results,
    )
    write_new(output / "review.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = review(args.experiment, args.output)
    print(result["status"])

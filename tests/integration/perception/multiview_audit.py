"""Reconstruct the fixed candidate score and same-image parent comparison from native masks."""

from collections import Counter
from pathlib import Path
import argparse
import gzip
import hashlib
import json

import numpy as np

from camera_resolution_v1_common import annotate
from fresh_quality_2k_review import read, rgb_bytes
from multiview_detector import TARGET, evaluate_run, records, score_run
from person_pair_candidate import dump
from physical_ai.perception.camera_resolution_v1 import unpack


def audit(run, work, evidence, name):
    policy = read(evidence / "selection.json")["thresholds"]
    rows = list(records(work / (name + "-verified.jsonl.gz")))
    gt = read(run / "evaluation-only-gt.json")["frames"]
    capture = read(run / "dataset/capture.json")["frames"]
    pred = read(run / "baseline/predictions.json")["rows"]
    if len({r["rgb"] for r in rows}) != 81:
        raise ValueError("distinct evaluation denominator")
    for row, f, truth, baseline in zip(rows, capture, gt, pred, strict=True):
        mask = unpack(run / "dataset", f["instance"], 2560, 1536)
        objs, excl = annotate(mask, 2560, 1536)
        if objs != truth["objects"] or excl != truth["excluded"]:
            raise ValueError("original mask truth")
        raw = unpack(run / "dataset", f["rgb"], 2560, 1536)
        if (
            hashlib.sha256(rgb_bytes(raw)).hexdigest() != row["rgb"]
            or baseline["rgb_sha256"] != row["rgb"]
            or not baseline["valid"]
        ):
            raise ValueError("paired RGB")
        if row["detections"][: len(row["base"])] != row["base"]:
            raise ValueError("parent prediction missing")
    parent, _ = score_run(run, rows, {str(c): 1.01 for c in TARGET})
    baseline, _ = score_run(
        run,
        [dict(rgb=r["rgb_sha256"], base=r["detections"], new={}) for r in pred],
        policy,
    )
    official = read(run / "baseline/score.json")
    if any(
        baseline["card"][k] != official[k]
        for k in ("micro", "per_class", "strata", "near_person")
    ):
        raise ValueError("YOLOX replay")
    selected, trace = score_run(run, rows, policy)
    if selected != read(work / (name + "-score.json")) or any(
        x["detections"] != r["detections"] for x, r in zip(trace, rows, strict=True)
    ):
        raise ValueError("candidate replay")
    if name == "site492":
        previous = read(
            evidence.parent / "m10_bus_recall_v1/evaluation-holdout-01-score.json"
        )
        if parent["card"]["per_class"] != previous["card"]["per_class"]:
            raise ValueError("previous score did not reproduce")
    lat = np.asarray([r["elapsed_s"] for r in rows]) * 1000
    counts = Counter({str(c): 0 for c in TARGET})
    retain = []
    for row in rows:
        counts.update(str(x["class_id"]) for x in row["detections"][len(row["base"]) :])
        retain.append({k: row[k] for k in ("rgb", "base", "detections", "elapsed_s")})
    result = dict(
        passed=selected["passed"],
        parent=parent["card"],
        candidate=selected,
        baseline={
            k: official[k] for k in ("micro", "per_class", "strata", "near_person")
        },
        additions=counts,
        latency_ms=dict(
            p50=float(np.median(lat)),
            p95=float(np.percentile(lat, 95)),
            min=float(min(lat)),
            max=float(max(lat)),
        ),
        mask_frames_replayed=len(rows),
        visibility=read(run / "visibility.json"),
        boot_restoration=read(run / "boot-restoration.json"),
    )
    dataset = run / "dataset/capture.json"
    result["capture_sha256"] = hashlib.sha256(dataset.read_bytes()).hexdigest()
    if result["visibility"]["capture_sha256"] != result["capture_sha256"]:
        raise ValueError("capture identity")
    dump(evidence / (name + ".json"), result)
    with (evidence / (name + "-detections.json.gz")).open("wb") as out:
        out.write(
            gzip.compress(json.dumps(retain, separators=(",", ":")).encode(), mtime=0)
        )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("run", type=Path)
    parser.add_argument("name", choices=("site492", "holdout"))
    args = parser.parse_args()
    if args.name == "site492":
        if not (args.evidence / "nomination.json").is_file():
            raise ValueError("freeze before retrospective evaluation")
        evaluate_run(
            args.run, args.work, read(args.evidence / "selection.json"), args.name
        )
    audit(args.run, args.work, args.evidence, args.name)

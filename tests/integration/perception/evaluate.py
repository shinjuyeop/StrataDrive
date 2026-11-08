#!/usr/bin/env python3
"""Independent scalar IoU evaluator; ground truth is read only in this program."""

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import (
    MODEL_SHA256,
    PROFILE_PATH,
    CUDA_PROFILE_PATH,
    sha256_file,
)
from physical_ai.perception.dataset import RgbDataset, read_json


def overlap(a, b):
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(
        0, min(a[3], b[3]) - max(a[1], b[1])
    )
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection
    return intersection / union if union > 0 else 0


def valid_box(box):
    return (
        isinstance(box, list)
        and len(box) == 4
        and all(type(v) in (int, float) and math.isfinite(v) for v in box)
        and 0 <= box[0] < box[2] <= 640
        and 0 <= box[1] < box[3] <= 384
    )


def counts(detections, truth):
    by_class = {}
    for cls in (0, 1, 2, 3, 5, 7):
        predictions = sorted(
            [d for d in detections if d["class_id"] == cls], key=lambda d: -d["score"]
        )
        actual = [t for t in truth if t["class_id"] == cls]
        used = set()
        tp = 0
        for prediction in predictions:
            candidates = [
                (overlap(prediction["box"], target["box"]), i)
                for i, target in enumerate(actual)
                if i not in used
            ]
            best = max(
                candidates, default=(0, -1), key=lambda pair: (pair[0], -pair[1])
            )
            if best[0] >= 0.5:
                used.add(best[1])
                tp += 1
        by_class[str(cls)] = {
            "tp": tp,
            "fp": len(predictions) - tp,
            "fn": len(actual) - tp,
        }
    return by_class


def rates(metrics):
    for values in metrics.values():
        tp, fp, fn = values["tp"], values["fp"], values["fn"]
        values["precision"] = tp / (tp + fp) if tp + fp else None
        values["recall"] = tp / (tp + fn) if tp + fn else None
    return metrics


def evaluate(dataset_path, truth_path, run_path):
    dataset = RgbDataset(dataset_path)
    # Verify RGB bytes even though the evaluator does not infer on them.
    list(dataset.frames())
    truth = read_json(truth_path)
    summary = read_json(run_path / "result.json")
    execution = summary.get("execution", "cpu")
    if execution not in ("cpu", "cuda"):
        raise ValueError("execution profile")
    if execution == "cuda" and (
        summary.get("execution_profile_sha256") != sha256_file(CUDA_PROFILE_PATH)
        or not summary.get("cpu_node_fallback_disabled")
        or summary.get("provider", [None])[0] != "CUDAExecutionProvider"
    ):
        raise ValueError("CUDA execution provenance")
    if (
        truth["schema"] != "m10-visible-instance-gt-v1"
        or truth["capture_sha256"] != dataset.manifest["capture_sha256"]
        or truth["rgb_manifest_sha256"] != sha256_file(dataset_path)
        or summary["dataset_sha256"] != sha256_file(dataset_path)
        or summary["profile_sha256"] != sha256_file(PROFILE_PATH)
        or summary["model_sha256"] != MODEL_SHA256
        or summary["predictions_sha256"] != sha256_file(run_path / "predictions.jsonl")
    ):
        raise ValueError("evaluation provenance/hash")
    # Strict JSON parser per record (including duplicate/nonfinite rejection).
    records = []
    for line in (run_path / "predictions.jsonl").read_text().splitlines():

        def invalid(value):
            raise ValueError(f"nonfinite prediction {value}")

        def unique(pairs):
            d = {}
            for key, value in pairs:
                if key in d:
                    raise ValueError("duplicate prediction key")
                d[key] = value
            return d

        records.append(
            json.loads(line, parse_constant=invalid, object_pairs_hook=unique)
        )
    expected = len(dataset.manifest["frames"])
    if (
        not len(records)
        == len(truth["frames"])
        == summary["expected"]
        == summary["attempted"]
        == expected
    ):
        raise ValueError("evaluation denominator")
    model_valid = admitted = late = errors = 0
    totals = {str(c): {"tp": 0, "fp": 0, "fn": 0} for c in (0, 1, 2, 3, 5, 7)}
    available = {str(c): {"tp": 0, "fp": 0, "fn": 0} for c in (0, 1, 2, 3, 5, 7)}
    scenes = defaultdict(
        lambda: {
            "frames": 0,
            "gt": 0,
            "tp": 0,
            "fp": 0,
            "fn": 0,
            "excluded": 0,
            "unavailable": 0,
        }
    )
    for source, gt, prediction in zip(
        dataset.manifest["frames"], truth["frames"], records
    ):
        if (
            not source["frame"] == gt["frame"] == prediction["frame"]
            or not source["scene"] == gt["scene"] == prediction["scene"]
            or source["source_ns"] != prediction["source_ns"]
            or source["rgb_sha256"] != prediction["rgb_sha256"]
        ):
            raise ValueError("evaluation source identity/order")
        for target in gt["objects"] + gt["excluded"]:
            if (
                type(target["class_id"]) is not int
                or target["class_id"] not in (0, 1, 2, 3, 5, 7)
                or not valid_box(target["box"])
                or target["visible_pixels"] <= 0
            ):
                raise ValueError("GT shape/class")
        seen = set()
        for target in gt["objects"]:
            identity = (target["class_id"], target["instance_id"])
            if (
                identity in seen
                or target["visible_pixels"] < 25
                or min(
                    target["box"][2] - target["box"][0],
                    target["box"][3] - target["box"][1],
                )
                < 4
            ):
                raise ValueError("GT duplicate/support")
            seen.add(identity)
        if (
            type(prediction["model_valid"]) is not bool
            or type(prediction["admitted"]) is not bool
        ):
            raise ValueError("prediction validity type")
        if (
            type(prediction["elapsed_wall_ns"]) is not int
            or prediction["elapsed_wall_ns"] < 0
        ):
            raise ValueError("wall duration")
        if prediction["model_valid"]:
            model_valid += 1
            detected = prediction["detections"]
            if not isinstance(detected, list) or len(detected) > 100:
                raise ValueError("detection count")
            for detection in detected:
                if (
                    set(detection) != {"class_id", "score", "box"}
                    or type(detection["class_id"]) is not int
                    or detection["class_id"] not in (0, 1, 2, 3, 5, 7)
                    or not valid_box(detection["box"])
                    or type(detection["score"]) not in (int, float)
                    or not math.isfinite(detection["score"])
                    or not 0.35 <= detection["score"] <= 1
                ):
                    raise ValueError("detection payload")
            if prediction["expires_ns"] != source["source_ns"] + 100_000_000:
                raise ValueError("renewed expiry")
            for name in ("preprocess_ns", "inference_ns", "postprocess_ns"):
                if type(prediction[name]) is not int or prediction[name] < 0:
                    raise ValueError("stage duration")
            if (
                sum(
                    prediction[n]
                    for n in ("preprocess_ns", "inference_ns", "postprocess_ns")
                )
                > prediction["elapsed_wall_ns"]
            ):
                raise ValueError("stage duration exceeds total")
            if prediction["admitted"] != (prediction["elapsed_wall_ns"] < 100_000_000):
                raise ValueError("late publication")
            admitted += prediction["admitted"]
            late += not prediction["admitted"]
        else:
            errors += 1
            detected = []
            if prediction["admitted"] or prediction["detections"] is not None:
                raise ValueError("failure encoded as normal")
        track_ids = set()
        if not prediction["admitted"] and prediction["tracks"]:
            raise ValueError("unavailable tracks")
        for track, detection in zip(prediction["tracks"], detected):
            if track["track_id"] in track_ids or track["track_id"] <= 0:
                raise ValueError("duplicate track")
            track_ids.add(track["track_id"])
            history = track["observations"]
            if not 1 <= len(history) <= 10:
                raise ValueError("history bound")
            if (
                history[-1]["frame"] != source["frame"]
                or history[-1]["source_ns"] != source["source_ns"]
                or history[-1]["box"] != detection["box"]
                or track["class_id"] != detection["class_id"]
            ):
                raise ValueError("coasted track")
            if any(
                b["frame"] <= a["frame"] or b["source_ns"] <= a["source_ns"]
                for a, b in zip(history, history[1:])
            ):
                raise ValueError("track history ordering")
        if prediction["admitted"] and len(prediction["tracks"]) != len(detected):
            raise ValueError("track denominator")
        raw_counts = counts(detected, gt["objects"])
        available_counts = counts(
            detected if prediction["admitted"] else [], gt["objects"]
        )
        scene = scenes[source["scene"]]
        scene["frames"] += 1
        scene["gt"] += len(gt["objects"])
        scene["excluded"] += len(gt["excluded"])
        scene["unavailable"] += not prediction["admitted"]
        for cls in totals:
            for key in ("tp", "fp", "fn"):
                totals[cls][key] += raw_counts[cls][key]
                available[cls][key] += available_counts[cls][key]
                scene[key] += raw_counts[cls][key]
    if (model_valid, admitted, late, errors) != (
        summary["model_valid"],
        summary["admitted"],
        summary["late"],
        summary["errors"],
    ):
        raise ValueError("summary counts")
    return {
        "audit": "PASS",
        "quality_acceptance": "NOT_SET",
        "metric": "visible-instance boxes @ IoU0.5; not COCO mAP",
        "frames": expected,
        "model_valid": model_valid,
        "admitted": admitted,
        "late": late,
        "errors": errors,
        "raw_model": rates(totals),
        "admitted_output": rates(available),
        "scenes": dict(scenes),
        "gt_sha256": sha256_file(truth_path),
        "predictions_sha256": sha256_file(run_path / "predictions.jsonl"),
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--truth", type=Path, required=True)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    report = evaluate(a.dataset, a.truth, a.run)
    with a.output.open("x") as output:
        output.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))

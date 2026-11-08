#!/usr/bin/env python3
"""Actual backend health faults and independent evaluator mutation rejection."""

import argparse
import copy
from dataclasses import replace
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import WIDTH, HEIGHT, sha256_file
from physical_ai.perception.dataset import RgbDataset
from physical_ai.perception.yolox import YoloX
from evaluate import evaluate


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--truth", type=Path, required=True)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    evaluate(a.dataset, a.truth, a.run)
    backend = YoloX(a.model)
    _, camera = next(RgbDataset(a.dataset).frames())
    image_rejections = []
    for name, value in (("blackout", 0), ("flat-gray", 128), ("whiteout", 255)):
        try:
            backend.infer(replace(camera, rgb=bytes([value]) * WIDTH * HEIGHT * 3))
        except ValueError as error:
            image_rejections.append({"case": name, "reason": str(error)})
        else:
            raise ValueError("information loss admitted")
    summary = json.loads((a.run / "result.json").read_text())
    rows = [
        json.loads(line)
        for line in (a.run / "predictions.jsonl").read_text().splitlines()
    ]
    valid = next(
        i for i, row in enumerate(rows) if row["model_valid"] and row["detections"]
    )
    mutations = {
        "source_renewal": lambda r: r[valid].__setitem__(
            "source_ns", r[valid]["source_ns"] + 1
        ),
        "expiry_extension": lambda r: r[valid].__setitem__(
            "expires_ns", r[valid]["expires_ns"] + 1
        ),
        "frame_relabel": lambda r: r[valid].__setitem__("frame", r[valid]["frame"] + 1),
        "scene_relabel": lambda r: r[valid].__setitem__("scene", "other"),
        "missing_frame": lambda r: r.pop(),
        "reordered_frames": lambda r: r.reverse(),
        "score_out_of_range": lambda r: r[valid]["detections"][0].__setitem__(
            "score", 2
        ),
        "unsupported_class": lambda r: r[valid]["detections"][0].__setitem__(
            "class_id", 4
        ),
        "box_outside": lambda r: r[valid]["detections"][0]["box"].__setitem__(0, -1),
        "late_publication": lambda r: r[valid].update(
            admitted=True, elapsed_wall_ns=100_000_000
        ),
        "image_identity": lambda r: r[valid].__setitem__("rgb_sha256", "0" * 64),
        "failure_as_empty": lambda r: r[valid].update(
            model_valid=False, admitted=False, detections=[]
        ),
    }
    rejected = []
    with tempfile.TemporaryDirectory() as folder:
        run = Path(folder)
        for name, mutate in mutations.items():
            changed = copy.deepcopy(rows)
            mutate(changed)
            (run / "predictions.jsonl").write_text(
                "".join(json.dumps(r) + "\n" for r in changed)
            )
            updated = dict(
                summary, predictions_sha256=sha256_file(run / "predictions.jsonl")
            )
            (run / "result.json").write_text(json.dumps(updated))
            try:
                evaluate(a.dataset, a.truth, run)
            except (ValueError, KeyError, TypeError):
                rejected.append(name)
            else:
                raise ValueError(f"audit mutation accepted: {name}")
    report = {
        "status": "PASS",
        "image_health_rejected": image_rejections,
        "audit_mutations_rejected": rejected,
    }
    with a.output.open("x") as output:
        output.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()

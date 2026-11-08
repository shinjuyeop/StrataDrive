#!/usr/bin/env python3
"""Same RGB/model FP32 CPU vs CUDA parity; first calls remain measured."""

import argparse
import json
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.dataset import RgbDataset
from physical_ai.perception.yolox import YoloX, preprocess, postprocess
from physical_ai.perception.contract import sha256_file


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    cpu = YoloX(a.model)
    gpu = YoloX(a.model, execution="cuda")
    rows = []
    seen = set()
    for row, camera in RgbDataset(a.dataset).frames():
        if row["scene"] in seen:
            continue
        seen.add(row["scene"])
        tensor, _ = preprocess(camera)
        reference = cpu.session.run(["output"], {"images": tensor})[0]
        candidate = gpu.session.run(["output"], {"images": tensor})[0]
        equal = bool(np.allclose(reference, candidate, atol=1e-3, rtol=1e-4))
        a_det, b_det = postprocess(reference), postprocess(candidate)
        boxes_equal = len(a_det) == len(b_det) and all(
            x.class_id == y.class_id
            and abs(x.score - y.score) <= 1e-4
            and np.allclose(x.box, y.box, atol=0.01, rtol=0)
            for x, y in zip(a_det, b_det)
        )
        rows.append(
            {
                "scene": row["scene"],
                "frame": row["frame"],
                "raw_equal": equal,
                "detections_equal": boxes_equal,
                "count": len(a_det),
                "max_absolute_difference": float(np.max(np.abs(reference - candidate))),
            }
        )
    report = {
        "status": "PASS"
        if rows and all(r["raw_equal"] and r["detections_equal"] for r in rows)
        else "FAIL",
        "raw_atol": 1e-3,
        "raw_rtol": 1e-4,
        "box_atol_pixels": 0.01,
        "score_atol": 1e-4,
        "dataset_sha256": sha256_file(a.dataset),
        "cuda_options": gpu.session.get_provider_options(),
        "rows": rows,
    }
    with a.output.open("x") as output:
        output.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

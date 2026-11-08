#!/usr/bin/env python3
"""Cross-runtime FP32 equivalence on the same frozen RGB input (not accuracy)."""

import argparse
import json
from pathlib import Path
import sys
import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.dataset import RgbDataset
from physical_ai.perception.yolox import YoloX, preprocess
from physical_ai.perception.contract import sha256_file


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    detector = YoloX(args.model)
    network = cv2.dnn.readNetFromONNX(str(args.model))
    network.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
    network.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
    cv2.setNumThreads(4)
    rows, scenes = [], set()
    for row, camera in RgbDataset(args.dataset).frames():
        if row["scene"] in scenes:
            continue
        scenes.add(row["scene"])
        # Independent construction: the frozen camera already has width640,
        # hence no spatial resampling, only bottom256 rows of RGB114 padding.
        rgb = np.frombuffer(camera.rgb, np.uint8).reshape(384, 640, 3)
        padded = np.full((640, 640, 3), 114, np.float32)
        padded[:384] = rgb
        independent = padded.transpose(2, 0, 1)[None].copy()
        tensor, _ = preprocess(camera)
        if not np.array_equal(tensor, independent):
            raise ValueError("preprocess differs from independent RGB tensor")
        onnx = detector.session.run(["output"], {"images": tensor})[0]
        network.setInput(independent)
        opencv = network.forward()
        delta = np.abs(onnx - opencv)
        equal = bool(np.allclose(onnx, opencv, atol=1e-3, rtol=1e-4))
        rows.append(
            {
                "scene": row["scene"],
                "frame": row["frame"],
                "equal": equal,
                "max_absolute_difference": float(delta.max()),
                "values": int(delta.size),
            }
        )
    report = {
        "status": "PASS" if rows and all(r["equal"] for r in rows) else "FAIL",
        "atol": 1e-3,
        "rtol": 1e-4,
        "dataset_sha256": sha256_file(args.dataset),
        "rows": rows,
    }
    with args.output.open("x") as output:
        output.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

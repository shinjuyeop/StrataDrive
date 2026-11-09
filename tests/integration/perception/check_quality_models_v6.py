#!/usr/bin/env python3
"""Pinned L: independent RGB tensor and CPU/CUDA/OpenCV raw comparison."""

import argparse
from pathlib import Path
import sys
import time
import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.dataset import RgbDataset
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.large_model_v6 import LargeYoloX, INPUT_PROFILE
from physical_ai.perception.yolox import preprocess, postprocess
from quality_benchmark import write_new


def check(dataset, model):
    start = time.monotonic_ns()
    cpu, cuda = LargeYoloX(model, "cpu"), LargeYoloX(model, "cuda")
    setup = time.monotonic_ns() - start
    cv2.setNumThreads(4)
    network = cv2.dnn.readNetFromONNX(str(model))
    network.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
    network.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
    rows = []
    for index, (source, frame) in enumerate(RgbDataset(dataset).frames()):
        if index not in (0, 24, 48):
            continue
        rgb = np.frombuffer(frame.rgb, np.uint8).reshape(384, 640, 3)
        independent = np.empty((1, 3, 640, 640), np.float32)
        independent.fill(114)
        for channel in range(3):
            independent[0, channel, :384] = rgb[:, :, channel]
        actual, _ = preprocess(frame)
        equal_tensor = np.array_equal(independent, actual)
        begin = time.monotonic_ns()
        a = cpu.session.run(["output"], {"images": independent})[0]
        b = cuda.session.run(["output"], {"images": actual})[0]
        network.setInput(independent)
        c = network.forward()
        comparisons = {}
        for name, raw in (("cuda", b), ("opencv", c)):
            comparisons[name] = dict(
                equal=bool(np.allclose(a, raw, atol=1e-3, rtol=1e-4)),
                maximum_absolute_error=float(np.abs(a - raw).max()),
                detections=len(postprocess(raw)),
            )
        rows.append(
            dict(
                scene=source["scene"],
                rgb_sha256=source["rgb_sha256"],
                equal_tensor=bool(equal_tensor),
                comparisons=comparisons,
                cpu_detections=len(postprocess(a)),
                total_wall_ns=time.monotonic_ns() - begin,
            )
        )
    return dict(
        schema="m10-model-check-v6",
        status="PASS"
        if len(rows) == 3
        and all(
            r["equal_tensor"] and all(c["equal"] for c in r["comparisons"].values())
            for r in rows
        )
        else "FAIL",
        model_sha256=sha256_file(model),
        dataset_sha256=sha256_file(dataset),
        input_profile=INPUT_PROFILE,
        atol=1e-3,
        rtol=1e-4,
        initialization_wall_ns=setup,
        cuda_providers=cuda.session.get_providers(),
        cuda_options=cuda.session.get_provider_options(),
        cpu_node_fallback_disabled=True,
        cold_calls_excluded=0,
        rows=rows,
        scope="Specified tensor/raw numerical agreement on three preparation images; not accuracy/live20Hz",
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("dataset", type=Path)
    p.add_argument("model", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    result = check(a.dataset, a.model)
    write_new(a.output, result)
    print(result)
    raise SystemExit(0 if result["status"] == "PASS" else 1)

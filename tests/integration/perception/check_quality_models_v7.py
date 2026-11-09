"""Independent tensor, raw and complete native output check on fresh preparation."""

import argparse
from pathlib import Path
import sys
import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import RgbDataset
from physical_ai.perception.quality_candidates_v7 import (
    QualityCandidateV7,
    TRAINED_SHA256,
)
from physical_ai.perception.training_v1 import decode_six
from physical_ai.perception.yolox import preprocess, postprocess
from quality_benchmark import write_new


def compare(expected, actual):
    if len(expected) != len(actual) or [d.class_id for d in expected] != [
        d.class_id for d in actual
    ]:
        return dict(equal=False, box_error=None, score_error=None)
    box = max(
        (
            max(abs(x - y) for x, y in zip(a.box, b.box))
            for a, b in zip(expected, actual)
        ),
        default=0.0,
    )
    score = max((abs(a.score - b.score) for a, b in zip(expected, actual)), default=0.0)
    return dict(equal=box <= 0.01 and score <= 0.0001, box_error=box, score_error=score)


def check(dataset, trained, baseline):
    rows = []
    cv2.setNumThreads(4)
    for candidate, path, decode in (
        ("baseline", baseline, postprocess),
        ("trained-v1", trained, decode_six),
    ):
        cpu, cuda = (
            QualityCandidateV7(path, candidate, "cpu"),
            QualityCandidateV7(path, candidate, "cuda"),
        )
        network = cv2.dnn.readNetFromONNX(str(path))
        network.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        network.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        for index, (source, frame) in enumerate(RgbDataset(dataset).frames()):
            if index not in (0, 24, 48):
                continue
            rgb = np.frombuffer(frame.rgb, np.uint8).reshape(384, 640, 3)
            independent = np.full((1, 3, 640, 640), 114, np.float32)
            for channel in range(3):
                independent[0, channel, :384] = rgb[:, :, channel]
            tensor, _ = preprocess(frame)
            a = cpu.detector.session.run(["output"], {"images": independent})[0]
            b = cuda.detector.session.run(["output"], {"images": tensor})[0]
            network.setInput(independent)
            c = network.forward()
            reference = decode(a)
            comparisons = {}
            for name, raw in (("cuda", b), ("opencv", c)):
                comparisons[name] = dict(
                    raw_equal=bool(np.allclose(a, raw, atol=0.001, rtol=0.0001)),
                    raw_max_error=float(np.abs(a - raw).max()),
                    detections=compare(reference, decode(raw)),
                )
            # Exercise the complete frame wrapper, including image/timing/identity.
            ca, cb = cpu.infer(frame), cuda.infer(frame)
            complete = compare(ca.detections, cb.detections)
            passed = bool(
                np.array_equal(independent, tensor)
                and complete["equal"]
                and all(
                    x["raw_equal"] and x["detections"]["equal"]
                    for x in comparisons.values()
                )
                and ca.identity == cb.identity == frame.identity
                and ca.model_sha256 == cb.model_sha256
            )
            rows.append(
                dict(
                    candidate=candidate,
                    scene=source["scene"],
                    rgb_sha256=source["rgb_sha256"],
                    passed=passed,
                    complete=complete,
                    comparisons=comparisons,
                )
            )
    return dict(
        schema="m10-model-check-v7",
        status="PASS" if len(rows) == 6 and all(r["passed"] for r in rows) else "FAIL",
        model_sha256=TRAINED_SHA256,
        dataset_sha256=sha256_file(dataset),
        atol=0.001,
        rtol=0.0001,
        box_atol=0.01,
        score_atol=0.0001,
        cpu_node_fallback_disabled=True,
        cold_calls_excluded=0,
        rows=rows,
        scope="Three fixed fresh preparation frames per model; independent tensor/raw and complete native output; not quality/live20Hz",
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("dataset", "trained", "baseline", "output"):
        p.add_argument(name, type=Path)
    a = p.parse_args()
    r = check(a.dataset, a.trained, a.baseline)
    write_new(a.output, r)
    print(r)
    raise SystemExit(0 if r["status"] == "PASS" else 1)

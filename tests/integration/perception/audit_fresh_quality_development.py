"""Verify retained development outputs and reproduce the original failed decision."""

import argparse
from dataclasses import asdict
from pathlib import Path

import numpy as np

from fresh_quality_2k_review import BASE, ROOT, digest, read, write
from fresh_quality_2k_score import nomination
from physical_ai.perception.camera_resolution_v1 import canonical
from physical_ai.perception.model_screen_v2 import decode, nms
from physical_ai.perception.resolution_car_v1 import decode as decode_dfine


def check_detections(actual, stored):
    if len(actual) != len(stored) or any(
        a["class_id"] != b["class_id"]
        or a["score"] != b["score"]
        or list(a["box"]) != b["box"]
        for a, b in zip(actual, stored)
    ):
        raise ValueError("recorded and original detections differ")


def replay(run, decode_rows):
    rows = read(run / "predictions.json")["rows"]
    if len(rows) != 81:
        raise ValueError("incomplete development predictions")
    for index, row in enumerate(rows):
        file = run / "raw" / f"{index:03}.npz"
        if digest(file) != row["raw_sha256"]:
            raise ValueError("raw model tensor hash")
        with np.load(file, allow_pickle=False) as archive:
            decode_rows(index, row, dict(archive))
    return len(rows)


def audit():
    original = BASE / "runs/evaluation-development-01"
    result = nomination(original)
    if result != read(original / "comparison.json") or result["status"] != "FAIL":
        raise ValueError("original nomination verdict changed")
    checked = dict(original_candidate=81, original_baseline=81)
    registry = read(ROOT / "profiles/perception-model-screen-v2.json")["models"]
    for name in ("yolox-l", "rtdetrv2-r18", "rtv4-s", "damo-s"):

        def check_model(index, row, raw):
            det = decode(raw, registry[name]["family"], 0.35)
            check_detections([asdict(d) for d in det], row["detections"])

        checked[name] = replay(BASE / "development-model-screen-01" / name, check_model)
    full = read(original / "candidate/predictions.json")["rows"]

    def check_tiles(index, row, raw):
        detections = list(full[index]["detections"])
        for i, (x, y) in enumerate(((0, 0), (1024, 0), (0, 614), (1024, 614))):
            v = {k: raw[f"tile{i}_{k}"] for k in ("labels", "scores", "boxes")}
            v["boxes"] = np.clip(
                v["boxes"], [0, 0, 0, 0], [1536, 922, 1536, 922]
            ).astype(np.float32) + np.array([x, y, x, y], np.float32)
            detections.extend(asdict(d) for d in decode_dfine(canonical(v, 4)))
        keep = (
            nms(
                np.array([d["class_id"] for d in detections]),
                np.array([d["score"] for d in detections]),
                np.array([d["box"] for d in detections]),
                0.5,
            )
            if detections
            else []
        )
        check_detections([detections[i] for i in keep], row["detections"])

    checked["tiled"] = replay(BASE / "development-diagnosis-01", check_tiles)

    def check_masks(index, row, raw):
        masked, boxes = [], []
        categories = {1: 0, 2: 1, 3: 2, 4: 3, 6: 5, 8: 7}
        for i, (label, score, box) in enumerate(
            zip(raw["labels"], raw["scores"], raw["boxes"])
        ):
            if label not in categories or score < 0.35:
                continue
            values = dict(class_id=categories[label], score=float(score))
            boxes.append(dict(values, box=(box / 4).tolist()))
            packed = raw[f"mask_{i}"]
            if packed.dtype != np.uint8 or packed.shape != (1536, 320):
                raise ValueError("stored native mask dimensions")
            y, x = np.nonzero(np.unpackbits(packed, axis=1))
            if len(y):
                masked.append(
                    dict(
                        values,
                        box=[
                            x.min() / 4,
                            y.min() / 4,
                            (x.max() + 1) / 4,
                            (y.max() + 1) / 4,
                        ],
                    )
                )
        check_detections(masked, row["mask_detections"])
        check_detections(boxes, row["box_detections"])

    checked["mask_rcnn"] = replay(BASE / "development-mask-01", check_masks)
    return dict(
        status="PASS_OUTPUT_REPLAY",
        original_development_decision=result["status"],
        frames_by_pipeline=checked,
        comparison_sha256=digest(original / "comparison.json"),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    write(parser.parse_args().output, audit())

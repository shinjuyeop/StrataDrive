"""Compare the retained model with a fixed four-tile development-only image pass."""

import argparse
from dataclasses import asdict
import hashlib
from pathlib import Path
import time

import numpy as np
from PIL import Image

from fresh_quality_2k_review import BASE, ROOT, digest, read, rgb_bytes, write
from physical_ai.perception.camera_resolution_v1 import canonical, unpack
from physical_ai.perception.class_calibration_v1 import decode as decode_vector
from physical_ai.perception.model_screen_v2 import nms
from physical_ai.perception.resolution_car_v1 import decode as decode_fixed
from physical_ai.perception.resolution_v2 import ResolutionDetector
from run_resolution_v2 import quality


def tiled(detector, rgb, original, raw_path):
    # Four overlapping views cover the complete image. Each is 60% of its
    # original axes and uses the same model weights and RGB normalization.
    results = list(original)
    arrays = {}
    for i, (x, y) in enumerate(((0, 0), (1024, 0), (0, 614), (1024, 614))):
        width, height = 1536, 922
        crop = rgb.crop((x, y, x + width, y + height))
        resized = np.asarray(
            crop.resize((960, 960), Image.Resampling.BILINEAR), np.float32
        )
        feed = dict(
            images=np.ascontiguousarray(resized.transpose(2, 0, 1)[None] / 255.0),
            orig_target_sizes=np.array([[width, height]], np.int64),
        )
        raw = detector.raw(feed)
        arrays.update({f"tile{i}_{k}": value for k, value in raw.items()})
        global_boxes = raw["boxes"].copy()
        global_boxes = np.clip(
            global_boxes, [0, 0, 0, 0], [width, height, width, height]
        ).astype(np.float32)
        global_boxes += np.array([x, y, x, y], np.float32)
        results.extend(
            asdict(d) for d in decode_fixed(canonical(dict(raw, boxes=global_boxes), 4))
        )
    np.savez_compressed(raw_path, **arrays)
    if not results:
        return []
    indices = nms(
        np.array([d["class_id"] for d in results]),
        np.array([d["score"] for d in results]),
        np.array([d["box"] for d in results]),
        0.5,
    )
    if len(indices) > 100:
        raise ValueError("detection capacity")
    return [results[i] for i in indices]


def diagnose(out):
    run = BASE / "runs/evaluation-development-01"
    images = read(run / "images.json")
    predictions = read(run / "candidate/predictions.json")
    scenes = read(run / "benchmark.json")["scenes"]
    gt = read(run / "evaluation-only-gt.json")["frames"]
    if (
        images["partition"] != "development"
        or not len(images["frames"])
        == len(predictions["rows"])
        == len(scenes)
        == len(gt)
        == 81
    ):
        raise ValueError("complete original development inputs required")
    model = ROOT / "build/m10-resolution-v2/models/dfine-960.onnx"
    out.mkdir(exist_ok=False)
    (out / "raw").mkdir()
    write(
        out / "declaration.json",
        dict(
            source_sha256=digest(Path(__file__)),
            method="Four 1536 by 922 crops of each 2560 by 1536 RGB plus the original full-frame results. Same-class NMS IoU 0.5.",
            confidence="Published per-class thresholds; separately compare original full frame at the existing 0.35 floor",
            images_sha256=digest(run / "images.json"),
            input_predictions_sha256=digest(run / "candidate/predictions.json"),
            model_sha256=digest(model),
            attempts=81,
            use="Development diagnosis only",
        ),
    )
    detector = ResolutionDetector(
        960, model, ROOT / "build/m10-resolution-v2/models.json"
    )
    if detector.session.get_providers()[0] != "CUDAExecutionProvider":
        raise ValueError("CUDA inference provider required")
    rows, floors, trace = [], [], []
    for index, (frame, original, scene, truth) in enumerate(
        zip(images["frames"], predictions["rows"], scenes, gt)
    ):
        if (
            not original["valid"]
            or not frame["scene"]
            == original["scene"]
            == scene["scene"]
            == truth["scene"]
        ):
            raise ValueError("original prediction association")
        path = run / "candidate" / original["raw"]
        if original["raw_sha256"] != digest(path):
            raise ValueError("original detector tensor changed")
        with np.load(path, allow_pickle=False) as archive:
            raw = canonical(dict(archive), 4)
        at_floor = [asdict(d) for d in decode_vector(raw, (0.35,) * 6)]
        floors.append((scene, truth, at_floor, True, False, raw))
        pixels = rgb_bytes(unpack(run / "dataset", frame["rgb_raw"], 2560, 1536))
        if hashlib.sha256(pixels).hexdigest() != frame["rgb_sha256"]:
            raise ValueError("original RGB digest")
        raw_path = out / "raw" / f"{index:03}.npz"
        begin = time.monotonic_ns()
        detections = tiled(
            detector,
            Image.frombytes("RGB", (2560, 1536), pixels),
            original["detections"],
            raw_path,
        )
        rows.append((scene, truth, detections, True, False, None))
        trace.append(
            dict(
                scene=frame["scene"],
                rgb_sha256=frame["rgb_sha256"],
                raw=raw_path.name,
                raw_sha256=digest(raw_path),
                detections=detections,
                elapsed_ns=time.monotonic_ns() - begin,
            )
        )
    write(out / "predictions.json", dict(rows=trace))
    cards = {}
    for name, values in (("full_frame_at_floor", floors), ("full_plus_tiles", rows)):
        card = quality(values)
        cards[name] = {
            k: card[k]
            for k in (
                "micro",
                "per_class",
                "near_person",
                "gates",
                "absolute_quality",
                "strata",
                "sizes",
            )
        }
    write(out / "scores.json", cards)
    print({k: v["micro"] for k, v in cards.items()}, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    diagnose(parser.parse_args().output)

#!/usr/bin/env python3
"""Convert captured BGRA to RGB inputs and isolated visible-instance labels."""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import WIDTH, HEIGHT, sha256_file
from physical_ai.perception.dataset import read_json, local_path

SEMANTIC_TO_COCO = {12: 0, 19: 1, 14: 2, 18: 3, 16: 5, 15: 7}


def visible_boxes(raw):
    bgra = np.frombuffer(raw, np.uint8).reshape(HEIGHT, WIDTH, 4)
    semantic = bgra[:, :, 2]
    instance = bgra[:, :, 1].astype(np.uint16) + (bgra[:, :, 0].astype(np.uint16) << 8)
    included, excluded = [], []
    for tag, cls in SEMANTIC_TO_COCO.items():
        for ident in np.unique(instance[semantic == tag]):
            y, x = np.where((semantic == tag) & (instance == ident))
            box = [int(x.min()), int(y.min()), int(x.max()) + 1, int(y.max()) + 1]
            row = {
                "class_id": cls,
                "instance_id": int(ident),
                "visible_pixels": int(len(x)),
                "box": box,
            }
            if len(x) < 25 or box[2] - box[0] < 4 or box[3] - box[1] < 4:
                row["reason"] = "small_visible_support"
                excluded.append(row)
            else:
                included.append(row)
    return included, excluded


def prepare(capture_path, output, *, expected_frames=60):
    capture = read_json(capture_path)
    if (
        capture["status"] != "PASS"
        or len(capture["frames"]) != expected_frames
        or capture["cleanup_errors"]
        or capture["overflow"]
    ):
        raise ValueError("capture not complete")
    output.mkdir(parents=True, exist_ok=False)
    (output / "rgb").mkdir()
    camera = {
        "width": WIDTH,
        "height": HEIGHT,
        "camera_id": 1,
        "calibration_revision": 1,
        "format": "RGB8",
    }
    manifest = {
        "schema": "m10-rgb-dataset-v1",
        "split": "evaluation",
        "capture_sha256": sha256_file(capture_path),
        "camera": camera,
        "epoch": capture["epoch"],
        "clock_instance": capture["clock_instance"],
        "frames": [],
    }
    truth = {
        "schema": "m10-visible-instance-gt-v1",
        "capture_sha256": manifest["capture_sha256"],
        "annotation": "visible instance masks; not amodal COCO boxes; evaluation only",
        "frames": [],
    }
    for row in capture["frames"]:
        raw = {}
        for stream in ("rgb", "instance"):
            source = local_path(capture_path.parent, row[stream]["path"])
            raw[stream] = source.read_bytes()
            if (
                len(raw[stream]) != WIDTH * HEIGHT * 4
                or hashlib.sha256(raw[stream]).hexdigest() != row[stream]["sha256"]
            ):
                raise ValueError("capture layout/hash mismatch")
        pixels = np.frombuffer(raw["rgb"], np.uint8).reshape(HEIGHT, WIDTH, 4)
        rgb = np.ascontiguousarray(pixels[:, :, [2, 1, 0]]).tobytes()
        path = f"rgb/{row['frame']:08d}.rgb"
        (output / path).write_bytes(rgb)
        manifest["frames"].append(
            {
                "scene": row["scene"],
                "frame": row["frame"],
                "source_ns": row["source_ns"],
                "rgb_path": path,
                "rgb_sha256": hashlib.sha256(rgb).hexdigest(),
            }
        )
        boxes, excluded = visible_boxes(raw["instance"])
        truth["frames"].append(
            {
                "frame": row["frame"],
                "scene": row["scene"],
                "objects": boxes,
                "excluded": excluded,
            }
        )
    (output / "rgb.json").write_text(json.dumps(manifest, indent=2) + "\n")
    truth["rgb_manifest_sha256"] = sha256_file(output / "rgb.json")
    (output / "evaluation-only-gt.json").write_text(json.dumps(truth, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps({"frames": len(prepare(args.capture, args.output)["frames"])}))

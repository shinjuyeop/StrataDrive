"""Test a fixed, pretrained visible-mask detector on the consumed development set."""

import argparse
import hashlib
from pathlib import Path
import time

import numpy as np
import torch
import torchvision
from torchvision.models.detection import (
    MaskRCNN_ResNet50_FPN_V2_Weights,
    maskrcnn_resnet50_fpn_v2,
)

from fresh_quality_2k_review import BASE, ROOT, digest, read, rgb_bytes, write
from physical_ai.perception.camera_resolution_v1 import unpack
from run_resolution_v2 import quality

WEIGHT_SHA = "73cbd0190fcbe3ba339921fbce2c3a0b6bb9126c9a133c85e43a2a8e060a109e"
CATEGORIES = {1: 0, 2: 1, 3: 2, 4: 3, 6: 5, 8: 7}


def screen(weights, output):
    run = BASE / "runs/evaluation-development-01"
    frames, scenes, truth = (
        read(run / "images.json"),
        read(run / "benchmark.json")["scenes"],
        read(run / "evaluation-only-gt.json")["frames"],
    )
    if (
        frames["partition"] != "development"
        or not len(frames["frames"]) == len(scenes) == len(truth) == 81
        or digest(weights) != WEIGHT_SHA
    ):
        raise ValueError("original development input and official model required")
    output.mkdir(exist_ok=False)
    (output / "raw").mkdir()
    write(
        output / "declaration.json",
        dict(
            model="TorchVision Mask R-CNN ResNet50 FPN V2 COCO_V1",
            weights_sha256=WEIGHT_SHA,
            url=MaskRCNN_ResNet50_FPN_V2_Weights.COCO_V1.url,
            source_sha256=digest(Path(__file__)),
            input_sha256=digest(run / "images.json"),
            device=torch.cuda.get_device_name(),
            torch=torch.__version__,
            torchvision=torchvision.__version__,
            method="Original full RGB, default TorchVision resizing, float32, confidence >= 0.35, native pixel mask >= 0.5, half-open visible boxes; separately score original detector boxes. Development only.",
        ),
    )
    model = maskrcnn_resnet50_fpn_v2(weights=None, weights_backbone=None)
    model.load_state_dict(torch.load(weights, map_location="cpu", weights_only=True))
    model.eval().to("cuda")
    rows, mask_rows, box_rows = [], [], []
    with torch.inference_mode():
        for i, (frame, scene, gt) in enumerate(zip(frames["frames"], scenes, truth)):
            if not frame["scene"] == scene["scene"] == gt["scene"]:
                raise ValueError("development scene link")
            pixels = rgb_bytes(unpack(run / "dataset", frame["rgb_raw"], 2560, 1536))
            if hashlib.sha256(pixels).hexdigest() != frame["rgb_sha256"]:
                raise ValueError("original RGB digest")
            tensor = (
                torch.from_numpy(
                    np.frombuffer(pixels, np.uint8).copy().reshape(1536, 2560, 3)
                )
                .permute(2, 0, 1)
                .to("cuda", dtype=torch.float32)
                / 255
            )
            begin = time.monotonic_ns()
            (result,) = model([tensor])
            masks, boxes, packed = [], [], {}
            scores = result["scores"].cpu().numpy()
            labels = result["labels"].cpu().numpy()
            coordinates = result["boxes"].cpu().numpy()
            for n, (label, score, box) in enumerate(zip(labels, scores, coordinates)):
                if label not in CATEGORIES or score < 0.35:
                    continue
                common = dict(class_id=CATEGORIES[label], score=float(score))
                boxes.append(dict(common, box=(box / 4).tolist()))
                mask = (result["masks"][n, 0] >= 0.5).cpu().numpy()
                packed[f"mask_{n}"] = np.packbits(mask, axis=1)
                y, x = np.nonzero(mask)
                if len(y):
                    masks.append(
                        dict(
                            common,
                            box=[
                                x.min() / 4,
                                y.min() / 4,
                                (x.max() + 1) / 4,
                                (y.max() + 1) / 4,
                            ],
                        )
                    )
            elapsed = time.monotonic_ns() - begin
            path = output / "raw" / f"{i:03}.npz"
            np.savez_compressed(
                path, scores=scores, labels=labels, boxes=coordinates, **packed
            )
            rows.append(
                dict(
                    scene=frame["scene"],
                    rgb_sha256=frame["rgb_sha256"],
                    raw_sha256=digest(path),
                    elapsed_ns=elapsed,
                    mask_detections=masks,
                    box_detections=boxes,
                )
            )
            mask_rows.append((scene, gt, masks, True, False, None))
            box_rows.append((scene, gt, boxes, True, False, None))
    write(output / "predictions.json", dict(rows=rows))
    cards = {}
    for name, observations in (
        ("visible_masks", mask_rows),
        ("detector_boxes", box_rows),
    ):
        card = quality(observations)
        cards[name] = {
            k: card[k]
            for k in (
                "micro",
                "per_class",
                "near_person",
                "strata",
                "gates",
                "absolute_quality",
            )
        }
    write(output / "scores.json", cards)
    print({k: v["micro"] for k, v in cards.items()}, flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("weights", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    screen(a.weights, a.output)

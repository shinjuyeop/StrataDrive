#!/usr/bin/env python3
"""Render fixed GT-only preparation panels; never loads model predictions."""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.dataset import read_json, RgbDataset
from physical_ai.perception.contract import CLASSES, sha256_file
from quality_benchmark import write_new
from physical_ai.perception.yolox import image_health


def review(data, output, part):
    dataset = RgbDataset(data / "rgb.json")
    truth = read_json(data / "evaluation-only-gt.json")["frames"]
    meta = read_json(data / "benchmark.json")
    images = []
    health = []
    for _, frame in dataset.frames():
        health.append(image_health(frame))
        images.append(np.frombuffer(frame.rgb, np.uint8).reshape(384, 640, 3))

    def panel(index):
        x, y, w, h = 230, 100, 200, 150
        image = cv2.resize(
            cv2.cvtColor(images[index][y : y + h, x : x + w], cv2.COLOR_RGB2BGR),
            (400, 300),
            interpolation=cv2.INTER_NEAREST,
        )
        for field in ("objects", "excluded"):
            for g in truth[index][field]:
                a, b, c, d = g["box"]
                a, c = (a - x) * 2, (c - x) * 2
                b, d = (b - y) * 2, (d - y) * 2
                color = (
                    (160, 160, 160)
                    if field == "excluded"
                    else (255, 80, 255)
                    if 13 in g["semantic_tags"]
                    else (255, 255, 0)
                )
                cv2.rectangle(image, (a, b), (c, d), color, 1)
                text = (
                    CLASSES[g["class_id"]]
                    + (" rider" if 13 in g["semantic_tags"] else "")
                    + f" {g['visible_pixels']}px"
                )
                cv2.putText(
                    image,
                    text,
                    (max(1, a), max(12, min(295, b - 5))),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.33,
                    color,
                    1,
                    cv2.LINE_AA,
                )
        head = np.zeros((38, 400, 3), np.uint8)
        cv2.putText(
            head,
            truth[index]["scene"] + " " + meta["scenes"][index]["stratum"],
            (4, 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.33,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        return np.concatenate([head, image])

    for label, offsets in (("near-occluded", (0, 3)), ("medium-far", (1, 2))):
        panels = [panel(c * 4 + off) for c in range(6) for off in offsets]
        canvas = np.concatenate(
            [np.concatenate(panels[i : i + 4], axis=1) for i in range(0, 12, 4)]
        )
        cv2.imwrite(str(output / f"{part}-{label}.png"), canvas)
    result = dict(
        schema="m10-quality-annotation-panels-v8",
        created_utc=datetime.now(timezone.utc).isoformat(),
        partition=part,
        site=meta["site"],
        frames=len(images),
        rgb_manifest_sha256=sha256_file(data / "rgb.json"),
        truth_sha256=sha256_file(data / "evaluation-only-gt.json"),
        all_rgb_health="PASS",
        min_luma_std=min(h["luma_std"] for h in health),
        scope="Fixed24 ClearNoon panels; all81 RGB health checks; visual review recorded separately",
    )
    write_new(output / f"{part}-panels.json", result)
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("data", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("partition")
    a = p.parse_args()
    print(review(a.data, a.output, a.partition))

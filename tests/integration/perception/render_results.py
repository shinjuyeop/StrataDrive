#!/usr/bin/env python3
"""Render evaluation overlays after inference. These images never feed the model."""

import argparse
import json
from pathlib import Path
import sys
import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.dataset import RgbDataset, read_json
from physical_ai.perception.contract import CLASSES
from evaluate import evaluate


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--truth", type=Path, required=True)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    evaluate(a.dataset, a.truth, a.run)
    if a.output.exists():
        raise FileExistsError(a.output)
    truth = read_json(a.truth)["frames"]
    rows = [
        json.loads(line)
        for line in (a.run / "predictions.jsonl").read_text().splitlines()
    ]
    seen = set()
    panels = []
    for (source, camera), gt, prediction in zip(
        RgbDataset(a.dataset).frames(), truth, rows
    ):
        if source["scene"] in seen:
            continue
        seen.add(source["scene"])
        rgb = np.frombuffer(camera.rgb, np.uint8).reshape(384, 640, 3)
        panel = np.zeros((460, 640, 3), np.uint8)
        panel[76:] = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        state = "admitted" if prediction["admitted"] else "unavailable/late"
        cv2.putText(
            panel,
            f"{source['scene']} | frame {source['frame']} | {state}",
            (12, 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
        )
        cv2.putText(
            panel,
            "GREEN: raw model | CYAN: visible GT (evaluation only)",
            (12, 45),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.47,
            (220, 220, 220),
            1,
        )
        cv2.putText(
            panel,
            "Diagnostic fixture: full ODD image quality not accepted",
            (12, 65),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.46,
            (80, 180, 255),
            1,
        )
        for target in gt["objects"]:
            x1, y1, x2, y2 = map(int, target["box"])
            cv2.rectangle(panel, (x1, y1 + 76), (x2 - 1, y2 + 75), (255, 255, 0), 1)
        for detection in prediction["detections"] or []:
            x1, y1, x2, y2 = map(round, detection["box"])
            cv2.rectangle(panel, (x1, y1 + 76), (x2, y2 + 76), (0, 255, 0), 1)
            label = f"{CLASSES[detection['class_id']]} {detection['score']:.2f}"
            cv2.putText(
                panel,
                label,
                (max(0, x1), max(90, y1 + 72)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.42,
                (0, 255, 0),
                1,
            )
        panels.append(panel)
    if not panels or not cv2.imwrite(str(a.output), np.concatenate(panels, axis=1)):
        raise ValueError("image write failed")


if __name__ == "__main__":
    main()

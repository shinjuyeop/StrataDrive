import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from evaluate import counts, overlap
from prepare_dataset import visible_boxes
from physical_ai.perception.contract import HEIGHT, WIDTH
from physical_ai.perception.dataset import RgbDataset, read_json


class EvaluationTests(unittest.TestCase):
    def test_one_to_one_and_class_aware_counts(self):
        truth = [{"class_id": 2, "box": [0, 0, 10, 10]}]
        detections = [
            {"class_id": 2, "box": [0, 0, 10, 10], "score": 0.9},
            {"class_id": 2, "box": [0, 0, 10, 10], "score": 0.8},
            {"class_id": 0, "box": [0, 0, 10, 10], "score": 0.9},
        ]
        self.assertEqual(counts(detections, truth)["2"], {"tp": 1, "fp": 1, "fn": 0})
        self.assertEqual(counts(detections, truth)["0"], {"tp": 0, "fp": 1, "fn": 0})
        self.assertEqual(counts([], truth)["2"], {"tp": 0, "fp": 0, "fn": 1})
        self.assertEqual(overlap([0, 0, 1, 1], [1, 0, 2, 1]), 0)

    def test_visible_instance_ids_semantic_mapping_and_small_exclusions(self):
        image = np.zeros((HEIGHT, WIDTH, 4), np.uint8)
        image[10:20, 30:40] = [1, 2, 14, 255]
        image[30:32, 10:12] = [0, 7, 12, 255]
        image[30:40, 50:60] = [2, 2, 14, 255]
        boxes, small = visible_boxes(image.tobytes())
        self.assertEqual(len(boxes), 2)
        self.assertEqual(len(small), 1)
        self.assertEqual(boxes[0]["instance_id"], 258)
        self.assertEqual(boxes[0]["box"], [30, 10, 40, 20])
        self.assertEqual(small[0]["class_id"], 0)

    def test_rgb_manifest_rejects_gt_duplicate_future_schema_and_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = bytes(WIDTH * HEIGHT * 3)
            (root / "input.rgb").write_bytes(raw)
            baseline = {
                "schema": "m10-rgb-dataset-v1",
                "split": "evaluation",
                "capture_sha256": "0" * 64,
                "camera": {
                    "width": 640,
                    "height": 384,
                    "camera_id": 1,
                    "calibration_revision": 1,
                    "format": "RGB8",
                },
                "epoch": 1,
                "clock_instance": 7,
                "frames": [
                    {
                        "frame": 1,
                        "source_ns": 0,
                        "scene": "fixture",
                        "rgb_path": "input.rgb",
                        "rgb_sha256": hashlib.sha256(raw).hexdigest(),
                    }
                ],
            }
            path = root / "rgb.json"
            path.write_text(json.dumps(baseline))
            self.assertEqual(len(list(RgbDataset(path).frames())), 1)
            mutations = []
            changed = copy.deepcopy(baseline)
            changed["ground_truth"] = []
            mutations.append(changed)
            changed = copy.deepcopy(baseline)
            changed["frames"] *= 2
            mutations.append(changed)
            changed = copy.deepcopy(baseline)
            changed["frames"][0]["rgb_path"] = "../outside"
            mutations.append(changed)
            changed = copy.deepcopy(baseline)
            changed["frames"][0]["rgb_sha256"] = "0" * 64
            mutations.append(changed)
            changed = copy.deepcopy(baseline)
            changed["camera"]["format"] = "BGRA8"
            mutations.append(changed)
            for changed in mutations:
                path.write_text(json.dumps(changed))
                with self.assertRaises(ValueError):
                    list(RgbDataset(path).frames())
            for text in ('{"x":1,"x":2}', '{"x":NaN}'):
                path.write_text(text)
                with self.assertRaises(ValueError):
                    read_json(path)

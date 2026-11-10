"""Screen decoder, native preprocessing and holdout separation regressions."""

import json
from pathlib import Path
import tempfile
import unittest
import numpy as np

from physical_ai.perception.model_screen_v1 import (
    decode_rtdetr,
    decode_nanodet,
    prepare_rgb,
)
from run_model_screen_v1 import validate_development
from check_model_screen_v1 import compare_top300


class ModelScreenTests(unittest.TestCase):
    def raw_rt(self):
        return dict(
            labels=np.zeros((1, 300), np.int64),
            scores=np.zeros((1, 300), np.float32),
            boxes=np.tile(np.array([[[10, 20, 30, 40]]], np.float32), (1, 300, 1)),
        )

    def test_rtdetr_native_mapping_clip_and_no_nms(self):
        raw = self.raw_rt()
        raw["labels"][0, :3] = [7, 7, 4]
        raw["scores"][0, :3] = [0.9, 0.8, 0.99]
        raw["boxes"][0, :2] = [-1, 20, 700, 500]
        out = decode_rtdetr(raw)
        self.assertEqual([d.class_id for d in out], [7, 7])
        self.assertEqual(out[0].box, (0.0, 20.0, 640.0, 384.0))

    def test_bad_low_score_coordinates_are_not_hidden(self):
        for value in (float("nan"), float("inf")):
            raw = self.raw_rt()
            raw["boxes"][0, -1, 0] = value
            with self.assertRaises(ValueError):
                decode_rtdetr(raw)
        raw = self.raw_rt()
        raw["labels"][0, -1] = 80
        with self.assertRaises(ValueError):
            decode_rtdetr(raw)

    def test_capacity_and_empty_are_distinct(self):
        raw = self.raw_rt()
        self.assertEqual(decode_rtdetr(raw), ())
        raw["scores"][0, :101] = 0.9
        with self.assertRaisesRegex(ValueError, "capacity"):
            decode_rtdetr(raw)

    def test_topk_permutation_is_not_a_changed_detection(self):
        a = self.raw_rt()
        a["labels"][0, :2] = [26, 9]
        b = {k: v.copy() for k, v in a.items()}
        for k in b:
            b[k][:, [0, 1]] = b[k][:, [1, 0]]
        self.assertTrue(compare_top300(a, b)["all300_matched"])
        b["labels"][0, 1] = 10
        with self.assertRaisesRegex(ValueError, "set mismatch"):
            compare_top300(a, b)

    def nano(self):
        return {
            name: np.zeros((1, side * side, width), np.float32)
            for cls, box, side in [
                ("792", "795", 52),
                ("814", "817", 26),
                ("836", "839", 13),
            ]
            for name, width in [(cls, 80), (box, 32)]
        }

    def test_nanodet_class_agnostic_nms_before_target_filter(self):
        raw = self.nano()
        # Identical-height neighboring boxes: an out-of-scope aeroplane suppresses
        # a lower-score person, matching the official model's global NMS policy.
        index = 20 * 52 + 20
        raw["792"][0, index, 4] = 0.95
        raw["792"][0, index + 1, 0] = 0.9
        self.assertEqual(decode_nanodet(raw), ())
        raw["792"][0, index, 4] = 0
        out = decode_nanodet(raw)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].class_id, 0)
        self.assertGreater(out[0].box[1], 0)

    def test_nanodet_nonfinite_and_preprocess(self):
        raw = self.nano()
        raw["839"][0, -1, -1] = float("nan")
        with self.assertRaises(ValueError):
            decode_nanodet(raw)
        image = np.zeros((384, 640, 3), np.uint8)
        image[:, :, 0] = 255
        feed = prepare_rgb(image, "rtdetr")
        self.assertEqual(feed["images"].shape, (1, 3, 640, 640))
        self.assertEqual(feed["orig_target_sizes"].tolist(), [[640, 384]])
        self.assertEqual(feed["images"][0, :, 100, 100].tolist(), [1.0, 0.0, 0.0])
        self.assertEqual(
            prepare_rgb(image, "nanodet")["input.1"].shape, (1, 3, 416, 416)
        )

    def test_holdout_is_refused_before_scoring(self):
        # Reject a holdout even when stored in a misleadingly named directory.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            for name in (
                "benchmark.json",
                "evaluation-only-gt.json",
                "benchmark-seal.json",
            ):
                (path / name).write_text(json.dumps(dict(partition="holdout")))
            from unittest.mock import patch

            with patch("run_model_screen_v1.RgbDataset"):
                with self.assertRaisesRegex(ValueError, "refuses holdout"):
                    validate_development(path)


if __name__ == "__main__":
    unittest.main()

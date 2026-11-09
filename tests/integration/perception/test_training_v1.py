from pathlib import Path
from types import SimpleNamespace
import json
import hashlib
import tempfile
import unittest
import numpy as np
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.training_v1 import (
    pack_sample,
    decode_six,
    check_freeze,
    ROOT,
)
from physical_ai.perception.yolox import postprocess
from train_domain_v1 import score_records
from physical_ai.perception.trained_model_v1 import TrainedOnnxV1


class TrainingV1Tests(unittest.TestCase):
    def test_model_manifest_rejects_old_contract_and_tampered_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "model.onnx").write_bytes(b"fixture")
            manifest = dict(
                schema="m10-trained-model-v1",
                architecture="YOLOX-L-six-class",
                head_to_native=[0, 1, 2, 3, 5, 7],
                input=[1, 3, 640, 640],
                output=[1, 8400, 85],
                input_profile="rgb-unscaled-letterbox640-v1",
                runtime_promotion=False,
                model_bytes=7,
                model_sha256=hashlib.sha256(b"fixture").hexdigest(),
            )
            path = root / "manifest.json"
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "identity/contract"):
                TrainedOnnxV1(root / "model.onnx", path)
            manifest["output"] = [1, 8400, 11]
            manifest["model_sha256"] = "0" * 64
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "identity/contract"):
                TrainedOnnxV1(root / "model.onnx", path)

    def test_exact_rgb_padding_and_one_pixel_positive_flip(self):
        rgb = np.zeros((384, 640, 3), np.uint8)
        rgb[383, 639] = [10, 20, 30]
        labels = [dict(native_class=7, box=(639, 383, 1, 1), quality_eligible=False)]
        image, target = pack_sample(rgb, labels, True)
        self.assertEqual(image[:, 383, 0].tolist(), [10, 20, 30])
        self.assertTrue((image[:, 384:] == 114).all())
        self.assertEqual(target[0].tolist(), [5, 0.5, 383.5, 1, 1])
        self.assertEqual(np.count_nonzero(target[1:]), 0)

    def test_empty_frames_and_reject_truncation_or_invalid_labels(self):
        rgb = np.zeros((384, 640, 3), np.uint8)
        self.assertFalse(pack_sample(rgb, [])[1].any())
        for label in (
            dict(native_class=4, box=(0, 0, 1, 1)),
            dict(native_class=0, box=(639, 0, 2, 1)),
            dict(native_class=0, box=(0, 0, float("nan"), 1)),
        ):
            with self.assertRaises(ValueError):
                pack_sample(rgb, [label])
        with self.assertRaises(ValueError):
            pack_sample(rgb, [dict(native_class=0, box=(1, 1, 1, 1))] * 101)

    def test_native_mapping_and_classwise_nms(self):
        raw = np.zeros((1, 8400, 11), np.float32)
        raw[0, 0, :5] = [20, 20, 0, 0, 0.9]
        raw[0, 0, 10] = 0.9  # six-head5 -> native7 truck
        found = decode_six(raw)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].class_id, 7)
        self.assertEqual(found[0].box, (156.0, 156.0, 164.0, 164.0))
        with self.assertRaises(ValueError):
            postprocess(raw)

    def test_raw_invalid_confidence_overflow_and_old_output_rejected(self):
        with self.assertRaises(ValueError):
            decode_six(np.zeros((1, 8400, 85), np.float32))
        for channel, value in ((0, float("nan")), (4, 1.1), (2, 1000)):
            raw = np.zeros((1, 8400, 11), np.float32)
            raw[0, 0, channel] = value
            with self.assertRaises(ValueError):
                decode_six(raw)

    def test_independent_matching_duplicate_fp_and_tiny_truth(self):
        data = SimpleNamespace(
            images={1: dict(id=1, rgb_sha256="a")},
            targets={
                1: [
                    dict(category_id=1, bbox=[10, 10, 1, 1]),
                    dict(category_id=8, bbox=[30, 30, 10, 10]),
                ]
            },
        )
        records = [
            dict(
                image_id=1,
                rgb_sha256="a",
                detections=[
                    dict(class_id=0, score=0.9, box=[10, 10, 11, 11]),
                    dict(class_id=0, score=0.8, box=[10, 10, 11, 11]),
                    dict(class_id=5, score=0.7, box=[30, 30, 40, 40]),
                ],
            )
        ]
        score = score_records(data, records)
        self.assertEqual((score["tp"], score["fp"], score["fn"]), (1, 2, 1))
        self.assertAlmostEqual(score["macro_f1"], (2 / 3) / 6)
        self.assertEqual(score["objects"], 2)

    def test_score_requires_all_rgb_and_valid_predictions(self):
        data = SimpleNamespace(images={1: dict(id=1, rgb_sha256="a")}, targets={1: []})
        for records in (
            [],
            [dict(image_id=1, rgb_sha256="wrong", detections=[])],
            [
                dict(
                    image_id=1,
                    rgb_sha256="a",
                    detections=[dict(class_id=0, score=float("nan"), box=[0, 0, 1, 1])],
                )
            ],
        ):
            with self.assertRaises(ValueError):
                score_records(data, records)

    def test_prelaunch_source_drift_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as directory:
            source = Path(directory) / "source.py"
            source.write_text("before\n")
            freeze = Path(directory) / "freeze.json"
            freeze.write_text(
                json.dumps(
                    dict(sources={str(source.relative_to(ROOT)): sha256_file(source)})
                )
            )
            check_freeze(freeze)
            source.write_text("after\n")
            with self.assertRaisesRegex(ValueError, "source drift"):
                check_freeze(freeze)

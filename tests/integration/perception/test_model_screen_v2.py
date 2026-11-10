"""Calibration boundaries, native semantics and fail-closed separation regressions."""

from dataclasses import asdict
import unittest
from unittest.mock import patch
import numpy as np

from physical_ai.perception.contract import Detection
from physical_ai.perception.model_screen_v2 import ScreenDetection, decode, nms
from physical_ai.perception.model_screen_v2 import ScreenDetector
from physical_ai.perception.model_screen_v1 import decode_rtdetr
from run_model_screen_v2 import selection_key, validate_run


class ModelScreenV2Tests(unittest.TestCase):
    def test_damo_image_input_preserves_native_pil_rgb(self):
        # Native demo's still-image path is RGB; video path differs upstream.
        # An asymmetric color fixture catches a self-consistent RGB/BGR mistake.
        from types import SimpleNamespace
        from physical_ai.perception.contract import HEIGHT, WIDTH
        from physical_ai.perception.contract import CameraFrame, FrameIdentity

        rgb = np.zeros((HEIGHT, WIDTH, 3), np.uint8)
        rgb[: HEIGHT // 2, :, 0] = 255
        frame = CameraFrame(FrameIdentity(1, 7, 1, 50_000_000), rgb.tobytes())
        backend = SimpleNamespace(spec={"family": "damo"})
        output = ScreenDetector.prepare(backend, frame)["images"]
        self.assertEqual(output[0, :, 100, 100].tolist(), [255.0, 0.0, 0.0])

    def detr(self):
        return dict(
            labels=np.zeros((1, 300), np.int64),
            scores=np.zeros((1, 300), np.float32),
            boxes=np.tile(np.array([[[10, 20, 30, 40]]], np.float32), (1, 300, 1)),
        )

    def test_lower_threshold_is_offline_only(self):
        raw = self.detr()
        raw["scores"][0, 0] = 0.2
        result = decode(raw, "rtdetr", 0.1)
        self.assertIsInstance(result[0], ScreenDetection)
        with self.assertRaises(ValueError):
            Detection(result[0].class_id, result[0].score, result[0].box).validate()
        self.assertEqual(decode(raw, "rtdetr", 0.35), ())

    def test_common_threshold_matches_frozen_decoder(self):
        raw = self.detr()
        raw["labels"][0, :3] = [7, 3, 4]
        raw["scores"][0, :3] = [0.9, 0.8, 0.99]
        self.assertEqual(
            [asdict(d) for d in decode(raw, "rtdetr", 0.35)],
            [asdict(d) for d in decode_rtdetr(raw)],
        )

    def test_nonfinite_low_score_and_inverted_box_are_errors(self):
        for field, value in (("boxes", np.nan), ("scores", np.inf)):
            raw = self.detr()
            raw[field].flat[-1] = value
            with self.assertRaises(ValueError):
                decode(raw, "rtdetr", 0.7)
        raw = self.detr()
        raw["boxes"][0, -1] = [10, 10, 1, 1]
        with self.assertRaises(ValueError):
            decode(raw, "rtdetr", 0.7)

    def test_capacity_and_undeclared_threshold_fail(self):
        raw = self.detr()
        raw["scores"][0, :101] = 0.2
        with self.assertRaisesRegex(ValueError, "capacity"):
            decode(raw, "rtdetr", 0.1)
        with self.assertRaisesRegex(ValueError, "undeclared"):
            decode(raw, "rtdetr", 0.25)

    def test_damo_is_multilabel_class_nms_and_native_scaling(self):
        raw = dict(
            scores=np.zeros((1, 8400, 80), np.float32),
            boxes=np.tile(np.array([[[10, 20, 30, 40]]], np.float32), (1, 8400, 1)),
        )
        raw["scores"][0, 0, [0, 1, 4]] = [0.9, 0.8, 0.99]
        raw["scores"][0, 1, 0] = 0.7
        result = decode(raw, "damo", 0.35)
        self.assertEqual([d.class_id for d in result], [0, 1])
        self.assertEqual(result[0].box, (10.0, 12.0, 30.0, 24.0))

    def test_nms_precedes_clipping_and_is_continuous(self):
        keep = nms(
            np.array([0, 0, 1]),
            np.array([0.9, 0.8, 0.7]),
            np.array([[0, 0, 1, 1], [0.9, 0, 1.9, 1], [0, 0, 1, 1]]),
            0.5,
        )
        self.assertEqual(keep.tolist(), [0, 1, 2])

    def test_selection_order_is_predeclared(self):
        a = dict(
            absolute_development_gates="FAIL",
            macro_f1=0.99,
            minimum_class_recall=0.9,
            micro=dict(f1=0.99),
            threshold=0.1,
        )
        b = {**a, "absolute_development_gates": "PASS", "macro_f1": 0.8}
        self.assertGreater(selection_key(b), selection_key(a))
        self.assertGreater(selection_key({**b, "threshold": 0.7}), selection_key(b))

    def test_run_group_cannot_be_relabelled(self):
        report = dict(
            schema="m10-pretrained-screen-run-v2",
            group="holdout",
            candidate="yolox-s",
            freeze_sha256="digest",
            model_sha256="model",
        )
        with patch("run_model_screen_v2.read_json", return_value=report):
            with self.assertRaisesRegex(ValueError, "provenance"):
                validate_run({}, "freeze", "run", "check")


if __name__ == "__main__":
    unittest.main()

import unittest
from types import SimpleNamespace

import numpy as np
from PIL import Image

from vehicle_class import GRIDS, STRIDES, recognition


class VehicleClassEvidenceTest(unittest.TestCase):
    def test_two_decoder_heads_and_independent_yolo_anchor_use_the_same_box(self):
        box = np.array([16, 16, 624, 368], float)
        outputs = {}
        for prefix, cls, score in (("original_", 2, 0.82), ("", 7, 0.91)):
            outputs[prefix + "boxes"] = box.reshape(1, 1, 4)
            outputs[prefix + "labels"] = np.array([[cls]])
            outputs[prefix + "scores"] = np.array([[score]])

        def dfine(names, feed):
            self.assertEqual(feed["images"].shape, (1, 3, 960, 960))
            return [outputs[name] for name in names]

        detector = SimpleNamespace(
            session=SimpleNamespace(run=dfine), spec={"outputs": list(outputs)}
        )

        def yolo(names, feed):
            self.assertEqual(feed["images"].shape, (1, 3, 640, 640))
            raw = np.zeros((1, len(GRIDS), 85), dtype=np.float32)
            anchor = 100
            raw[0, anchor, :2] = (box[:2] + box[2:]) / (2 * STRIDES[anchor]) - GRIDS[
                anchor
            ]
            raw[0, anchor, 2:4] = np.log((box[2:] - box[:2]) / STRIDES[anchor])
            raw[0, anchor, 4] = 0.9
            raw[0, anchor, 7] = 0.8
            return [raw]

        values = recognition(
            Image.new("RGB", (640, 384)),
            box,
            detector,
            SimpleNamespace(session=SimpleNamespace(run=yolo)),
        )
        self.assertEqual(len(values), 36)
        np.testing.assert_allclose(values[:4], 0.82)
        np.testing.assert_allclose(values[16:20], 0.91)
        np.testing.assert_allclose(values[24:28], 0.72, rtol=1e-5)

"""The one car revision changes only the declared class threshold."""

import unittest
import numpy as np
from physical_ai.perception.resolution_v2 import decode as previous
from physical_ai.perception.resolution_car_v1 import decode, VECTOR


class ResolutionCarV1Tests(unittest.TestCase):
    def test_car_below_previous_threshold_is_the_only_new_detection(self):
        raw = dict(
            labels=np.full((1, 300), 79, np.int64),
            scores=np.zeros((1, 300), np.float32),
            boxes=np.tile(np.array([[[10, 10, 30, 30]]], np.float32), (1, 300, 1)),
        )
        raw["labels"][0, :3] = [0, 1, 2]
        raw["scores"][0, :3] = [0.55, 0.45, 0.65]
        self.assertEqual([d.class_id for d in previous(raw)], [1])
        self.assertEqual([d.class_id for d in decode(raw)], [2, 1])
        self.assertEqual(VECTOR, (0.6, 0.4, 0.6, 0.5, 0.5, 0.6))

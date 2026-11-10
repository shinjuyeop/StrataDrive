"""Validated subset preserves complete quality and nonregression behavior."""

from copy import deepcopy
import unittest
import numpy as np
from physical_ai.perception.resolution_v2 import SIZES, prepare_rgb
from test_resolution_v1 import fixture
from run_resolution_v2 import quality, nonregression


class ResolutionV2Tests(unittest.TestCase):
    def test_numerically_failed1280_is_not_a_quality_candidate(self):
        self.assertEqual(SIZES, (640, 960))
        with self.assertRaises(ValueError):
            prepare_rgb(np.zeros((384, 640, 3), np.uint8), 1280)

    def test_missing_rider_and_class_regression_cannot_hide_in_micro_score(self):
        scenes, truths, _ = fixture()
        rows = [
            (
                s,
                g,
                [
                    dict(class_id=o["class_id"], score=0.9, box=o["box"])
                    for o in g["objects"]
                ],
                True,
                True,
                None,
            )
            for s, g in zip(scenes, truths)
        ]
        complete = quality(rows)
        self.assertEqual(complete["absolute_quality"], "PASS")
        altered = deepcopy(complete)
        altered["per_class"]["7"]["recall"] = 0.99
        self.assertEqual(nonregression(complete, altered)["status"], "FAIL")
        rows = deepcopy(rows)
        for _, gt, _, _, _, _ in rows:
            gt["objects"][:] = [
                o for o in gt["objects"] if 13 not in o["semantic_tags"]
            ]
        self.assertFalse(quality(rows)["gates"]["all_riders_visible"])

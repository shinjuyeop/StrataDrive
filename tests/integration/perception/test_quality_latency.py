"""Regression checks for accelerated inference arithmetic and crop preprocessing."""

import unittest

import numpy as np
from PIL import Image
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier

from multiview_detector import appearance, candidate_boxes, describe
from quality_features import PackedClassifier, appearances, boxes_for, geometry
from quality_latency_cuda import coefficients


class LatencyTests(unittest.TestCase):
    def test_crop_taps_match_pillow(self):
        rng = np.random.default_rng(9)
        for width, output in (
            (1, 960),
            (960, 960),
            (731, 960),
            (2560, 960),
            (2560, 640),
            (1536, 384),
        ):
            image = rng.integers(0, 256, (1, width), dtype=np.uint8)
            axis = coefficients(width, output)
            offsets = (axis[:, :1] + np.arange(8)).clip(0, width - 1)
            vals = (
                (image[0, offsets].astype(np.int64) * axis[:, 1:]).sum(axis=1)
                + (1 << 21)
            ) >> 22
            ref = np.asarray(
                Image.fromarray(image).resize((output, 1), Image.Resampling.BILINEAR)
            )[0]
            np.testing.assert_array_equal(ref, vals)

    def test_descriptors_and_geometry_preserve_classifier_inputs(self):
        image = np.random.default_rng(41).integers(
            0, 256, (384, 640, 3), dtype=np.uint8
        )
        boxes = np.array(
            [[50, 45, 109, 162], [201, 111, 344, 155], [50, 45, 109, 162]], float
        )
        parents = [dict(class_id=0, score=0.8, box=boxes[0].tolist())]
        obs = np.array(
            [
                [0, 0, 0, 0.7, *boxes[0]],
                [0, 1, 0, 0.8, *boxes[0]],
                [1, 0, 7, 0.6, *boxes[1]],
            ]
        )
        base = np.array([[0, 0.8, *boxes[0]]])
        actual = np.hstack((geometry(boxes, obs, base), appearances(image, boxes)))
        expected = np.array(
            [describe(image, 0, box, obs, parents) for box in boxes], np.float32
        )
        np.testing.assert_array_equal(actual, expected)
        np.testing.assert_array_equal(
            appearances(image, boxes),
            np.array([appearance(image, b) for b in boxes], np.float32),
        )

    def test_stable_proposal_order(self):
        obs = [
            [0, 0, 0, 0.8, 30, 50, 50, 110],
            [1, 0, 0, 0.8, 31, 50, 51, 110],
            [2, 0, 7, 0.6, 60, 11, 144, 85],
        ]
        base = [dict(class_id=0, score=0.8, box=[29, 50, 50, 110])]
        shapes = {k: np.array([[0, 0, 1, 1]]) for k in ("1-1", "3-3", "1-0", "3-0")}
        for c in (0, 1, 3, 7):
            ref = np.asarray(candidate_boxes(c, obs, base, shapes)).reshape(-1, 4)
            out = boxes_for(
                c, np.array(obs), np.array([[0, 0.8, 29, 50, 50, 110]]), shapes
            )
            np.testing.assert_array_equal(out, ref)

    def test_packed_probabilities(self):
        x = np.random.default_rng(80).normal(size=(100, 8)).astype(np.float32)
        y = x[:, 0] ** 2 + x[:, 1] > 1
        f = ExtraTreesClassifier(n_estimators=9, max_depth=4, random_state=42).fit(x, y)
        b = HistGradientBoostingClassifier(
            max_iter=10, max_leaf_nodes=5, random_state=42
        ).fit(x, y)
        expected = (f.predict_proba(x)[:, 1] + b.predict_proba(x)[:, 1]) / 2
        np.testing.assert_allclose(
            PackedClassifier((f, b)).probability(x), expected, rtol=1e-12, atol=1e-12
        )

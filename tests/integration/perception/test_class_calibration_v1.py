"""Class separation, score-grid ranking and unchanged runtime floor regressions."""

from dataclasses import asdict
import unittest
import numpy as np

from physical_ai.perception.class_calibration_v1 import (
    CLASS_ORDER,
    GRID,
    decode,
    from_counts,
    rank,
    search,
    validate_vector,
)
from physical_ai.perception.model_screen_v2 import decode as scalar_decode
from quality_benchmark_v3 import measure


class ClassCalibrationTests(unittest.TestCase):
    def raw(self):
        raw = dict(
            labels=np.full((1, 300), 79, np.int64),
            scores=np.zeros((1, 300), np.float32),
            boxes=np.tile(np.array([[[10, 10, 30, 30]]], np.float32), (1, 300, 1)),
        )
        raw["labels"][0, :3] = [0, 1, 2]
        raw["scores"][0, :3] = [0.4, 0.6, 0.8]
        return raw

    def baseline(self):
        return dict(
            micro=dict(precision=0.9, recall=0.75),
            per_class={str(c): dict(recall=0.7) for c in CLASS_ORDER},
        )

    def points(self):
        return {
            str(t): dict(
                per_class={str(c): dict(tp=8, fp=1, fn=2) for c in CLASS_ORDER},
                near_person=dict(tp=3, fp=0, fn=0),
                negative_fp_by_class={str(c): 0 for c in CLASS_ORDER},
                negative_frames=9,
                errors=0,
            )
            for t in GRID
        }

    def test_mixed_vector_does_not_confuse_overlapping_rider_gt(self):
        raw = self.raw()
        gt = [
            dict(
                class_id=c,
                box=[10, 10, 30, 30],
                instance_id=7,
                semantic_tags=[13 if c == 0 else 19],
                visible_pixels=100,
            )
            for c in [0, 1]
        ]
        vector = [0.35, 0.7, 0.7, 0.7, 0.7, 0.7]
        mixed = [asdict(d) for d in decode(raw, vector)]
        values, _, _, _, _ = measure(mixed, gt, [])
        for class_id, threshold in zip(CLASS_ORDER, vector):
            scalar = [asdict(d) for d in scalar_decode(raw, "rtdetr", threshold)]
            expected, _, _, _, _ = measure(scalar, gt, [])
            self.assertEqual(values[str(class_id)], expected[str(class_id)])

    def test_constant_vector_equals_native_scalar_decoder(self):
        for t in GRID:
            self.assertEqual(
                [asdict(d) for d in decode(self.raw(), [t] * 6)],
                [asdict(d) for d in scalar_decode(self.raw(), "rtdetr", t)],
            )

    def test_floor_and_grid_are_explicit(self):
        for vector in ([0.3] * 6, [0.35] * 5, [float("nan")] * 6, [True] * 6):
            with self.assertRaises(ValueError):
                validate_vector(vector)

    def test_native_capacity_is_not_hidden_by_high_class_thresholds(self):
        raw = self.raw()
        raw["labels"][0, :101] = 0
        raw["scores"][0, :101] = 0.4
        with self.assertRaisesRegex(ValueError, "capacity"):
            decode(raw, [0.7] * 6)

    def test_failure_flag_cannot_be_ranked_as_absolute_pass(self):
        counts = {str(c): dict(tp=8, fp=1, fn=2) for c in CLASS_ORDER}
        card = from_counts(
            [0.35] * 6, counts, dict(tp=3, fn=0), 0, 9, 1, self.baseline()
        )
        self.assertFalse(card["absolute"]["no_model_errors"])
        self.assertFalse(card["absolute_pass"])

    def test_ranking_prioritizes_unchanged_gates(self):
        base = dict(
            absolute_pass=True,
            relative_pass=False,
            macro_f1=0.99,
            minimum_class_recall=0.9,
            f1=0.99,
            vector=[0.7] * 6,
        )
        eligible = {**base, "relative_pass": True, "macro_f1": 0.8}
        self.assertGreater(rank(eligible), rank(base))
        self.assertGreater(rank(base), rank({**base, "absolute_pass": False}))

    def test_complete_search_and_exact_tie_choose_higher_vector(self):
        result = search(self.points(), self.baseline())
        self.assertEqual(result["combinations"], 15625)
        self.assertEqual(result["absolute_pass_count"], 15625)
        self.assertEqual(result["selected"]["vector"], [0.7] * 6)


if __name__ == "__main__":
    unittest.main()

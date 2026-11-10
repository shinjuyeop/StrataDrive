"""Semantic ambiguity, threshold boundaries and non-reusable proposal bounds."""

import unittest
import numpy as np

from physical_ai.perception.model_diagnostics_v1 import (
    FP_BUCKETS,
    FN_BUCKETS,
    fp_evidence,
    fn_evidence,
    maximum_matching,
    native_proposals,
    strict_matching,
)
from quality_benchmark_v3 import measure


def obj(class_id=0, box=(10, 10, 30, 30), instance=7, tags=(12,)):
    return dict(
        class_id=class_id,
        box=list(box),
        instance_id=instance,
        semantic_tags=list(tags),
        visible_pixels=100,
    )


def pred(class_id=0, score=0.8, box=(10, 10, 30, 30), native_index=0):
    return dict(
        class_id=class_id, score=score, box=list(box), native_index=native_index
    )


class ModelDiagnosticsTests(unittest.TestCase):
    def raw(self):
        return dict(
            labels=np.zeros((1, 300), np.int64),
            scores=np.zeros((1, 300), np.float32),
            boxes=np.tile(np.array([[[10, 10, 30, 30]]], np.float32), (1, 300, 1)),
        )

    def test_primary_duplicate_and_stable_tie_match_existing_scorer(self):
        objects = [obj(), obj(box=(100, 100, 120, 120))]
        predictions = [pred(), pred(), pred(class_id=1)]
        values, assigned, used = strict_matching(predictions, objects)
        expected, expected_used, _, _, _ = measure(predictions, objects, [])
        self.assertEqual((values, used), (expected, expected_used))
        self.assertEqual(assigned, {0: 0, 1: None, 2: None})
        self.assertEqual(
            fp_evidence(predictions[1], objects, [], used)["bucket"], FP_BUCKETS[0]
        )

    def test_rider_overlap_is_preserved_as_ambiguity(self):
        objects = [obj(tags=(13,)), obj(class_id=1, tags=(19,))]
        # A motorcycle prediction overlaps two different GT classes from one actor.
        result = fp_evidence(pred(class_id=3), objects, [], set())
        self.assertEqual(result["bucket"], FP_BUCKETS[1])
        self.assertTrue(result["rider_overlap"])
        self.assertTrue(result["same_actor_cross_class_gt_overlap"])
        self.assertEqual(len(result["relationships"]), 2)

    def test_excluded_overlap_does_not_remove_primary_fp(self):
        result = fp_evidence(pred(), [], [obj()], set())
        self.assertEqual(result["bucket"], FP_BUCKETS[-1])
        self.assertEqual(result["max_excluded_iou"], 1.0)

    def test_threshold_equality_and_subscreen_scores(self):
        target = obj()
        low = fn_evidence(target, [pred(score=0.02)], 0.5)
        self.assertEqual(low["bucket"], FN_BUCKETS[1])
        self.assertTrue(low["same_class_support_below_0p1"])
        exact = fn_evidence(target, [pred(score=0.5)], 0.5)
        self.assertEqual(exact["bucket"], FN_BUCKETS[0])

    def test_missing_class_is_distinct_from_localization(self):
        target = obj(class_id=1)
        missing = fn_evidence(target, [pred(class_id=0)], 0.5)
        self.assertEqual(missing["bucket"], FN_BUCKETS[3])
        self.assertEqual(missing["max_other_class_iou"], 1.0)
        localization = fn_evidence(
            target, [pred(class_id=1, box=(20, 10, 40, 30))], 0.5
        )
        self.assertEqual(localization["bucket"], FN_BUCKETS[2])

    def test_one_proposal_cannot_rescue_two_ground_truths(self):
        objects = [obj(), obj(instance=8)]
        result = maximum_matching(objects, [pred()])
        self.assertEqual(len(result["matched_gt"]), 1)
        self.assertEqual(len(result["assignment"]), 1)

    def test_maximum_matching_finds_augmenting_path(self):
        # First proposal can serve either GT, second only the first.
        objects = [obj(box=(0, 0, 10, 10)), obj(box=(4, 0, 14, 10), instance=8)]
        proposals = [pred(box=(2, 0, 12, 10)), pred(box=(0, 0, 10, 10), native_index=1)]
        self.assertEqual(len(maximum_matching(objects, proposals)["matched_gt"]), 2)

    def test_native_low_score_invalid_values_are_not_hidden(self):
        for field, value in (("boxes", np.inf), ("scores", np.nan)):
            raw = self.raw()
            raw[field].flat[-1] = value
            with self.assertRaisesRegex(ValueError, "raw contract"):
                native_proposals(raw)
        raw = self.raw()
        raw["labels"][0, -1] = 80
        with self.assertRaises(ValueError):
            native_proposals(raw)

    def test_clipping_and_all_native_classes_remain_visible(self):
        raw = self.raw()
        raw["labels"][0, 0] = 79
        raw["boxes"][0, 0] = [-10, 10, 700, 500]
        result = native_proposals(raw)
        self.assertEqual(result[0]["class_id"], 79)
        self.assertEqual(result[0]["score"], 0.0)
        self.assertEqual(result[0]["box"], [0.0, 10.0, 640.0, 384.0])


if __name__ == "__main__":
    unittest.main()

import unittest

import numpy as np

from person_proposal_diagnosis import diagnose


class PersonAttributionTest(unittest.TestCase):
    def test_only_scores_on_matching_boxes_can_explain_a_miss(self):
        box = [0, 0, 10, 10]
        queries = np.array([[0, 0, 5, 10], [20, 20, 30, 30]])
        scores = np.array([0.4, 0.99])
        result = diagnose(box, False, queries, scores, [])
        self.assertEqual(result["reason"], "below_score")
        self.assertEqual(result["best_person_score"], 0.4)
        self.assertEqual(
            diagnose(box, False, queries[1:], scores[1:], [])["reason"], "no_box_iou50"
        )

    def test_ranking_and_competition_for_same_person_are_distinct(self):
        box = [0, 0, 10, 10]
        args = (np.array([box]), np.array([0.6]))
        selected = [dict(box=box, score=0.6)]
        self.assertEqual(diagnose(box, False, *args, [])["reason"], "top300")
        self.assertEqual(diagnose(box, False, *args, selected)["reason"], "one_to_one")
        self.assertEqual(diagnose(box, True, *args, selected)["reason"], "detected")

import unittest

import numpy as np

from multiview_detector import TARGET, candidate_boxes, combine, overlap


def det(c, score, box):
    return dict(class_id=c, score=score, box=list(box))


class MultiviewDetectorTest(unittest.TestCase):
    def test_additions_preserve_parent_and_require_independent_boxes(self):
        parent = [det(0, 0.4, (2, 3, 10, 18)), det(5, 0.7, (20, 40, 60, 80))]
        separate = det(0, 0.5, (32, 33, 43, 63))
        suggestions = {
            "0": [
                det(0, 0.99, (2, 4, 10, 18)),
                separate,
                det(0, 0.49, (90, 93, 99, 120)),
            ]
        }
        self.assertEqual(
            combine(parent, suggestions, {str(c): 0.5 for c in TARGET}),
            parent + [separate],
        )
        self.assertEqual(len(parent), 2)

    def test_clipped_rider_proposals_stay_inside_frame(self):
        shapes = {"1-0": [[-1, -1, 0.6, 0.8]]}
        boxes = candidate_boxes(0, [[1, 0, 1, 0.9, 2, 6, 22, 36]], [], shapes)
        np.testing.assert_allclose(boxes, [[0, 0, 14, 30]])

    def test_overlap_for_empty_and_disjoint_candidates(self):
        box = np.array([0, 0, 10, 10])
        self.assertEqual(len(overlap(box, [])), 0)
        np.testing.assert_allclose(
            overlap(box, np.array([box, [10, 0, 20, 10]])), [1, 0]
        )

import unittest

import numpy as np

from person_pair_candidate import predictions


class AdditivePersonScoreTest(unittest.TestCase):
    def test_keep_parent_and_suppress_a_second_hit_on_same_person(self):
        original = dict(class_id=0, box=[0, 0, 10, 10], score=0.61)
        data = dict(
            boxes=np.array(
                [[1, 0, 10, 10], [20, 20, 30, 30], [21, 20, 30, 30], [40, 40, 50, 50]]
            ),
            p=np.array([0.4, 0.4, 0.4, 0.05]),
            x=np.ones((4, 1)),
        )
        output = predictions(
            {"original": [original]}, data, dict(weight=[1.5], bias=0.0)
        )
        self.assertEqual(output[0], original)
        self.assertEqual([d["box"] for d in output[1:]], [[20, 20, 30, 30]])
        self.assertGreaterEqual(output[1]["score"], 0.6)

    def test_empty_image_and_empty_query_set(self):
        data = dict(boxes=np.empty((0, 4)), p=np.empty(0), x=np.empty((0, 1)))
        self.assertEqual(
            predictions({"original": []}, data, dict(weight=[1], bias=0.0)), []
        )

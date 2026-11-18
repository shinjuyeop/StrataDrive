import unittest

import numpy as np

from person_assignment_candidate import assign, refine


class PersonAssignmentTest(unittest.TestCase):
    def test_maximizes_distinct_people_before_query_quality(self):
        matches, people = assign(
            np.array([[0.99, 0.50], [0.51, 0.49], [0.10, 0.10]]),
            np.array([0.9, 0.3, 0.1]),
        )
        self.assertEqual(dict(zip(matches, people)), {0: 1, 1: 0})

    def test_only_one_positive_for_duplicate_queries(self):
        matches, people = assign(
            np.array([[0.7], [0.8], [0.2]]), np.array([0.6, 0.6, 0.7])
        )
        self.assertEqual(matches.tolist(), [1])
        self.assertEqual(people.tolist(), [0])
        self.assertEqual(len(assign(np.empty((3, 0)), np.ones(3))[0]), 0)

    def test_bounds_each_coordinate_update_by_original_box_size(self):
        class Extreme:
            def predict(self, x):
                return np.array([[-10.0, -10.0, 10.0, 10.0]])

        result = refine(np.array([[1.0, 2.0, 11.0, 22.0]]), np.ones((1, 2)), Extreme())
        np.testing.assert_allclose(result, [[0.0, 0.0, 14.0, 28.0]])

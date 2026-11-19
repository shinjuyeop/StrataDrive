"""Small car recovery preserves an overlapping car at a different depth."""

import unittest

from small_car import add


def car(box, score=0.9):
    return dict(class_id=2, box=box, score=score)


class SmallCarRecoveryTests(unittest.TestCase):
    def test_partly_occluded_car(self):
        front = car([20, 30, 100, 100])
        distant = car([25, 23, 43, 36])
        self.assertEqual(add([front], [distant], 0.7), [front, distant])

    def test_duplicate_and_interior_fragment(self):
        front = car([20, 30, 100, 100])
        for box in ([22, 33, 97, 95], [45, 55, 52, 64]):
            with self.subTest(box=box):
                self.assertEqual(add([front], [car(box)], 0.7), [front])

    def test_annotation_boundary_margin(self):
        self.assertEqual(add([], [car([20, 30, 31, 34.15])], 0.7), [])

    def test_minimum_agreement_and_duplicate_proposals(self):
        distant = car([30, 20, 44, 29])
        similar = car([31, 20, 45, 29], 0.8)
        weak = car([50, 60, 60, 68], 0.5)
        self.assertEqual(add([], [distant, similar, weak], 0.7), [distant])

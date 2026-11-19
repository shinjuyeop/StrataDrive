import unittest

from cycle_transfer import alignment, regions, suggestions


class CycleTransferTest(unittest.TestCase):
    def test_rider_alignment_requires_upper_and_lower_contact(self):
        box = [10, 20, 30, 40]
        self.assertTrue(alignment(box, [15, 2, 25, 28]))
        self.assertFalse(alignment(box, [35, 2, 45, 28]))
        self.assertFalse(alignment(box, [15, 1, 25, 13]))

    def test_duplicate_views_and_existing_bike(self):
        bike = dict(class_id=1, score=0.7, box=[10, 20, 30, 40])
        self.assertEqual(regions([bike, bike], [bike]), [])
        self.assertEqual(len(regions([bike, bike], [])), 1)

    def test_rider_alone_does_not_determine_type(self):
        bike = dict(class_id=1, score=0.7, box=[10, 20, 30, 40])
        rider = dict(class_id=0, score=0.9, box=[15, 2, 25, 28])
        self.assertEqual(suggestions([bike], [rider], [], []), [])
        self.assertEqual(
            len(suggestions([bike], [rider], [[0, 0, 1, 0.8, 10, 20, 30, 40]], [])), 1
        )

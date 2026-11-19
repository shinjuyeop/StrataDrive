import unittest

from visible_car import select_boxes


class VisibleSupportTests(unittest.TestCase):
    def test_apply_both_visibility_floors_only_to_added_boxes(self):
        parent = [{"box": [0, 0, 5, 5]}]
        small_area = {"box": [10, 10, 17, 15]}
        narrow = {"box": [20, 20, 60, 24]}
        supported = {"box": [40, 40, 54, 50]}
        calibration = dict(area_fraction=0.4, side_fraction=0.9)
        self.assertEqual(
            select_boxes(parent, parent + [small_area, narrow, supported], calibration),
            parent + [supported],
        )

    def test_parent_identity(self):
        with self.assertRaises(ValueError):
            select_boxes([{"box": [0, 0, 4, 4]}], [], {})

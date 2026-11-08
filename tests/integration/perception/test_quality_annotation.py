import unittest

import numpy as np

from prepare_dataset import visible_boxes
from quality_annotation import visible_boxes_v2


class QualityAnnotationTests(unittest.TestCase):
    def setUp(self):
        self.image = np.zeros((384, 640, 4), np.uint8)

    def paint(self, x, tag, ident, w=5, h=5):
        self.image[10 : 10 + h, x : x + w] = (ident >> 8, ident & 255, tag, 255)

    def test_rider_is_person_and_vehicle_with_same_instance_remains_separate(self):
        self.paint(10, 13, 0x1234)
        self.paint(20, 19, 0x1234)
        included, excluded = visible_boxes_v2(self.image.tobytes())
        self.assertFalse(excluded)
        self.assertEqual(
            [(o["class_id"], o["instance_id"]) for o in included],
            [(0, 0x1234), (1, 0x1234)],
        )
        self.assertEqual(included[0]["box"], [10, 10, 15, 15])
        self.assertEqual(included[0]["semantic_tags"], [13])
        # Frozen v1 remains byte-for-byte unchanged and still exposes its omission.
        self.assertEqual(
            [o["class_id"] for o in visible_boxes(self.image.tobytes())[0]], [1]
        )

    def test_person_tags_merge_once_per_instance_without_merging_other_people(self):
        self.paint(10, 12, 1)
        self.paint(15, 13, 1)
        self.paint(30, 13, 2)
        rows, _ = visible_boxes_v2(self.image.tobytes())
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["visible_pixels"], 50)
        self.assertEqual(rows[0]["box"], [10, 10, 20, 15])
        self.assertEqual(rows[0]["semantic_tags"], [12, 13])

    def test_support_thresholds_and_unknown_tags_are_unchanged(self):
        self.paint(10, 13, 1, w=6, h=4)  # 24 pixels
        self.paint(30, 13, 2, w=3, h=10)  # 30 pixels but side3
        self.paint(50, 13, 3)  # 25 pixels, accepted
        self.paint(70, 24, 4)  # road line, not a person
        rows, excluded = visible_boxes_v2(self.image.tobytes())
        self.assertEqual([r["instance_id"] for r in rows], [3])
        self.assertEqual([r["instance_id"] for r in excluded], [1, 2])
        with self.assertRaises(ValueError):
            visible_boxes_v2(b"")


if __name__ == "__main__":
    unittest.main()

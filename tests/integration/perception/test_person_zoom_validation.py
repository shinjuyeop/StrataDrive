import unittest

from person_zoom_validation import crop_bounds, merge


class NativeZoomGeometryTest(unittest.TestCase):
    def test_corner_crop_has_same_field_of_view_at_every_source_size(self):
        for factor in (1, 2, 4):
            size = (640 * factor, 384 * factor)
            self.assertEqual(
                crop_bounds(size, [637, 380, 640, 384]),
                (400 * factor, 240 * factor, *size),
            )
            self.assertEqual(
                crop_bounds(size, [0, 0, 1, 1]), (0, 0, 240 * factor, 144 * factor)
            )

    def test_replace_inside_centers_keep_right_boundary_and_restore_coordinates(self):
        outside = dict(class_id=0, score=0.8, box=[238, 40, 242, 50])
        inside = dict(class_id=0, score=0.75, box=[10, 10, 30, 40])
        local = [
            dict(class_id=0, score=0.9, box=[16, 8, 32, 24]),
            dict(class_id=3, score=0.9, box=[10, 4, 30, 20]),
        ]
        for factor in (1, 2, 4):
            self.assertEqual(
                merge(
                    [inside, outside],
                    local,
                    (0, 0, 240 * factor, 144 * factor),
                    (640 * factor, 384 * factor),
                ),
                [outside, dict(class_id=0, score=0.9, box=[6, 3, 12, 9])],
            )

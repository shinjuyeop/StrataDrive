import unittest
from quality_site_geometry import screen


class SiteGeometryTests(unittest.TestCase):
    def test_flat_site_preserves_actor_origin_clearance(self):
        self.assertTrue(screen(0.3, 0.1, 0.8, 0.5, 0.1, 0.4)["passed"])

    def test_rising_falling_and_off_lane_sites_rejected(self):
        for road_z, distance in ((0.4, 0), (-0.2, 0), (0.1, 2.1)):
            with self.subTest(road_z=road_z, distance=distance):
                self.assertFalse(screen(0.3, 0.1, 0.8, 0.5, road_z, distance)["passed"])

    def test_invalid_geometry_cannot_report_clearance_success(self):
        for value in (float("nan"), float("inf"), True):
            with self.assertRaises(ValueError):
                screen(0.3, 0.1, 0.8, 0.5, value, 0)
        with self.assertRaises(ValueError):
            screen(0.3, 0.1, 0.8, 0.5, 0.1, -1)

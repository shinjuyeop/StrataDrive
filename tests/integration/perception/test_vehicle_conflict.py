import unittest
from vehicle_conflict import containment, filter_detections


class VehicleConflictTest(unittest.TestCase):
    def test_occlusion_overlap_is_asymmetric(self):
        self.assertEqual(containment([2, 3, 4, 5], [0, 0, 8, 8]), 1)
        self.assertEqual(containment([0, 0, 8, 8], [2, 3, 4, 5]), 4 / 64)
        self.assertEqual(containment([0, 0, 1, 1], [2, 3, 4, 5]), 0)

    def test_independent_truck_survives(self):
        parent = [dict(class_id=k) for k in [2, 7, 7, 7]]
        checks = {"1": {"car_evidence": 0.8}, "2": {"car_evidence": 0.3}}
        self.assertEqual(
            filter_detections(parent, checks, 0.75), [parent[0], parent[2], parent[3]]
        )

"""JSON representation equivalence cannot hide numerical or count changes."""

import unittest
from audit_class_calibration_v1 import exact_json_candidates


class ClassCalibrationAuditTests(unittest.TestCase):
    def test_tuple_box_round_trip_is_exact_json(self):
        expected = {"predictions": [{"box": [1.0, 2.0, 3.0, 4.0], "score": 0.6}]}
        actual = {"predictions": [{"box": (1.0, 2.0, 3.0, 4.0), "score": 0.6}]}
        exact_json_candidates(expected, actual)

    def test_small_score_or_count_change_is_rejected(self):
        for actual in ({"score": 0.60000001, "tp": 5}, {"score": 0.6, "tp": 6}):
            with self.assertRaisesRegex(ValueError, "exact serialized"):
                exact_json_candidates({"score": 0.6, "tp": 5}, actual)


if __name__ == "__main__":
    unittest.main()

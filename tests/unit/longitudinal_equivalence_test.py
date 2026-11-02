"""Test the independent replay oracle by corrupting otherwise valid evidence."""
from copy import deepcopy
import importlib.util
import json
import math
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1] / "integration/longitudinal"
sys.path.insert(0, str(HERE))
SPEC = importlib.util.spec_from_file_location("longitudinal_equivalence", HERE / "check_equivalence.py")
oracle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(oracle)


class LongitudinalEquivalenceTest(unittest.TestCase):
    def setUp(self):
        self.expected = oracle.python_replay(
            "new fixture\ninit 1\nstep 0 0.02 1 1 1 0 0 0\n"
            "step 20000000 0.02 1 1 1 1 20000000 0\n")

    def test_round_trip_and_counts(self):
        actual = oracle.read_records("\n".join(json.dumps(row) for row in self.expected))
        result = oracle.compare_records(self.expected, actual)
        self.assertTrue(result["pass_"])
        self.assertEqual(result["events"], 4)
        self.assertEqual(result["cases"]["fixture"]["steps"], 2)
        self.assertTrue(all(value == 0 for value in result["max_absolute_errors"].values()))

    def test_missing_extra_reordered_or_empty_events_fail(self):
        for actual in (self.expected[:-1], self.expected + [self.expected[-1]],
                       self.expected[::-1], []):
            with self.subTest(actual_count=len(actual)), self.assertRaises(ValueError):
                oracle.compare_records(self.expected, actual)
        with self.assertRaises(ValueError):
            oracle.compare_records([], [])

    def test_state_validity_reason_source_and_optional_mutations_fail(self):
        changes = [("output", "valid", False), ("output", "reason", "latched"),
                   ("output", "source_ns", 20_000_001), ("output", "acceleration", None),
                   ("state", "integral", .5), ("state", "previous", .5),
                   ("state", "last_ns", 20_000_001), ("state", "fault", True),
                   ("state", "target", None), ("state", "epoch", 2),
                   ("state", "sample", None)]
        for parent, key, value in changes:
            with self.subTest(parent=parent, key=key):
                actual = deepcopy(self.expected)
                actual[-1][parent][key] = value
                with self.assertRaisesRegex(ValueError, "event 3, case fixture"):
                    oracle.compare_records(self.expected, actual)

    def test_cached_speed_and_identity_mutations_fail(self):
        for key, value in [("epoch", 2), ("sequence", 0), ("source_ns", 0), ("speed_mps", .1)]:
            actual = deepcopy(self.expected)
            actual[-1]["state"]["sample"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                oracle.compare_records(self.expected, actual)

    def test_absolute_and_relative_tolerance_are_fixed(self):
        actual = deepcopy(self.expected)
        actual[-1]["output"]["acceleration"] += oracle.ABS_TOL / 2
        self.assertTrue(oracle.compare_records(self.expected, actual)["pass_"])
        actual[-1]["output"]["acceleration"] += 10 * oracle.ABS_TOL
        with self.assertRaises(ValueError):
            oracle.compare_records(self.expected, actual)
        expected = deepcopy(self.expected)
        expected[-1]["state"]["sample"]["speed_mps"] = 1e100
        actual = deepcopy(expected)
        actual[-1]["state"]["sample"]["speed_mps"] *= 1 + oracle.REL_TOL / 2
        self.assertTrue(oracle.compare_records(expected, actual)["pass_"])
        actual[-1]["state"]["sample"]["speed_mps"] *= 1 + 10 * oracle.REL_TOL
        with self.assertRaises(ValueError):
            oracle.compare_records(expected, actual)

    def test_nonfinite_bool_as_float_and_rounded_integer_outputs_fail(self):
        for value in (math.nan, math.inf, -math.inf, True, 10**400):
            actual = deepcopy(self.expected)
            actual[-1]["state"]["integral"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                oracle.compare_records(self.expected, actual)
        for path, value in (("source_ns", 20_000_000.), ("valid", 1)):
            actual = deepcopy(self.expected)
            actual[-1]["output"][path] = value
            with self.assertRaises(ValueError):
                oracle.compare_records(self.expected, actual)

    def test_missing_and_extra_fields_fail(self):
        actual = deepcopy(self.expected)
        del actual[-1]["state"]["last_ns"]
        with self.assertRaises(ValueError):
            oracle.compare_records(self.expected, actual)
        actual = deepcopy(self.expected)
        actual[-1]["state"]["unexamined"] = 0
        with self.assertRaises(ValueError):
            oracle.compare_records(self.expected, actual)

    def test_truncated_blank_duplicate_key_and_nonfinite_json_fail(self):
        for text in ('{"index":', "\n", '{"index":0,"index":1}', '{"integral":NaN}'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                oracle.read_records(text)

    def test_malformed_common_inputs_are_rejected(self):
        for name, text in oracle.MALFORMED.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                oracle.python_replay(text)

    def test_uint64_identity_remains_exact_and_signed_zero_is_numeric(self):
        expected = oracle.python_replay(
            "new maximum\ninit 4294967295\n"
            "step 18446744073709551615 -0.0 1 1 4294967295 18446744073709551615 18446744073709551615 -0.0\n")
        actual = oracle.read_records("\n".join(json.dumps(row) for row in expected))
        actual[-1]["state"]["sample"]["speed_mps"] = 0.0
        self.assertTrue(oracle.compare_records(expected, actual)["pass_"])
        actual[-1]["state"]["sample"]["sequence"] -= 1
        with self.assertRaises(ValueError):
            oracle.compare_records(expected, actual)


if __name__ == "__main__":
    unittest.main()

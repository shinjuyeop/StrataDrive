"""Availability is a sampled consumer property, not a publication count."""

import unittest
from physical_ai.perception.availability_v1 import availability, ideal_single_clock


class AvailabilityTests(unittest.TestCase):
    def test_10hz_with60ms_delay_has60ms_gap_at100ms_lifetime(self):
        value = ideal_single_clock(100_000_000, 60_000_000)
        self.assertEqual(value["available_fraction"], 0.4)
        self.assertEqual(value["gap_per_period_ns"], 60_000_000)
        self.assertEqual(
            ideal_single_clock(50_000_000, 40_000_000)["available_fraction"], 1
        )

    def test_sampled_gaps_age_and_same_frame_reuse(self):
        result = {"identity": {"frame": 1, "source_ns": 0}}
        rows = [
            dict(
                snapshot_read_wall_ns=t,
                snapshot_read_source_ns=t,
                perception=result if t in (40_000_000, 60_000_000) else None,
            )
            for t in range(0, 100_000_000, 20_000_000)
        ]
        out = availability(
            rows, [dict(identity={"frame": 1}, received_wall_ns=0)], 0, 100_000_000
        )
        self.assertEqual(
            (out["samples"], out["available_samples"], out["unique_frames"]), (5, 2, 1)
        )
        self.assertEqual(
            (
                out["longest_unavailable_sample_run"],
                out["longest_unavailable_first_to_last_ns"],
            ),
            (2, 20_000_000),
        )

    def test_expired_or_out_of_order_samples_are_not_counted(self):
        row = dict(
            snapshot_read_wall_ns=100_000_000,
            snapshot_read_source_ns=100_000_000,
            perception={"identity": {"frame": 1, "source_ns": 0}},
        )
        with self.assertRaises(ValueError):
            availability(
                [row], [dict(identity={"frame": 1}, received_wall_ns=0)], 0, 200_000_000
            )
        row["perception"] = None
        with self.assertRaises(ValueError):
            availability([row, row], [], 0, 200_000_000)


if __name__ == "__main__":
    unittest.main()

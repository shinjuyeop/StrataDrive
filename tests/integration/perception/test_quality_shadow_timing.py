from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
from m10_quality_shadow_timing import join_reads


def result(end, frame):
    return dict(
        renderer_frame=frame,
        physical_frame=2,
        end_ns=end,
        callback_ns=15,
        physical_source_ns=10,
        original_acquisition_ns=10,
        first_native_read_ns=None,
    )


def poll(now, accepted=0):
    return dict(
        observed_wall_ns=now,
        initialized=True,
        state_fault=False,
        disconnected=False,
        wall_enable_ns=1,
        state_received_wall_ns=now,
        state_source_ns=20,
        state_frame=3,
        source_enable_ns=1,
        accepted_results=accepted,
    )


class QualityShadowTimingTest(unittest.TestCase):
    def test_latest_completed_result_at_actual_read(self):
        frames = [result(20, 1), result(30, 2), result(35, 3), result(100_000_025, 4)]
        times = [16, 17, 20, 36, 100_000_009, 100_000_010, 100_000_025]
        reads = join_reads(frames, map(poll, times), 17, 100_000_025)
        self.assertEqual([r["renderer_frame"] for r in reads], [None, 1, 3, 3, 3])
        self.assertEqual(
            [r["timing"] for r in reads],
            [
                "no_completed_result",
                "time_eligible",
                "time_eligible",
                "time_eligible",
                "scene_wall_expired",
            ],
        )
        self.assertEqual(
            [f["first_native_read_ns"] for f in frames], [20, None, 36, None]
        )

    def test_native_acceptance_contradicts_observation_mode(self):
        with self.assertRaisesRegex(ValueError, "unexpected native acceptance"):
            join_reads([result(20, 1)], [poll(25, accepted=1)], 1, 30)

    def test_regressing_read_or_completion_cannot_be_joined(self):
        with self.assertRaisesRegex(ValueError, "unordered renderer"):
            join_reads([result(30, 1), result(25, 2)], [], 1, 30)
        with self.assertRaisesRegex(ValueError, "unordered native"):
            join_reads([], [poll(25), poll(20)], 1, 30)

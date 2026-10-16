"""Independent small observations protect the report's denominator and tail meaning."""
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / "integration/runtime/check_timing.py"
SPEC = importlib.util.spec_from_file_location("check_timing", PATH)
report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(report)


class TimingReportTest(unittest.TestCase):
    def test_skipped_and_late_jobs_are_not_dropped_from_miss_rate(self):
        rows = [dict(release_ns=100, deadline_ns=105, start_ns=101, end_ns=104, ran=1, detected_ns=0),
                dict(release_ns=110, deadline_ns=115, start_ns=111, end_ns=116, ran=1, detected_ns=116),
                dict(release_ns=120, deadline_ns=125, start_ns=0, end_ns=0, ran=0, detected_ns=125)]
        result = report.job_metrics(rows)
        self.assertEqual(result["eligible_jobs"], 3)
        self.assertEqual(result["executed_jobs"], 2)
        self.assertEqual(result["missed_jobs"], 2)
        self.assertEqual(result["miss_rate"], 2 / 3)
        self.assertEqual(result["job_elapsed_ms"]["samples"], 2)
        self.assertAlmostEqual(result["job_elapsed_ms"]["mean"], .000004)

    def test_monitor_miss_survives_worker_end_timestamp_before_progress_publish(self):
        row = dict(release_ns=100, deadline_ns=105, start_ns=101, end_ns=104, ran=1, detected_ns=105)
        self.assertEqual(report.job_metrics([row])["missed_jobs"], 1)

    def test_nearest_rank_uses_individual_samples_with_a_rare_tail(self):
        result = report.distribution([1] * 99 + [100])
        self.assertEqual((result["p95"], result["p99"], result["max"]), (1, 1, 100))
        self.assertEqual(report.distribution([])["mean"], None)

    def test_invalid_intervals_and_fabricated_skipped_duration_are_rejected(self):
        row = dict(release_ns=100, deadline_ns=105, start_ns=102, end_ns=101, ran=1, detected_ns=0)
        with self.assertRaisesRegex(AssertionError, "interval"):
            report.job_metrics([row])
        row.update(ran=0, end_ns=103)
        with self.assertRaisesRegex(AssertionError, "fabricated"):
            report.job_metrics([row])

    def test_unavailable_generation_time_is_not_a_new_sensor_acquisition(self):
        row = dict(feedback_publish_ns=108, feedback_source_ns=105, input_source_ns=100,
                   feedback_valid=0, job_time_ns=105, deadline_ns=110, fault=1,
                   feedback_failsafe=1, command_rx_ns=0)
        report.validate_feedback(row)
        row["feedback_valid"] = 1
        with self.assertRaisesRegex(AssertionError, "fabricated"):
            report.validate_feedback(row)
        row["feedback_source_ns"] = row["input_source_ns"]
        report.validate_feedback(row)


if __name__ == "__main__":
    unittest.main()

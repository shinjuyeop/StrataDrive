"""Independent small observations protect the report's denominator and tail meaning."""
import importlib.util
from pathlib import Path
import tempfile
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

    def test_loss_latency_keeps_original_valid_rx_and_both_budget_boundaries(self):
        stream = dict(health=2, last_valid_ns=1_000_000_000, detected_ns=1_080_000_000)
        self.assertEqual(report.receive_latency(stream), 80)
        stream["detected_ns"] = 1_100_000_000
        self.assertEqual(report.receive_latency(stream), 100)

    def test_raw_packet_time_cannot_disguise_a_late_valid_loss_detection(self):
        stream = dict(health=2, last_valid_ns=1_000_000_000, detected_ns=1_100_000_001)
        with self.assertRaisesRegex(AssertionError, "budget"):
            report.receive_latency(stream)
        stream["detected_ns"] = 1_079_999_999
        with self.assertRaisesRegex(AssertionError, "budget"):
            report.receive_latency(stream)

    def test_missing_original_reference_and_clock_fault_are_not_pass_results(self):
        for stream in [dict(health=2, last_valid_ns=0, detected_ns=1_100_000_000),
                       dict(health=3, last_valid_ns=1_000_000_000, detected_ns=1_100_000_000)]:
            with self.assertRaises(AssertionError):
                report.receive_latency(stream)
        self.assertIsNone(report.receive_latency(dict(health=1, last_valid_ns=1_000_000_000, detected_ns=0)))

    def test_cpu_selection_prefers_a_different_physical_core_and_respects_allowed_mask(self):
        topology = {0: dict(physical_package_id="0", core_id="0"),
                    1: dict(physical_package_id="0", core_id="0"),
                    2: dict(physical_package_id="0", core_id="1")}
        self.assertEqual(report.select_cpus([0, 1, 2], topology), (0, 2))
        self.assertEqual(report.select_cpus([0, 1, 2], topology, 2, 0), (2, 0))
        self.assertEqual(report.select_cpus([3, 7], {}), (3, 7))

    def test_impossible_or_outside_cpu_placement_is_rejected(self):
        for allowed, runtime, load in [([0], None, None), ([0, 1], 2, None), ([0, 1], 0, 0), ([0, 1], 0, 2)]:
            with self.assertRaises(AssertionError):
                report.select_cpus(allowed, {}, runtime, load)

    def test_layout_order_rotates_and_every_trace_condition_keeps_all_repetitions(self):
        conditions = list(report.placement_conditions(3))
        self.assertEqual(len(conditions), 18)
        self.assertEqual([conditions[i][0] for i in (0, 6, 12)], ["baseline", "shared", "separate"])
        self.assertEqual([conditions[i][1] for i in (0, 6, 12)], [True, False, True])
        for layout in ("baseline", "shared", "separate"):
            for detailed in (True, False):
                self.assertEqual(sum(a == layout and b == detailed for a, b, _ in conditions), 3)

    def test_pooling_retains_misses_and_excludes_only_the_gap_between_independent_runs(self):
        def row(t, ran=1):
            return dict(release_ns=t, deadline_ns=t+5, start_ns=t+1 if ran else 0,
                        end_ns=t+2 if ran else 0, ran=ran, detected_ns=0 if ran else t+5)
        result = report.pooled_job_metrics([[row(100), row(110), row(120, 0)], [row(10000), row(10010)]])
        self.assertEqual((result["eligible_jobs"], result["executed_jobs"], result["missed_jobs"]), (5, 4, 1))
        self.assertEqual(result["observed_start_interval_ms"]["samples"], 2)
        self.assertEqual(result["observed_start_interval_ms"]["max"], .00001)

    def test_load_cpu_bounds_keep_partial_boundary_cycles_without_inventing_cpu_time(self):
        load = dict(exitcode=0, hard_limit_reached=False, allowed_cpus=[1], policy=0, first_release_ns=100,
                    period_ns=10, busy_window_ns=7, stopped_ns=130, wall_begin_ns=90, total_cpu_ns=20,
                    rows=[dict(release_ns=t, start_ns=t, end_ns=t+7, cpu_ns=6, ran=1) for t in (100, 110, 120)])
        result = report.validate_load(load, 1, 105, 125)
        self.assertEqual(result["requested_busy_fraction"], .7)
        self.assertEqual(result["measurement_busy_cpu_fraction_lower"], .3)
        self.assertEqual(result["measurement_busy_cpu_fraction_upper"], .9)
        self.assertEqual(result["worker_loop_cpu_fraction"], .5)
        self.assertEqual(result["cycles"], 3)

    def test_load_without_window_coverage_or_correct_affinity_cannot_validate(self):
        base = dict(exitcode=0, hard_limit_reached=False, allowed_cpus=[1], policy=0,
                    first_release_ns=110, period_ns=10, busy_window_ns=7, stopped_ns=130, rows=[])
        with self.assertRaisesRegex(AssertionError, "span"):
            report.validate_load(base, 1, 100, 125)
        with self.assertRaisesRegex(AssertionError, "placement"):
            report.validate_load(base, 0, 115, 125)

    def test_every_owner_must_confirm_its_mask_and_scheduler(self):
        threads = {name: dict(allowed_cpus=[3], observed_cpu=3, policy=0, priority=0)
                   for name in ("brake", "drive", "bms", "power", "rx", "monitor", "plant_fixture")}
        report.validate_placement(dict(threads=threads), 3)
        threads["monitor"]["allowed_cpus"] = [3, 4]
        with self.assertRaisesRegex(AssertionError, "placement"):
            report.validate_placement(dict(threads=threads), 3)

    def test_failed_contract_observations_remain_in_trace_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for name in ("brake", "drive", "bms", "power", "rx"):
                (directory / (name + "-jobs.csv")).write_text("start_ns,end_ns,ran\n100,120,1\n0,0,0\n")
            failed = dict(label="shared-full-1", directory=tmp, verdict="FAIL", observation_scope="validated job intervals",
                          metadata=dict(scenario="normal", detailed_trace=True))
            compared = report.trace_comparison([failed], "multirate")["by_task"]["drive"]
            self.assertEqual(compared["full_ms"]["samples"], 1)
            self.assertEqual(compared["full_runs"], ["shared-full-1"])
            self.assertEqual(compared["full_excluded_runs"], [])


if __name__ == "__main__":
    unittest.main()

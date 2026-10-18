"""Independent small observations protect the report's denominator and tail meaning."""
import importlib.util
import copy
import json
from pathlib import Path
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1] / "integration/runtime/check_timing.py"
SPEC = importlib.util.spec_from_file_location("check_timing", PATH)
report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(report)


class TimingReportTest(unittest.TestCase):
    @staticmethod
    def owner_fixture():
        config = dict(first_release_ns=1000, period_ns=10, slots=4, cpu_time_recorded=True)
        rows = [dict(slot=i, release_ns=1000+i*10, wake_target_ns=1000+i*10,
                     sleep_begin_ns=900 if i == 0 else 995+i*10, start_ns=1001+i*10,
                     phase_ns=1002+i*10, end_ns=1004+i*10, ran=1, cpu_begin_ns=10+i*10,
                     cpu_end_ns=11+i*10, injection_begin_ns=0, injection_end_ns=0,
                     expired_outputs=0, expired_feedback=0) for i in range(4)]
        return config, rows

    @staticmethod
    def skip_cycle(rows, index):
        rows[index] = {k: v if k in ("slot", "release_ns") else 0 for k, v in rows[index].items()}

    def test_owner_wake_delay_keeps_the_requested_target_when_a_newer_release_is_selected(self):
        config, rows = self.owner_fixture()
        self.skip_cycle(rows, 0)
        rows[1].update(wake_target_ns=1000, sleep_begin_ns=900, start_ns=1012, phase_ns=1013, end_ns=1015)
        report.validate_owner_cycles(rows, config)
        metrics = report.owner_cycle_metrics([rows], 10)
        self.assertEqual(metrics["skipped_slots"], 1)
        self.assertEqual(metrics["skip_locations"]["after_requested_wake"], 1)
        self.assertEqual(metrics["wake_target_to_start_ms"]["max"], .000012)
        self.assertEqual(metrics["latest_release_to_start_ms"]["max"], .000002)

    def test_owner_body_overrun_keeps_skips_and_distinguishes_cpu_work_from_wall_time(self):
        config, rows = self.owner_fixture()
        rows[0]["end_ns"] = 1025
        self.skip_cycle(rows, 1); self.skip_cycle(rows, 2)
        rows[3]["sleep_begin_ns"] = 1026
        report.validate_owner_cycles(rows, config)
        metrics = report.owner_cycle_metrics([rows], 10)
        self.assertEqual((metrics["scheduled_slots"], metrics["executed_cycles"], metrics["skipped_slots"]), (4, 2, 2))
        self.assertEqual(metrics["skip_locations"]["inside_previous_body"], 2)
        self.assertEqual(metrics["body_crossed_next_release"], 1)
        self.assertEqual(metrics["body_elapsed_ms"]["max"], .000024)
        self.assertEqual(metrics["thread_cpu_ms"]["max"], .000001)

    def test_owner_bookkeeping_gap_is_separate_from_body_and_wake_return_delay(self):
        config, rows = self.owner_fixture()
        self.skip_cycle(rows, 1); self.skip_cycle(rows, 2)
        rows[3]["sleep_begin_ns"] = 1029
        report.validate_owner_cycles(rows, config)
        metrics = report.owner_cycle_metrics([rows], 10)
        self.assertEqual(metrics["skip_locations"]["before_requested_wake"], 2)
        self.assertEqual(metrics["body_crossed_next_release"], 0)

    def test_late_sleep_call_is_not_reported_entirely_as_sleep_return_delay(self):
        config, rows = self.owner_fixture()
        self.skip_cycle(rows, 1)
        rows[2].update(wake_target_ns=1010, sleep_begin_ns=1021, start_ns=1023, phase_ns=1024, end_ns=1025)
        rows[3]["sleep_begin_ns"] = 1026
        report.validate_owner_cycles(rows, config)
        metrics = report.owner_cycle_metrics([rows], 10)
        self.assertEqual(metrics["wake_target_to_start_ms"]["max"], .000013)
        self.assertEqual(metrics["sleep_call_lateness_ms"]["max"], .000011)
        self.assertEqual(metrics["sleep_return_delay_ms"]["max"], .000002)

    def test_late_terminal_cycle_does_not_invent_more_scheduled_slots(self):
        config, rows = self.owner_fixture(); config["slots"] = 2; rows = rows[:2]
        rows[0]["end_ns"] = 1015
        rows[1].update(wake_target_ns=1020, sleep_begin_ns=1016, start_ns=1021, phase_ns=1022, end_ns=1024)
        report.validate_owner_cycles(rows, config)
        self.assertEqual(report.owner_cycle_metrics([rows], 10)["scheduled_slots"], 2)

    def test_fabricated_owner_work_cpu_time_old_release_and_incomplete_tail_are_rejected(self):
        config, original = self.owner_fixture()
        for mutation in ("skipped", "cpu", "cpu_regression", "release", "tail"):
            rows = copy.deepcopy(original)
            if mutation == "skipped":
                rows[0]["ran"] = 0
            elif mutation == "cpu":
                rows[0]["cpu_end_ns"] = 100
            elif mutation == "cpu_regression":
                rows[1]["cpu_begin_ns"] = 1; rows[1]["cpu_end_ns"] = 2
            elif mutation == "release":
                rows[0]["start_ns"] = 1011; rows[0]["phase_ns"] = 1012; rows[0]["end_ns"] = 1014
            else:
                self.skip_cycle(rows, 3)
            with self.assertRaises(AssertionError, msg=mutation):
                report.validate_owner_cycles(rows, config)

    def test_minimal_owner_trace_keeps_intervals_but_has_no_cpu_clock_samples(self):
        config, rows = self.owner_fixture(); config["cpu_time_recorded"] = False
        for row in rows:
            row["cpu_begin_ns"] = row["cpu_end_ns"] = 0
        report.validate_owner_cycles(rows, config)
        metrics = report.owner_cycle_metrics([rows], 10)
        self.assertEqual(metrics["body_elapsed_ms"]["samples"], 4)
        self.assertEqual(metrics["thread_cpu_ms"]["samples"], 0)
        rows[0]["cpu_begin_ns"] = 1
        with self.assertRaisesRegex(AssertionError, "minimal"):
            report.validate_owner_cycles(rows, config)

    def test_normal_contract_still_rejects_any_expired_output(self):
        metadata = dict(schema=4, clock="CLOCK_MONOTONIC", aborted=False, trace_drops=0, expired_outputs=1, scenario="normal")
        with self.assertRaisesRegex(AssertionError, "expired output"):
            report.analyze_multirate(Path("unused"), metadata)

    def test_plant_injection_does_not_allow_unrelated_or_unaccounted_expiry_later(self):
        _, rows = self.owner_fixture()
        rows[1].update(injection_begin_ns=1012, injection_end_ns=1013)
        rows[2].update(expired_outputs=2, expired_feedback=1)
        report.validate_plant_overrun_expiry(rows)
        rows[3]["expired_outputs"] = 1
        with self.assertRaisesRegex(AssertionError, "unrelated expiry"):
            report.validate_plant_overrun_expiry(rows)

    def test_rx_correlation_retains_each_miss_and_owner_slots_without_claiming_a_cause(self):
        config, rows = self.owner_fixture()
        rows[0]["end_ns"] = 1025; rows[3]["sleep_begin_ns"] = 1026
        self.skip_cycle(rows, 1); self.skip_cycle(rows, 2)
        rx = [dict(job=0, release_ns=1010, deadline_ns=1018, start_ns=0, end_ns=0, ran=0, detected_ns=1019),
              dict(job=1, release_ns=1020, deadline_ns=1028, start_ns=1021, end_ns=1022, ran=1, detected_ns=1028)]
        result = report.correlate_rx_owners(rx, dict(monitor=rows, plant_fixture=copy.deepcopy(rows)), config)
        self.assertEqual((result["rx_missed_jobs"], result["both_owners_skipped_same_slot"]), (2, 2))
        event = result["events"][0]["owners"]["monitor"]
        self.assertEqual((event["previous_phase_ns"], event["next_phase_ns"], event["phase_gap_ns"]), (1002, 1032, 30))
        self.assertTrue(event["next_phase_at_or_after_rx_deadline"])

    def test_owner_pooling_uses_individual_samples_and_excludes_inter_run_gaps(self):
        _, rows = self.owner_fixture(); second = copy.deepcopy(rows)
        for row in second:
            for key in ("release_ns", "wake_target_ns", "sleep_begin_ns", "start_ns", "phase_ns", "end_ns"):
                row[key] += 10000
        metrics = report.owner_cycle_metrics([rows, second], 10)
        self.assertEqual(metrics["observed_start_interval_ms"]["samples"], 6)
        self.assertEqual(metrics["observed_start_interval_ms"]["max"], .00001)

    def test_bad_owner_trace_does_not_discard_valid_failed_run_job_observations_or_break_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            metadata = dict(schema=4, owner_cycles={}, tasks=[dict(name="rx", jobs=1, first_release_ns=100, period_ns=10, deadline_ns=5)])
            (directory / "rx-jobs.csv").write_text("job,release_ns,deadline_ns,start_ns,end_ns,ran,detected_ns\n0,100,105,101,106,1,105\n")
            (directory / "run.json").write_text(json.dumps(metadata))
            observed = report.observe_jobs(directory)
            self.assertEqual(observed["metrics"]["rx"]["missed_jobs"], 1)
            self.assertIn("owner_observation_error", observed)
            metadata["schema"] = 3
            (directory / "run.json").write_text(json.dumps(metadata))
            self.assertNotIn("owner_observation_error", report.observe_jobs(directory))

    @staticmethod
    def feedback_observations():
        wire=dict(crc_ok=1,source_ns=10,sequence=0,value_valid=1,torque_nm=12.4,
                  speed_valid=1,speed_source_ns=14,capability_valid=1,capability_source_ns=15,
                  input_time_ns=12,payload_hex="01"*64)
        tx=dict(wire,begin_ns=16,end_ns=17,generation_ns=15,deadline_ns=20,job=0,candidate_job=0,replayed=0)
        rx=dict(wire,time_ns=18,accepted_ns=19,usable=1,usable_source_ns=10,usable_torque_nm=12.4)
        job=dict(reported=1,phase_ns=15,report_source_ns=10,value_valid=1,input_source_ns=10,input_torque_nm=12.35)
        return tx,rx,job

    def test_actual_socket_observation_preserves_acquisition_and_separate_generation_time(self):
        tx,rx,job=self.feedback_observations()
        result=report.drive_feedback_metrics([tx],[rx],[job])
        self.assertEqual(result["accepted"],1)
        self.assertEqual(result["source_to_rx_ms"]["max"],.000008)
        self.assertEqual(result["generation_to_tx_ms"]["max"],.000001)
        self.assertEqual(result["tx_to_rx_ms"]["max"],.000002)

    def test_report_generation_cannot_replace_the_actual_torque_acquisition(self):
        tx,rx,job=self.feedback_observations(); tx["source_ns"]=15; job["report_source_ns"]=15
        with self.assertRaisesRegex(AssertionError,"acquisition"):
            report.drive_feedback_metrics([tx],[rx],[job])

    def test_actual_receiver_requires_recorded_transmitted_bytes_and_valid_acceptance(self):
        tx,rx,job=self.feedback_observations(); rx["payload_hex"]="02"*64
        with self.assertRaisesRegex(AssertionError,"socket TX"):
            report.drive_feedback_metrics([tx],[rx],[job])
        rx["payload_hex"]=tx["payload_hex"]; rx["accepted_ns"]=0
        with self.assertRaisesRegex(AssertionError,"no independent"):
            report.drive_feedback_metrics([tx],[rx],[job])

    def test_replayed_actual_stays_in_raw_counts_without_a_new_accepted_sample(self):
        tx,rx,job=self.feedback_observations()
        repeated=dict(tx,begin_ns=100,end_ns=101,replayed=1,candidate_job=1)
        rejected=dict(rx,time_ns=102,accepted_ns=0,usable=0)
        result=report.drive_feedback_metrics([tx,repeated],[rx,rejected],[job])
        self.assertEqual((result["sent"],result["received"],result["accepted"]),(2,2,1))

    def test_actual_csv_keeps_uint64_nanoseconds_and_exact_payload_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"actual.csv"; p.write_text("source_ns,torque_nm,payload_hex\n9007199254740993,12.4,"+"00"*64+"\n")
            row=report.multirate_rows(p)[0]
            self.assertEqual(row["source_ns"],9007199254740993)
            self.assertEqual(row["payload_hex"],"00"*64)

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

    def test_owner_layouts_move_only_the_declared_owners_and_keep_load_cpu_fixed(self):
        colocated = report.owner_placement("colocated", 3, 7)
        rx = report.owner_placement("rx-isolated", 3, 7)
        io = report.owner_placement("io-isolated", 3, 7)
        self.assertEqual(set(colocated.values()), {7})
        self.assertEqual({n for n in rx if rx[n] != colocated[n]}, {"rx"})
        self.assertEqual({n for n in io if io[n] != colocated[n]}, {"rx", "monitor", "plant_fixture"})
        self.assertEqual(io, report.owner_placement("io-baseline", 3, 7))

    def test_wrong_owner_can_not_be_hidden_by_the_correct_set_of_used_cpus(self):
        owners = report.owner_placement("io-isolated", 3, 7)
        threads = {name: dict(allowed_cpus=[cpu], observed_cpu=cpu, policy=0, priority=0) for name, cpu in owners.items()}
        metadata = dict(threads=threads, requested_owner_cpus=[owners[n] for n in report.OWNER_NAMES])
        report.validate_placement(metadata, owners)
        threads["drive"], threads["rx"] = threads["rx"], threads["drive"]
        with self.assertRaisesRegex(AssertionError, "placement"):
            report.validate_placement(metadata, owners)

    def test_fixed_owner_map_needs_seven_decimal_ids_without_missing_or_extra_fields(self):
        self.assertEqual(report.parse_owner_cpus("7,7,7,7,3,3,3"), report.owner_placement("io-isolated", 3, 7))
        for invalid in ("", "0,0", "0,0,0,0,0,0,0,0", "0,0,0,0,0,0,", "0,0,0,0,0,0,-1", "0,0,0,0,0,0, 1"):
            with self.assertRaises(AssertionError):
                report.parse_owner_cpus(invalid)

    def test_four_owner_layouts_keep_repetitions_and_rotate_without_dropping_a_layout(self):
        conditions = list(report.placement_conditions(4, report.OWNER_LAYOUTS))
        self.assertEqual(len(conditions), 32)
        self.assertEqual([conditions[i][0] for i in (0, 8, 16, 24)], list(report.OWNER_LAYOUTS))
        for layout in report.OWNER_LAYOUTS:
            for detailed in (True, False):
                self.assertEqual(sum(a == layout and b == detailed for a, b, _ in conditions), 4)

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

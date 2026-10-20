"""Synthetic kernel-format/cleanup contracts; not a real kernel capture."""
import importlib.util
import errno
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
import resource
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/"tools"/(name+".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


capture = module("m4_kernel_capture")
analysis = module("m4_kernel_analysis")
with patch.dict(sys.modules, m4_kernel_capture=capture):
    campaign = module("m4_kernel_campaign")
campaign_analysis = module("m4_kernel_campaign_analysis")


def event(ns, kind, body, tid=0, cpu=1):
    return f"actor-{tid} [{cpu:03}] d..2. {ns//1000000000}.{ns%1000000000:09}: {kind}: {body}\n"


def trace_lines():
    return [
        event(999999000, "tracing_mark_write", "SD_M4_CLOCK_begin", 80, 2),
        event(1000000000, "hrtimer_init", "hrtimer=abc clockid=CLOCK_MONOTONIC mode=REL", 42),
        event(1000100000, "hrtimer_start", "hrtimer=abc function=hrtimer_wakeup expires=1002050000 softexpires=1002000000 mode=REL", 42),
        event(1002180000, "local_timer_entry", "vector=239"),
        event(1002190000, "irq_handler_entry", "irq=1 name=timer"),
        event(1002200000, "hrtimer_expire_entry", "hrtimer=abc function=hrtimer_wakeup now=1002200000"),
        event(1002210000, "sched_wakeup", "comm=actor pid=42 prio=120 target_cpu=001"),
        event(1002220000, "hrtimer_expire_exit", "hrtimer=abc"),
        event(1002260000, "irq_handler_exit", "irq=1 ret=handled"),
        event(1002270000, "local_timer_exit", "vector=239"),
        event(1002600000, "sched_switch", "prev_comm=idle prev_pid=0 prev_prio=120 prev_state=R ==> next_comm=actor next_pid=42 next_prio=120"),
        event(1003000000, "sched_switch", "prev_comm=actor prev_pid=42 prev_prio=120 prev_state=R+ ==> next_comm=load next_pid=99 next_prio=120", 42),
        event(1003200000, "sched_switch", "prev_comm=load prev_pid=99 prev_prio=120 prev_state=R ==> next_comm=actor next_pid=42 next_prio=120", 99),
        event(1003290000, "local_timer_entry", "vector=239", 42),
        event(1003300000, "irq_handler_entry", "irq=1 name=timer", 42),
        event(1003450000, "irq_handler_exit", "irq=1 ret=handled", 42),
        event(1003470000, "local_timer_exit", "vector=239", 42),
        event(1004000000, "sched_switch", "prev_comm=actor prev_pid=42 prev_prio=120 prev_state=S ==> next_comm=idle next_pid=0 next_prio=120", 42),
        event(1005000000, "tracing_mark_write", "SD_M4_CLOCK_end", 80, 2),
    ]


JOB = dict(owner="2", slot="1", release_ns="1002000000", deadline_ns="1006000000",
           start_ns="1002700000", end_ns="1003700000", cpu_ns="620000",
           detected_ns="0", requested_wake_ns="1002000000")


class KernelAnalysisTest(unittest.TestCase):
    def test_pre_injection_deadline_remains_unexpected_when_detected_after_injection(self):
        jobs = [dict(deadline_ns="1199", detected_ns="1205"),
                dict(deadline_ns="1204", detected_ns="1207")]
        events = [dict(kind="overrun-injected", owner="9", time_ns="1200")]
        result = campaign_analysis.split_misses(jobs, events)
        self.assertEqual(result["missed_before_injection"], 1)
        self.assertEqual(result["missed_after_injection"], 1)
        self.assertEqual(result["first_detection_ns"], 1205)

    def test_unobserved_injection_is_not_inferred_from_planned_time(self):
        result = campaign_analysis.split_misses([dict(deadline_ns="1300", detected_ns="1301")], [])
        self.assertEqual(result["injection_ns"], 0)
        self.assertEqual(result["missed_without_observed_injection"], 1)
        self.assertEqual(result["missed_after_injection"], 0)

    def data(self, lines=None):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)/"kernel.trace"
            p.write_text("".join(lines or trace_lines()))
            data = analysis.collect(p, {42})
        data["cycle_times"] = {42: [c["callback_ns"] for c in data["cycles"][42]]}
        return data

    def integrity(self):
        return dict(clock="mono", truncated=False, stats={"cpu1": "overrun: 0\ncommit overrun: 0\ndropped events: 0\n"},
                    markers=[dict(name="begin", before_ns=999998500, after_ns=999999500),
                             dict(name="end", before_ns=1004999500, after_ns=1005000500)])

    def test_kernel_format_and_exact_timestamp(self):
        row = analysis.parse("     <idle>-0     [001] d..2. 12345.000123: sched_switch: prev_pid=0 next_pid=42\n")
        self.assertEqual(row["ns"], 12345000123000)
        self.assertEqual(row["fields"]["next_pid"], "42")

    def test_real_kernel_syscall_entry_and_exit_formats(self):
        # 6.8.0-138 generic capture: syscall pretty-printers omit "event: body".
        cases = [
            ("sys_clock_nanosleep(which_clock: 0, flags: 0, rqtp: 7ffc2a8d5940, rmtp: 0)",
             "sys_enter_clock_nanosleep", "which_clock", "0"),
            ("sys_clock_nanosleep -> 0x0", "sys_exit_clock_nanosleep", "ret", "0x0"),
            ("sys_nanosleep(rqtp: 740f3c7fed08, rmtp: 0)", "sys_enter_nanosleep", "rmtp", "0"),
            ("sys_nanosleep -> 0xfffffffffffffdfc", "sys_exit_nanosleep", "ret", "0xfffffffffffffdfc"),
        ]
        for body, kind, key, value in cases:
            with self.subTest(body=body):
                row = analysis.parse(f"nosintgdmn-1800 [004] ...1. 447672.576178: {body}\n")
                self.assertIsNotNone(row)
                self.assertEqual(row["kind"], kind)
                self.assertEqual(row["fields"][key], value)
                self.assertEqual(row["ns"], 447672576178000)
        self.assertIsNone(analysis.parse("actor-42 [001] ..... 1.002000: UNKNOWN OUTPUT"))

    def test_parseable_syscalls_do_not_hide_real_buffer_loss(self):
        lines = trace_lines() + [
            "actor-42 [001] ..... 1.006000: sys_clock_nanosleep -> 0x0\n"]
        data = self.data(lines)
        self.assertEqual(data["unknown_lines"], 0)
        integrity = self.integrity()
        integrity["stats"]["cpu1"] = "overrun: 0\ncommit overrun: 0\ndropped events: 256668\n"
        self.assertEqual(analysis.integrity_errors(integrity, data),
                         ["cpu1: missing/nonzero dropped events"])

    def test_separates_timer_slack_runnable_delay_and_body_preemption(self):
        data = self.data()
        row = analysis.job_metrics(JOB, 42, data, True)
        self.assertEqual(row["timer_chain"], "OBSERVED")
        self.assertEqual(row["callback_minus_soft_ns"], 200000)
        self.assertEqual(row["callback_minus_hard_ns"], 150000)  #50us allowed coalescing is separate.
        self.assertEqual(row["switch_minus_wake_ns"], 390000)
        self.assertEqual(row["body_minus_switch_ns"], 100000)
        self.assertEqual(row["runnable_off_cpu_ns"], 200000)
        self.assertEqual(row["scheduled_ns"], 800000)
        self.assertEqual(row["irq_overlap_ns"], 180000)  # nested150us is not double-counted.
        self.assertEqual(row["coverage"], "valid")

    def test_clock_markers_validate_common_monotonic_axis(self):
        self.assertEqual(analysis.integrity_errors(self.integrity(), self.data()), [])
        bad = self.integrity()
        bad["markers"][0]["before_ns"] += 10000
        self.assertTrue(analysis.integrity_errors(bad, self.data()))

    def test_loss_truncation_and_unknown_lines_invalidate_capture(self):
        for field, value in (("truncated", True), ("stats", {"cpu1": "overrun: 1\n"}), ("clock", "local")):
            bad = {**self.integrity(), field: value}
            self.assertTrue(analysis.integrity_errors(bad, self.data()))
        self.assertTrue(analysis.integrity_errors(self.integrity(), self.data(trace_lines()+["LOST EVENTS\n"])))

    def test_missing_wake_or_wrong_clock_is_not_a_timer_chain(self):
        for lines in ([x for x in trace_lines() if "sched_wakeup" not in x],
                      [x.replace("CLOCK_MONOTONIC mode=REL", "CLOCK_REALTIME mode=ABS") for x in trace_lines()]):
            self.assertEqual(analysis.job_metrics(JOB, 42, self.data(lines), True)["timer_chain"], "NOT OBSERVED")

    def test_relative_realtime_uses_kernel_monotonic_base_without_wall_clock_conversion(self):
        for mode in ("REL", "REL|HARD", "REL|PINNED"):
            lines = [x.replace("CLOCK_MONOTONIC mode=REL", "CLOCK_REALTIME mode="+mode) for x in trace_lines()]
            data = self.data(lines)
            row = analysis.job_metrics(JOB, 42, data, True)
            self.assertEqual(row["timer_chain"], "OBSERVED")
            self.assertEqual(row["timer_clock"], "CLOCK_REALTIME")
            self.assertEqual(row["timer_effective_clock"], "CLOCK_MONOTONIC")
            self.assertEqual(row["timer_init_mode"], mode)
            self.assertEqual(row["callback_minus_hard_ns"], 150000)
            # Whole-capture loss must still prevent a trusted inference.
            self.assertEqual(analysis.job_metrics(JOB, 42, data, False)["timer_chain"], "UNTRUSTED")
        missing_init = [x for x in trace_lines() if "hrtimer_init" not in x]
        self.assertEqual(analysis.job_metrics(JOB, 42, self.data(missing_init), True)["timer_chain"], "NOT OBSERVED")

    def test_real_capture_excerpt_links_relative_timer_but_remains_untrusted(self):
        path = ROOT/"tests/unit/fixtures/m4_kernel_relative.trace"
        tid = 1556913
        data = analysis.collect(path, {tid})
        data["cycle_times"] = {tid: [c["callback_ns"] for c in data["cycles"][tid]]}
        job = dict(owner="0", slot="0", release_ns="447672859958482",
                   deadline_ns="447672863958482", start_ns="447672860029173",
                   end_ns="447672860030969", cpu_ns="1380", detected_ns="0",
                   requested_wake_ns="447672859958482")
        row = analysis.job_metrics(job, tid, data, False)
        self.assertEqual(data["unknown_lines"], 0)
        self.assertEqual(row["timer_chain"], "UNTRUSTED")  # Original full capture had drops.
        self.assertEqual(row["timer_clock"], "CLOCK_REALTIME")
        self.assertEqual(row["timer_effective_clock"], "CLOCK_MONOTONIC")
        self.assertEqual(row["wake_ns"], 447672860003000)
        self.assertEqual(row["switch_ns"], 447672860029000)
        self.assertEqual(row["switch_minus_wake_ns"], 26000)

    def test_reused_timer_address_cannot_borrow_old_owner_identity(self):
        lines = trace_lines()
        lines.insert(3, event(1000150000, "hrtimer_start",
                             "hrtimer=abc function=hrtimer_wakeup expires=1002050000 softexpires=1002000000 mode=REL", 99))
        self.assertEqual(analysis.job_metrics(JOB, 42, self.data(lines), True)["timer_chain"], "NOT OBSERVED")

    def test_unexecuted_slot_does_not_acquire_a_fictitious_wakeup(self):
        row = analysis.job_metrics({**JOB, "start_ns": "0", "end_ns": "0", "requested_wake_ns": "0"},
                                   42, self.data(), True)
        self.assertEqual(row["timer_chain"], "NOT OBSERVED")
        self.assertEqual(row["switch_minus_wake_ns"], "")

    def test_sleeping_outside_body_is_not_runnable_wait(self):
        data = self.data([x.replace("prev_state=R+", "prev_state=S") for x in trace_lines()])
        row = analysis.job_metrics(JOB, 42, data, True)
        self.assertEqual(row["runnable_off_cpu_ns"], 0)
        self.assertEqual(row["blocked_ns"], 200000)

    def test_wakeup_splits_sleep_from_runnable_wait_inside_body(self):
        lines = [x.replace("prev_state=R+", "prev_state=S") for x in trace_lines()]
        lines.insert(12, event(1003100000, "sched_wakeup", "comm=actor pid=42 prio=120 target_cpu=001"))
        row = analysis.job_metrics(JOB, 42, self.data(lines), True)
        self.assertEqual(row["blocked_ns"], 100000)
        self.assertEqual(row["runnable_off_cpu_ns"], 100000)
        self.assertEqual(row["off_cpu_ns"], 200000)

    def test_invalid_global_capture_does_not_publish_trusted_chain(self):
        row = analysis.job_metrics(JOB, 42, self.data(), False)
        self.assertEqual(row["coverage"], "INVALID")
        self.assertEqual(row["timer_chain"], "UNTRUSTED")


class CollectorSafetyTest(unittest.TestCase):
    def test_verified_limit_is_set_only_in_child_before_dropping_all_credentials(self):
        calls = MagicMock()
        with patch.object(capture.resource, "setrlimit", calls.limit), \
                patch.object(capture.os, "setgroups", calls.groups), \
                patch.object(capture.os, "setgid", calls.gid), \
                patch.object(capture.os, "setuid", calls.uid):
            capture.drop_worker_privileges(1000, 1000, [1000, 27], [20, 20])
        from unittest.mock import call
        self.assertEqual(calls.mock_calls, [call.limit(resource.RLIMIT_RTPRIO, (20, 20)),
                                          call.groups([1000, 27]), call.gid(1000), call.uid(1000)])
        for uid, limit in ((0, [20, 20]), (1000, [99, 99]), (1000, [0, 0])):
            with self.assertRaises(ValueError):
                capture.drop_worker_privileges(uid, 1000, [], limit)

    def test_live_parent_identity_and_ancestry_are_required(self):
        parent = dict(pid=10, ppid=1, start_ticks=123, uids=[1000]*4, gids=[1000]*4,
                      groups=[1000], cap_eff="0", rtprio=[20, 20], affinity=[0, 1, 2],
                      policy=0, priority=0)
        def read(pid):
            return parent.copy() if pid == 10 else dict(ppid=10)
        with patch.object(campaign.os, "getpid", return_value=20), \
                patch.object(campaign, "proc_identity", side_effect=read):
            self.assertEqual(campaign.verify_parent(10, 1000), parent)
            for field, bad in (("rtprio", [0, 0]), ("uids", [0]*4),
                               ("cap_eff", "1"), ("affinity", [0, 1]), ("policy", 1)):
                original = parent[field]
                parent[field] = bad
                with self.subTest(field=field), self.assertRaises(ValueError):
                    campaign.verify_parent(10, 1000)
                parent[field] = original
            with self.assertRaisesRegex(ValueError, "ancestor"):
                campaign.verify_parent(99, 1000)

    def test_campaign_is_fixed_and_budget_failure_is_not_success(self):
        self.assertEqual(campaign.PLAN, ["other-loaded"]+["fifo-monitor-overrun"]*10)
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            with patch.object(campaign.time, "monotonic", return_value=361):
                with self.assertRaisesRegex(RuntimeError, "time budget"):
                    campaign.check_budget(folder, 0)
            with patch.object(campaign.time, "monotonic", return_value=1), \
                    patch.object(campaign, "size_bytes", return_value=campaign.MAX_BYTES-campaign.HEADROOM_BYTES):
                with self.assertRaisesRegex(RuntimeError, "storage"):
                    campaign.check_budget(folder, 0)

    def test_budget_scan_tolerates_atomic_rename_of_epoch_file(self):
        folder, temporary = MagicMock(), MagicMock()
        folder.rglob.return_value = [temporary]
        temporary.is_file.return_value = True
        temporary.is_symlink.return_value = False
        temporary.stat.side_effect = FileNotFoundError("renamed during publication")
        self.assertEqual(campaign.size_bytes(folder), 0)

    def test_campaign_conflict_records_stop_and_all_attempts_not_run(self):
        with tempfile.TemporaryDirectory() as temp, \
                patch.object(campaign, "proc_identity", return_value={}), \
                patch.object(capture, "check_conflicts", side_effect=RuntimeError("foreign tracer")):
            parent = dict(uids=[os.getuid()]*4, gids=[os.getgid()]*4)
            self.assertEqual(campaign.collect(Path(temp), parent), 2)
            saved = json.loads((Path(temp)/"campaign.json").read_text())
            self.assertEqual(saved["status"], "STOPPED")
            self.assertTrue(all(r["status"] == "NOT RUN" for r in saved["attempts"]))

    def test_campaign_keeps_all_pairs_after_workload_failure_and_returns_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = dict(pid=10, uids=[os.getuid()]*4, gids=[os.getgid()]*4,
                          groups=os.getgroups(), affinity=[0, 1, 2], rtprio=[20, 20])
            with patch.object(campaign, "proc_identity", return_value={}), \
                    patch.object(campaign, "verify_parent", return_value=parent), \
                    patch.object(campaign, "validate_other", return_value=True), \
                    patch.object(capture, "check_conflicts", return_value={}), \
                    patch.object(capture, "snapshot", return_value={}), \
                    patch.object(capture, "run_pair", return_value=[dict(worker_exit=1), dict(worker_exit=0)]) as pair:
                self.assertEqual(campaign.collect(Path(temp), parent), 1)
                self.assertEqual(pair.call_count, 11)
                result = json.loads((Path(temp)/"campaign.json").read_text())
                self.assertEqual(len(result["attempts"]), 11)
                self.assertTrue(all(r["status"] == "COLLECTED" for r in result["attempts"]))

    def test_campaign_collection_error_is_invalid_without_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = dict(pid=10, uids=[os.getuid()]*4, gids=[os.getgid()]*4,
                          groups=os.getgroups(), affinity=[0, 1, 2], rtprio=[20, 20])
            results = [[dict(worker_exit=0)], RuntimeError("EBADF fixture")] + [[dict(worker_exit=0)]]*9
            with patch.object(campaign, "proc_identity", return_value={}), \
                    patch.object(campaign, "verify_parent", return_value=parent), \
                    patch.object(campaign, "validate_other", return_value=True), \
                    patch.object(capture, "check_conflicts", return_value={}), \
                    patch.object(capture, "snapshot", return_value={}), \
                    patch.object(capture, "run_pair", side_effect=results) as pair:
                self.assertEqual(campaign.collect(Path(temp), parent), 2)
                self.assertEqual(pair.call_count, 11)
                result = json.loads((Path(temp)/"campaign.json").read_text())
                self.assertEqual(result["attempts"][1]["status"], "INVALID")
                self.assertEqual(sum(r["status"] == "COLLECTED" for r in result["attempts"]), 10)

    def test_invalid_initial_other_leaves_fifo_not_run(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = dict(pid=10, uids=[os.getuid()]*4, gids=[os.getgid()]*4,
                          groups=os.getgroups(), affinity=[0, 1, 2], rtprio=[20, 20])
            with patch.object(campaign, "proc_identity", return_value={}), \
                    patch.object(campaign, "verify_parent", return_value=parent), \
                    patch.object(campaign, "validate_other", return_value=False), \
                    patch.object(capture, "check_conflicts", return_value={}), \
                    patch.object(capture, "snapshot", return_value={}), \
                    patch.object(capture, "run_pair", return_value=[dict(worker_exit=1)]) as pair:
                self.assertEqual(campaign.collect(Path(temp), parent), 2)
                self.assertEqual(pair.call_count, 1)
                result = json.loads((Path(temp)/"campaign.json").read_text())
                self.assertEqual(result["attempts"][0]["status"], "INVALID")
                self.assertTrue(all(r["status"] == "NOT RUN" for r in result["attempts"][1:]))

    def test_actual_nonroot_campaign_exits_without_creating_output(self):
        result = subprocess.run([sys.executable, str(ROOT/"tools/m4_kernel_campaign.py"),
                                 "build/should-not-be-created", "--user-parent", str(os.getppid())],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("use sudo", result.stderr)
        self.assertFalse((ROOT/"build/should-not-be-created").exists())

    def test_marker_failure_preserves_raw_trace_and_stats_then_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            base = self.base(temp)
            folder = Path(temp)/"output"
            folder.mkdir()
            inst = capture.TraceInstance(base, folder, [])
            (inst.path/"events").mkdir(parents=True)
            (inst.path/"per_cpu/cpu2").mkdir(parents=True)
            (inst.path/"tracing_on").write_text("1")
            (inst.path/"trace").write_bytes(b"# saved partial trace\n")
            stats = "overrun: 0\ncommit overrun: 0\ndropped events: 1\n"
            (inst.path/"per_cpu/cpu2/stats").write_text(stats)
            with patch.object(inst, "mark", side_effect=OSError(errno.EBADF, "marker reserve failed")):
                with self.assertRaises(OSError) as error:
                    inst.stop_and_save()
            self.assertEqual(error.exception.errno, errno.EBADF)
            self.assertEqual((folder/"kernel.trace").read_bytes(), b"# saved partial trace\n")
            saved = json.loads((folder/"trace-integrity.json").read_text())
            self.assertEqual(saved["stats"]["cpu2"], stats)
            self.assertEqual(saved["marker_errors"][0]["errno"], errno.EBADF)
            self.assertEqual(saved["tracing_on_before_stop"], "1")
            self.assertEqual((inst.path/"tracing_on").read_text().strip(), "0")
            self.assertIn("clock sandwich markers incomplete",
                          analysis.integrity_errors(saved, dict(markers={}, parsed=1,
                              unknown_lines=0, unclosed_callbacks=0)))

    def test_marker_cpu_has_headroom_within_original_total_buffer_cap(self):
        sizes = capture.buffer_sizes(list(range(16)), 2)
        self.assertEqual(sizes[0], 16384)
        self.assertEqual(sizes[1], 32768)
        self.assertEqual(sizes[2], 2048)
        self.assertEqual(sizes[3], 256)
        self.assertLess(sum(sizes.values()), capture.MAX_BUFFER_KB)
        with self.assertRaises(ValueError):
            capture.buffer_sizes(list(range(16)), 1)
        with self.assertRaises(ValueError):
            capture.buffer_sizes(list(range(80)), 2)

    def test_compact_capture_retains_required_chain_and_reports_omitted_events(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            available = [*capture.REQUIRED, "sched:sched_waking",
                         "syscalls:sys_enter_clock_nanosleep", "irq_vectors:local_timer_entry",
                         "irq_vectors:local_timer_exit", "irq:softirq_entry", "irq:softirq_exit"]
            (base/"available_events").write_text("\n".join(available))
            info = capture.inventory(base)
            self.assertTrue(set(capture.REQUIRED) <= set(info["selected"]))
            self.assertEqual(info["missing_required"], [])
            self.assertIn("irq_vectors:local_timer_entry", info["selected"])
            self.assertIn("irq:softirq_entry", info["selected"])
            self.assertEqual(set(info["available_not_selected"]),
                             {"sched:sched_waking", "syscalls:sys_enter_clock_nanosleep"})
            self.assertNotIn("sched:sched_waking", info["selected"])
            self.assertNotIn("syscalls:sys_enter_clock_nanosleep", info["selected"])
            self.assertEqual(capture.BUFFER_KB, {0: 16384, 1: 32768})

    def base(self, temp):
        base = Path(temp)/"tracefs"
        (base/"events").mkdir(parents=True)
        (base/"instances").mkdir()
        for name, value in dict(tracing_on="1", current_tracer="nop", trace_clock="[mono]",
                                tracing_cpumask="ffff").items():
            (base/name).write_text(value)
        (base/"events/enable").write_text("0")
        return base

    def test_conflicting_events_and_instances_are_not_modified(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(capture.Path, "glob", return_value=[]):
            base = self.base(temp)
            original = capture.check_conflicts(base)
            (base/"events/enable").write_text("X")
            with self.assertRaises(RuntimeError):
                capture.check_conflicts(base)
            self.assertEqual((base/"events/enable").read_text(), "X")
            (base/"events/enable").write_text("0")
            (base/"instances/other").mkdir()
            with self.assertRaises(RuntimeError):
                capture.check_conflicts(base)
            self.assertEqual(capture.snapshot(base), original)

    def test_bounded_export_marks_truncation_without_growing_file(self):
        with tempfile.TemporaryDirectory() as temp:
            a, b = Path(temp)/"input", Path(temp)/"output"
            a.write_bytes(b"x"*100)
            self.assertTrue(capture.bounded_copy(a, b, 10))
            self.assertEqual(b.stat().st_size, 10)
            b.unlink()
            self.assertFalse(capture.bounded_copy(a, b, 100))

    def test_partial_configuration_cleanup_only_touches_owned_instance(self):
        with tempfile.TemporaryDirectory() as temp:
            base = self.base(temp)
            previous = capture.snapshot(base)
            inst = capture.TraceInstance(base, Path(temp), [])
            (inst.path/"events").mkdir(parents=True)
            (inst.path/"tracing_on").write_text("1")
            (inst.path/"events/enable").write_text("1")
            inst.created = True
            # Real tracefs virtual files vanish on rmdir; ordinary temp files cannot.
            with patch.object(capture.Path, "rmdir"):
                self.assertEqual(inst.close(), [])
            self.assertEqual((inst.path/"tracing_on").read_text().strip(), "0")
            self.assertEqual((inst.path/"events/enable").read_text().strip(), "0")
            self.assertEqual(capture.snapshot(base), previous)
            self.assertFalse(inst.created)

    def test_watchdog_eof_stops_only_owned_instance(self):
        with tempfile.TemporaryDirectory() as temp:
            base = self.base(temp)
            inst = base/"instances/owned"
            (inst/"events").mkdir(parents=True)
            (inst/"tracing_on").write_text("1")
            (inst/"events/enable").write_text("1")
            previous = capture.snapshot(base)
            reader, writer = os.pipe()
            os.close(writer)
            with patch.object(capture.Path, "rmdir"):
                capture.watchdog(reader, inst, Path(temp), 1)
            self.assertEqual((inst/"tracing_on").read_text().strip(), "0")
            self.assertEqual(capture.snapshot(base), previous)
            self.assertIn("pipe closed", json.loads((Path(temp)/"watchdog.json").read_text())["reason"])

    def test_worker_refuses_root_before_running_application(self):
        with patch.object(capture.os, "getuid", return_value=0):
            with self.assertRaisesRegex(RuntimeError, "never run as root"):
                capture.worker(Path("/unreachable"), "other-loaded", "normal", [0, 1])

    def test_actual_nonroot_capture_exits_without_changing_tracefs(self):
        if os.geteuid() == 0:
            self.skipTest("test specifically requires nonroot invocation")
        result = subprocess.run([sys.executable, str(ROOT/"tools/m4_kernel_capture.py"), "capture",
                                 "build/should-not-be-created"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertFalse((ROOT/"build/should-not-be-created").exists())
        self.assertIn("use sudo", result.stderr)

    def test_sigterm_is_handled_as_cleanup_interrupt(self):
        with self.assertRaises(KeyboardInterrupt):
            capture.interrupted(signal.SIGTERM, None)

    def pair(self, interrupt=False):
        with tempfile.TemporaryDirectory() as temp:
            base = self.base(temp)
            folder = Path(temp)/"output"
            folder.mkdir()
            before = capture.snapshot(base)
            inst = MagicMock()
            inst.path = base/"instances"/"owned"
            (inst.path/"events").mkdir(parents=True)
            (inst.path/"tracing_on").write_text("0")
            inst.created = True
            inst.close.return_value = []
            processes = [MagicMock(pid=99999980), MagicMock(pid=99999981)]
            processes[0].wait.return_value = 1  # expected OFF workload FAIL must not suppress ON.
            processes[1].wait.side_effect = KeyboardInterrupt("fixture") if interrupt else None
            processes[1].wait.return_value = 1
            with patch.object(capture, "check_conflicts", return_value=before), \
                    patch.object(capture, "inventory", return_value={"selected": [], "missing_required": []}), \
                    patch.object(capture, "TraceInstance", return_value=inst), \
                    patch.object(capture.subprocess, "Popen", side_effect=processes) as popen, \
                    patch.object(capture, "kill_group"):
                if interrupt:
                    with self.assertRaises(KeyboardInterrupt):
                        capture.run_pair(folder, "other-loaded", "normal",
                                         (os.getuid(), os.getgid(), os.getgroups(), [0, 1, 2]), base)
                else:
                    rows = capture.run_pair(folder, "other-loaded", "normal",
                                            (os.getuid(), os.getgid(), os.getgroups(), [0, 1, 2]), base)
                    self.assertEqual([r["worker_exit"] for r in rows], [1, 1])
                self.assertEqual(popen.call_count, 2)
                for call in popen.call_args_list:
                    self.assertEqual(call.kwargs["user"], os.getuid())
                    self.assertEqual(call.kwargs["extra_groups"], os.getgroups())
                    self.assertTrue(call.kwargs["start_new_session"])
                inst.close.assert_called_once()
                self.assertTrue((folder/"collection.json").exists())
                self.assertEqual(capture.snapshot(base), before)

    def test_off_failure_does_not_suppress_on_and_privileges_are_dropped(self):
        self.pair()

    def test_interruption_exports_partial_trace_and_cleans_instance(self):
        self.pair(True)


if __name__ == "__main__":
    unittest.main()

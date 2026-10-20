"""Runner bookkeeping only: mock workload, but exercise the real Python process exit."""
import csv
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "tests/integration/runtime/check_m4_delivery_trace.py"


def fixture(mode, output):
    real_run = subprocess.run
    calls = 0

    def workload(command, **kwargs):
        nonlocal calls
        if not command or command[0] != "setarch":
            return real_run(command, **kwargs)
        calls += 1
        folder = Path(kwargs["env"]["STRATADRIVE_M4_RESULTS"])
        bad = calls == 1
        if bad and mode == "timeout":
            kwargs["stdout"].write("retained before timeout\n")
            raise subprocess.TimeoutExpired(command, 30)
        if bad and mode == "launch":
            raise FileNotFoundError("fixture missing executable")
        threads = [dict(owner=i, policy=0, priority=0, affinity=sorted(os.sched_getaffinity(0)), setup_error=0) for i in range(9)]
        result = dict(passed=not (bad and mode == "failure"), event_overflow=False,
                      ownership_ok=True, physical_ok=True, transport_trace_enabled=True,
                      guards_enabled=False, duration_ns=1800000000, threads=threads, reason="")
        (folder / "wall-normal.json").write_text(json.dumps(result))
        skipped = "<skipped/>" if bad and mode == "skipped" else ""
        (folder / "unit.xml").write_text('<testsuites><testsuite><testcase classname="M4AsyncWall" name="IndependentOwnersRunActualNormalPath">'
                                        + skipped + "</testcase></testsuite></testsuites>")
        for name in ["wall-normal.csv", "wall-normal-events.csv", "wall-normal-execution.csv"]:
            (folder / name).write_text("time_ns\n1\n")
        event = dict(time_ns=100, stage="central-enqueued", owner=7, peer=0, epoch=1, token=1,
                     operation=3, original_source_ns=90, payload_source_ns=99, inner_deadline_ns=200,
                     sent_ns=100, envelope_deadline_ns=150, result_source_ns=0, outcome=1)
        with (folder / "wall-normal-transport.csv").open("w") as f:
            w = csv.DictWriter(f, list(event)); w.writeheader(); w.writerow(event)
            w.writerow({**event, "time_ns": 110, "stage": "central-result-accepted", "result_source_ns": 105})
        if bad and mode == "missing":
            (folder / "wall-normal.csv").unlink()
        if bad and mode == "malformed":
            (folder / "wall-normal.json").write_text("{malformed")
        if bad and mode == "warning":
            kwargs["stdout"].write("WARNING: ThreadSanitizer: data race (fixture)\n")
        return subprocess.CompletedProcess(command, 1 if bad and mode == "failure" else 0)

    sys.argv = [str(RUNNER), output]
    with patch("subprocess.run", side_effect=workload):
        runpy.run_path(str(RUNNER), run_name="__main__")


class DeliveryTraceExitTest(unittest.TestCase):
    def check(self, mode, success=False):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "cohort"
            result = subprocess.run([sys.executable, __file__, "--fixture", mode, str(output)],
                                    cwd=ROOT, capture_output=True, text=True, timeout=30, check=False)
            if os.environ.get("STRATADRIVE_RUNNER_TEST_RESULTS"):
                saved = Path(os.environ["STRATADRIVE_RUNNER_TEST_RESULTS"]) / mode
                shutil.copytree(output, saved, dirs_exist_ok=True)
                (saved / "process.json").write_text(json.dumps({"mode": mode, "actual_exit": result.returncode,
                    "expected_exit": 0 if success else 1, "workload": "mock; runner process real"}, indent=2)+"\n")
                (saved / "process.log").write_text(result.stdout + result.stderr)
            self.assertEqual(result.returncode == 0, success, result.stdout[-1000:] + result.stderr[-1000:])
            rows = json.loads((output / "cohort.json").read_text())
            self.assertEqual(len(rows), 40)  # a failed first trial must not hide39 planned trials
            self.assertEqual(sum(r["verdict"] == "PASS" for r in rows), 40 if success else 39)
            with (output / "summary.csv").open() as stream:
                self.assertEqual(len(list(csv.DictReader(stream))), 40)
            self.assertTrue((output / "results.json").is_file())
            self.assertTrue((output / "01-normal/run.log").is_file())
            self.assertTrue((output / "20-normal/unit.xml").is_file())

    def test_all_pass_exits_zero(self): self.check("pass", True)
    def test_failed_trial_exits_nonzero_after_all_trials(self): self.check("failure")
    def test_timeout_exits_nonzero_after_all_trials(self): self.check("timeout")
    def test_launch_failure_records_missing_execution(self): self.check("launch")
    def test_missing_required_result_cannot_pass(self): self.check("missing")
    def test_skipped_gtest_cannot_pass(self): self.check("skipped")
    def test_malformed_result_does_not_abort_remaining_trials(self): self.check("malformed")
    def test_tsan_warning_cannot_pass(self): self.check("warning")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--fixture":
        fixture(sys.argv[2], sys.argv[3])
    else:
        unittest.main()

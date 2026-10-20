"""Mock DDS workloads, real runner process exit; timeout check uses a real child."""
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT/"tests/integration/middleware/run_probe.py"


def fixture(kind, output):
    module = runpy.run_path(str(RUNNER), run_name="probe_module")
    calls = 0
    real_run = subprocess.run

    def child(folder, _binary, _condition):
        nonlocal calls
        calls += 1
        p = Path(folder); p.mkdir(parents=True, exist_ok=True)
        for name in ("central.stderr", "zone.stderr"):
            (p/name).write_text("WARNING: ThreadSanitizer: data race\n" if kind == "warning" and calls == 1 else "")
        metrics = dict(cpu=1, affinity_count=1, cpu1=1, policy=0, sent=100,
                       received=103, accepted=100, rejected=3, echo_mismatch=0, channel_failures=0)
        result = dict(verdict="FAIL" if kind == "failure" and calls == 1 else "PASS", codes=[0, 0],
                      invalid_accepted=0, expired_echoes=1, central=dict(metrics), zone=dict(metrics))
        if calls == 1:
            if kind == "array": result = []
            elif kind == "null": result = None
            elif kind == "string": result = "PASS"
            elif kind == "missing-fields": result = {"verdict": "PASS"}
            elif kind == "wrong-type": result["invalid_accepted"] = "0"
            elif kind == "verdict-type": result["verdict"] = True
            elif kind == "codes-type": result["codes"] = [0, "0"]
            elif kind == "missing-role": del result["zone"]
            elif kind == "role-type": result["zone"] = []
            elif kind == "bool-metric": result["zone"]["received"] = True
            elif kind == "negative-metric": result["zone"]["received"] = -1
            elif kind == "probe-exit": result["codes"] = [0, 66]
        if not (kind == "missing" and calls == 1):
            (p/"result.json").write_text("{bad json" if kind == "invalid-json" and calls == 1 else json.dumps(result))
        return result

    def run_trial(command, folder, **_kwargs):
        child(folder, "mock", "normal")
        return (7 if kind == "process-exit" and calls == 1 else 0), ""

    def legacy_run(command, **kwargs):
        if command[0] == "unshare":
            child(command[5], "mock", "normal")
            return subprocess.CompletedProcess(command, 0)
        return real_run(command, **kwargs)

    main = module["main"]
    sys.argv = [str(RUNNER), "--child", output, "mock", "normal"] if kind.startswith("child-") else [str(RUNNER), "--output", output]
    kind = kind.removeprefix("child-")
    with patch.dict(main.__globals__, child=child, run_trial=run_trial), patch("subprocess.run", side_effect=legacy_run):
        raise SystemExit(main())


class MiddlewareProbeExitTest(unittest.TestCase):
    def check(self, kind, expected):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/"result"
            r = subprocess.run([sys.executable, __file__, "--fixture", kind, str(output)],
                               cwd=ROOT, capture_output=True, text=True, timeout=15)
            self.assertEqual(r.returncode, expected, r.stdout[-500:]+r.stderr[-1500:])
            if not kind.startswith("child-"):
                rows = json.loads((output/"results.json").read_text())
                self.assertEqual(len(rows), 36)
                self.assertEqual(sum(row["verdict"] == "PASS" for row in rows), 36 if expected == 0 else 35)
                first = output/"dds-normal-0"/"result.json"
                if kind not in ("pass", "missing"):
                    self.assertEqual(rows[0]["verdict"], "FAIL")
                    self.assertTrue(rows[0]["diagnostic_errors"])
                if kind == "array": self.assertEqual(json.loads(first.read_text()), [])
                if kind == "null": self.assertIsNone(json.loads(first.read_text()))
                if kind == "invalid-json": self.assertEqual(first.read_text(), "{bad json")
                if kind == "process-exit": self.assertEqual(rows[0]["runner_exit"], 7)


    def test_child_pass_exits_zero(self): self.check("child-pass", 0)
    def test_child_failure_exits_nonzero(self): self.check("child-failure", 1)
    def test_child_warning_exits_nonzero(self): self.check("child-warning", 1)
    def test_all_pass_exits_zero(self): self.check("pass", 0)
    def test_failure_preserves_all_36_and_exits_nonzero(self): self.check("failure", 1)
    def test_missing_result_preserves_all_36_and_exits_nonzero(self): self.check("missing", 1)
    def test_warning_preserves_all_36_and_exits_nonzero(self): self.check("warning", 1)

    def test_array_result_preserves_all_36(self): self.check("array", 1)
    def test_null_result_preserves_all_36(self): self.check("null", 1)
    def test_string_result_preserves_all_36(self): self.check("string", 1)
    def test_missing_fields_preserves_all_36(self): self.check("missing-fields", 1)
    def test_wrong_field_type_preserves_all_36(self): self.check("wrong-type", 1)
    def test_verdict_type_preserves_all_36(self): self.check("verdict-type", 1)
    def test_codes_type_preserves_all_36(self): self.check("codes-type", 1)
    def test_missing_role_preserves_all_36(self): self.check("missing-role", 1)
    def test_role_type_preserves_all_36(self): self.check("role-type", 1)
    def test_bool_metric_preserves_all_36(self): self.check("bool-metric", 1)
    def test_negative_metric_preserves_all_36(self): self.check("negative-metric", 1)
    def test_probe_exit_preserves_all_36(self): self.check("probe-exit", 1)
    def test_process_exit_is_retained(self): self.check("process-exit", 1)
    def test_invalid_json_is_retained(self): self.check("invalid-json", 1)

    def test_real_child_timeout_preserves_log_and_returns_failure(self):
        module = runpy.run_path(str(RUNNER), run_name="probe_module")
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            code, error = module["run_trial"]([sys.executable, "-u", "-c",
                "import time; print('before timeout',flush=True); time.sleep(10)"], folder, timeout=.2)
            self.assertEqual(code, 124)
            self.assertIn("timeout", error)
            self.assertIn("before timeout", (folder/"runner.log").read_text())


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--fixture": fixture(sys.argv[2], sys.argv[3])
    else: unittest.main()

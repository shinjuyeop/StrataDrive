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
        result = dict(verdict="FAIL" if kind == "failure" and calls == 1 else "PASS", codes=[0, 0])
        if not (kind == "missing" and calls == 1):
            (p/"result.json").write_text(json.dumps(result))
        return result

    def run_trial(command, folder, **_kwargs):
        child(folder, "mock", "normal")
        return 0, ""

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

    def test_child_pass_exits_zero(self): self.check("child-pass", 0)
    def test_child_failure_exits_nonzero(self): self.check("child-failure", 1)
    def test_child_warning_exits_nonzero(self): self.check("child-warning", 1)
    def test_all_pass_exits_zero(self): self.check("pass", 0)
    def test_failure_preserves_all_36_and_exits_nonzero(self): self.check("failure", 1)
    def test_missing_result_preserves_all_36_and_exits_nonzero(self): self.check("missing", 1)
    def test_warning_preserves_all_36_and_exits_nonzero(self): self.check("warning", 1)

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

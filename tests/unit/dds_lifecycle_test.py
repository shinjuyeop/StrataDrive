"""Diagnostic bookkeeping: no DDS installation or actual SDK workload required."""
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
RUNNER=ROOT/'tests/integration/middleware/check_dds_lifecycle.py'

class DdsLifecycleBookkeepingTest(unittest.TestCase):
    def test_sanitizer_prefix_does_not_hide_lifetime_stdout(self):
        module=runpy.run_path(str(RUNNER),run_name='diagnostic')
        result=module['lifetime_result']('WARNING: ThreadSanitizer: data race\n{"free_held":0,"free_ns":9}\nThreadSanitizer: reported 2 warnings\n')
        self.assertEqual(result,{'free_held':0,'free_ns':9})

    def test_invalid_json_cannot_supply_a_lifetime_result(self):
        module=runpy.run_path(str(RUNNER),run_name='diagnostic')
        self.assertEqual(module['lifetime_result']('{invalid\n[]\nnull\n'),{})

    def test_real_process_build_failure_retains_every_planned_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);compiler=tmp/'gcc';compiler.write_text('#!/bin/sh\necho deliberate compiler failure\nexit 7\n');compiler.chmod(0o755)
            command=[sys.executable,__file__,'--build-failure',str(tmp/'out')]
            r=subprocess.run(command,cwd=ROOT,env={**os.environ,'PATH':str(tmp)+':'+os.environ['PATH']},capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode,7,r.stderr)
            plan=json.loads((tmp/'out/plan.json').read_text())
            rows=json.loads((tmp/'out/results.json').read_text())
            self.assertEqual(len(rows),plan['lifecycle_runs']+plan['bucket_runs'])
            self.assertEqual(len(rows),24)
            self.assertTrue(all(row['verdict']=='NOT RUN' for row in rows))
            self.assertIn('deliberate compiler failure',(tmp/'out/build-0.log').read_text())

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--build-failure':
        module=runpy.run_path(str(RUNNER),run_name='diagnostic');main=module['main'];sys.argv=[str(RUNNER),sys.argv[2]]
        # These tests exercise process bookkeeping, not SDK availability/provenance.
        with patch.dict(main.__globals__,sha=lambda _path:'mock SDK hash for bookkeeping fixture'):
            raise SystemExit(main())
    else:unittest.main()

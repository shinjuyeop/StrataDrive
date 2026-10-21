"""Bookkeeping tests; no SDK or root required. Run from a checkout without build/."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('someip_runner',ROOT/'tests/integration/someip/run.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)

class SomeipPilotTest(unittest.TestCase):
    def test_lock_without_build_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.assertFalse((root/'build').exists())
            with runner.open_lock(root) as f:self.assertTrue(f.writable())
            self.assertTrue((root/'build/.m4-exclusive.lock').exists())

    def test_remote_nodes_have_distinct_diagnosis_and_client_ids(self):
        a,b=runner.config('central'),runner.config('front')
        self.assertNotEqual(a['diagnosis'],b['diagnosis'])
        for c in (a,b):self.assertEqual(int(c['applications'][0]['id'],16)>>8,int(c['diagnosis'],16))
        self.assertNotEqual(a['network'],b['network'])

    def test_explicit_bounded_transport_and_no_aggregation(self):
        for role in ('central','front'):
            c=runner.config(role)
            self.assertEqual(c['max-payload-size-reliable'],512)
            self.assertEqual(c['endpoint-queue-limit-external'],8192)
            self.assertTrue(all(v==0 for v in c['npdu-default-timings'].values()))

    def test_exit_and_missing_summary_cannot_pass(self):
        s={'pass':True,'orderly_stop':True,'control_gate_open':False}
        self.assertTrue(runner.summary_ok({'exit':0,'summary':s}))
        for row in ({'exit':1,'summary':s},{'exit':0},{'exit':-9,'summary':s}):self.assertFalse(runner.summary_ok(row))

    def test_force_kill_is_not_orderly(self):
        self.assertFalse(runner.summary_ok({'exit':0,'summary':{'pass':True,'orderly_stop':False,'control_gate_open':False}}))

    def test_sanitizer_failures_not_waived(self):
        for s in ('WARNING: ThreadSanitizer: data race','FATAL: ThreadSanitizer: unexpected memory mapping',
                  'AddressSanitizer:DEADLYSIGNAL','LeakSanitizer: detected memory leaks','runtime error: misaligned'):
            self.assertTrue(runner.sanitizer_errors(s))
        self.assertFalse(runner.sanitizer_errors('normal output'))

    def test_early_namespace_failure_keeps_result_and_exit1(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(runner.subprocess,'check_output',side_effect=subprocess.CalledProcessError(1,['mount'])):
                self.assertEqual(runner.inside(Path(tmp),Path('/absent/pilot'),'normal'),1)
            result=json.loads((Path(tmp)/'result.json').read_text())
            self.assertFalse(result['pass']);self.assertIn('error',result)

    def test_actual_child_timeout_executes_cleanup_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)
            self.assertEqual(runner.supervise([sys.executable,'-c','import time; time.sleep(30)'],dest,.05),1)
            result=json.loads((dest/'supervisor-timeout.json').read_text())
            self.assertTrue(result['forced_cleanup']);self.assertEqual(result['child_exit'],-9)
            self.assertTrue((dest/'supervisor.txt').exists())

if __name__=='__main__':unittest.main()

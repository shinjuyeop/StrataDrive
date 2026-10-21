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
    def test_malformed_operating_results_are_errors_not_aggregation_exceptions(self):
        with patch.object(sys,'path',[str(RUNNER.parent),*sys.path]):
            module=runpy.run_path(str(RUNNER.parent/'check_dds_operating_profile.py'),run_name='diagnostic')
        with tempfile.TemporaryDirectory() as tmp:
            for result in (None,[],{}, {'processes':None},{'processes':[None]},
                           {'processes':[{}]}, {'processes':[{'role':'zone','epoch':True,'exit':0}]},
                           {'processes':[{'role':'zone','epoch':42,'exit':0,'summary':[]}]}):
                with self.subTest(result=result):
                    self.assertTrue(module['evidence_errors'](Path(tmp),{'case':'partial','config':'D'},result))

    def test_expected_peer_kill_and_process_failure_cannot_be_sanitizer_pass(self):
        with patch.object(sys,'path',[str(RUNNER.parent),*sys.path]):
            module=runpy.run_path(str(RUNNER.parent/'check_dds_operating_profile.py'),run_name='diagnostic')
        classify=module['sanitizer_verdict']
        for profile in ('asan-ubsan','tsan'):
            self.assertTrue(classify(profile,'peer-kill',False).startswith('INCOMPLETE'))
            self.assertEqual(classify(profile,'peer-kill',True),'FAIL')
            self.assertTrue(classify(profile,'normal',False,False).startswith('INCOMPLETE'))
            self.assertEqual(classify(profile,'normal',True),'FAIL')
            self.assertEqual(classify(profile,'normal',False),'PASS')

    def test_operating_campaign_build_failure_preserves_all_planned_rows(self):
        for readiness,count in ((False,38),(True,6)):
            with self.subTest(readiness=readiness),tempfile.TemporaryDirectory() as tmp:
                tmp=Path(tmp);compiler=tmp/'gcc';compiler.write_text('#!/bin/sh\nexit 7\n');compiler.chmod(0o755)
                self.assertFalse((tmp/'fresh-build').exists())
                command=[sys.executable,__file__,'--operating-build-failure',str(tmp/'out')]
                if readiness:command.append('--readiness')
                r=subprocess.run(command,cwd=ROOT,env={**os.environ,'PATH':str(tmp)+':'+os.environ['PATH']},capture_output=True,text=True,timeout=10)
                self.assertEqual(r.returncode,7,r.stderr)
                self.assertTrue((tmp/'fresh-build/.m4-exclusive.lock').is_file())
                rows=json.loads((tmp/'out/results.json').read_text())
                self.assertEqual(len(rows),count)
                self.assertTrue(all(row['verdict']=='NOT RUN' for row in rows))

    def test_readiness_timeout_kills_and_records_both_real_children(self):
        module=runpy.run_path(str(RUNNER),run_name='diagnostic')
        inside=module['inside'];real_popen=subprocess.Popen;children=[]
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            def launch(_command,**kwargs):
                child=real_popen([sys.executable,'-c','import time; time.sleep(60)'],**kwargs)
                children.append(child);return child
            def timeout(_predicate):
                module['wait_for'](lambda:False,seconds=.03)
            try:
                with patch('subprocess.run'),patch('subprocess.Popen',side_effect=launch),patch.dict(inside.__globals__,wait_for=timeout):
                    self.assertEqual(inside(folder,Path('/unused'),'normal'),1)
                result=json.loads((folder/'result.json').read_text())
                self.assertEqual(result['functional'],'FAIL')
                self.assertIn('TimeoutError',result['error'])
                self.assertEqual(len(children),2)
                self.assertEqual(len(result['processes']),2)
                for child,row in zip(children,result['processes']):
                    self.assertEqual(child.poll(),-9)
                    self.assertEqual(row['exit'],-9)
                    self.assertTrue(row['cleanup_after_error'])
                    self.assertIn('summary_error',row)
                    with self.assertRaises(ProcessLookupError):os.kill(child.pid,0)
            finally:
                for child in children:
                    if child.poll() is None:child.kill();child.wait()

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
            self.assertFalse((tmp/'fresh-build').exists())
            command=[sys.executable,__file__,'--build-failure',str(tmp/'out')]
            r=subprocess.run(command,cwd=ROOT,env={**os.environ,'PATH':str(tmp)+':'+os.environ['PATH']},capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode,7,r.stderr)
            self.assertTrue((tmp/'fresh-build/.m4-exclusive.lock').is_file())
            plan=json.loads((tmp/'out/plan.json').read_text())
            rows=json.loads((tmp/'out/results.json').read_text())
            self.assertEqual(len(rows),plan['lifecycle_runs']+plan['bucket_runs'])
            self.assertEqual(len(rows),24)
            self.assertTrue(all(row['verdict']=='NOT RUN' for row in rows))
            self.assertIn('deliberate compiler failure',(tmp/'out/build-0.log').read_text())

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--operating-build-failure':
        sys.path.insert(0,str(RUNNER.parent))
        import check_dds_operating_profile as operating
        sys.argv=[str(RUNNER.parent/'check_dds_operating_profile.py'),*sys.argv[2:]]
        # Isolate only the lock location; keep real source/protocol reads and
        # compiler-process failure. Never depend on or lock the user's build/.
        lock=Path(sys.argv[1]).parent/'fresh-build/.m4-exclusive.lock'
        with patch.object(operating.d,'sha',lambda _path:'mock SDK hash for bookkeeping fixture'),patch.object(operating.d,'BUILD_LOCK',lock):
            raise SystemExit(operating.main())
    elif len(sys.argv)>1 and sys.argv[1]=='--build-failure':
        module=runpy.run_path(str(RUNNER),run_name='diagnostic');main=module['main'];sys.argv=[str(RUNNER),sys.argv[2]]
        # These tests exercise process bookkeeping, not SDK availability/provenance.
        lock=Path(sys.argv[1]).parent/'fresh-build/.m4-exclusive.lock'
        with patch.dict(main.__globals__,sha=lambda _path:'mock SDK hash for bookkeeping fixture',BUILD_LOCK=lock):
            raise SystemExit(main())
    else:unittest.main()

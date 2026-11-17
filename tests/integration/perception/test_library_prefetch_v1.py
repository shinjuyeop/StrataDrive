import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from physical_ai.perception.library_prefetch_v1 import prefetch,READ_BUDGET_NS
from audit_library_prefetch_v1 import validate
from endurance_host_v1 import prefetch_pipeline_libraries
from control_shadow_capture_v1 import Capture


class LibraryPrefetchTests(unittest.TestCase):
    def test_standalone_auditor_help_without_repository_environment(self):
        script=Path(__file__).with_name('audit_library_prefetch_v1.py').resolve()
        with tempfile.TemporaryDirectory() as folder:
            env={k:v for k,v in os.environ.items() if k!='PYTHONPATH'}
            result=subprocess.run([sys.executable,str(script),'--help'],cwd=folder,
                                  env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('--run',result.stdout)

    def test_standalone_auditor_records_missing_run_failure(self):
        script=Path(__file__).with_name('audit_library_prefetch_v1.py').resolve()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);output=root/'audit.json'
            env={k:v for k,v in os.environ.items() if k!='PYTHONPATH'}
            result=subprocess.run([sys.executable,str(script),'--run',str(root),
                                   '--output',str(output)],cwd=root,env=env,
                                  capture_output=True,text=True)
            self.assertEqual(result.returncode,1,result.stderr)
            self.assertEqual(json.loads(output.read_text())['status'],'FAIL')
            self.assertNotIn('ModuleNotFoundError',result.stderr)

    def fixture(self,root):
        path=root/'lib.so.1';path.write_bytes(b'unchanged library fixture')
        item=dict(path=path.name,bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        spec=dict(schema='m10-inference-library-prefetch-v1',read_budget_ns=READ_BUDGET_NS,files=[item])
        manifest=root/'profile.json';manifest.write_text(json.dumps(spec))
        return manifest,spec,path

    def test_exact_reads_preserve_file_and_run_no_model(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);m,s,p=self.fixture(root);before=p.stat();report={}
            prefetch(m,root,report)
            self.assertEqual(report['status'],'PASS')
            self.assertEqual((report['model_calls'],report['control_writes']),(0,0))
            self.assertEqual(p.stat().st_mtime_ns,before.st_mtime_ns)
            self.assertEqual(validate(report,m.read_bytes(),report['end_wall_ns'])['files'],1)

    def test_manifest_rejects_escape_duplicates_and_unbounded_reads(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);m,s,p=self.fixture(root)
            for mutate in (lambda d:d['files'].append(copy.deepcopy(d['files'][0])),
                           lambda d:d['files'][0].update(path='../lib.so.1'),
                           lambda d:d['files'][0].update(path=str(p)),
                           lambda d:d['files'][0].update(bytes=4*1024**3),
                           lambda d:d.update(read_budget_ns=READ_BUDGET_NS+1)):
                spec=copy.deepcopy(s);mutate(spec);m.write_text(json.dumps(spec))
                with self.assertRaises(ValueError):prefetch(m,root,{})

    def test_changed_bytes_fail_even_with_same_length(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);m,s,p=self.fixture(root);p.write_bytes(b'x'*p.stat().st_size);report={}
            with self.assertRaisesRegex(ValueError,'content changed'):prefetch(m,root,report)
            self.assertEqual(report['status'],'FAIL');self.assertEqual(report['files'],[])

    def test_deadline_is_exclusive_and_clock_regression_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);m,s,p=self.fixture(root)
            for clock,error in ((iter([0,READ_BUDGET_NS]).__next__,TimeoutError),
                                (iter([10,9]).__next__,ValueError)):
                report={}
                with self.assertRaises(error):prefetch(m,root,report,clock=clock)
                self.assertEqual(report['status'],'FAIL')

    def test_default_does_no_library_io_and_invalid_option_fails(self):
        with patch.dict(os.environ,{},clear=True),patch('physical_ai.perception.library_prefetch_v1.prefetch') as read:
            report={};prefetch_pipeline_libraries(report);read.assert_not_called();self.assertEqual(report,{})
            os.environ['STRATADRIVE_M10_PREFETCH_LIBRARIES']='2'
            with self.assertRaises(ValueError):prefetch_pipeline_libraries(report)
            read.assert_not_called()

    def test_prefetch_failure_prevents_model_and_worker_construction(self):
        with tempfile.TemporaryDirectory() as folder:
            capture=Capture(SimpleNamespace(output=Path(folder),wall_clock=1));before=os.sched_getaffinity(0)
            try:
                with patch('control_shadow_capture_v1.prefetch_pipeline_libraries',side_effect=TimeoutError('library read deadline')),patch('control_shadow_capture_v1.pipeline_backend') as backend:
                    with self.assertRaises(TimeoutError):capture.attach(SimpleNamespace(id=1),None,None)
                    backend.assert_not_called();self.assertIsNone(capture.worker)
                    self.assertEqual(capture.report['observer_cpus_after_setup'],sorted(before))
            finally:capture.tx.close();capture.rx.close()

    def test_audit_rejects_changed_identity_late_read_or_hidden_model_call(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);m,s,p=self.fixture(root);report={};prefetch(m,root,report)
            for mutate in (lambda d:d.update(model_calls=1),
                           lambda d:d.update(manifest_sha256='0'*64),
                           lambda d:d['files'][0].update(sha256='0'*64),
                           lambda d:d.update(files=[]),
                           lambda d:d.update(end_wall_ns=d['begin_wall_ns']+READ_BUDGET_NS)):
                got=copy.deepcopy(report);mutate(got)
                with self.assertRaises(ValueError):validate(got,m.read_bytes(),max(report['end_wall_ns'],got['end_wall_ns']))
            with self.assertRaises(ValueError):validate(report,m.read_bytes(),report['begin_wall_ns']-1)

    def test_combined_audit_requires_both_recorded_prefetches(self):
        from audit_library_prefetch_v1 import audit
        from test_gc_recovery_v1 import GcRecoveryTests
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);run=root/'run';run.mkdir();GcRecoveryTests().fixture(run)
            m,s,p=self.fixture(root);report={};prefetch(m,root,report);end=report['end_wall_ns']
            server=json.loads((run/'server.json').read_text());server['prefetch_inference_libraries']=True
            (run/'server.json').write_text(json.dumps(server))
            owner=dict(library_prefetch=report,preparation=dict(started_wall_ns=end+1000))
            renderer=dict(library_prefetch=report,preparation=[dict(begin_ns=end+1000)])
            (run/'capture/perception.json').write_text(json.dumps(owner))
            target=run/'capture/paired/renderer/result.json';target.parent.mkdir(parents=True);target.write_text(json.dumps(renderer))
            with patch('audit_library_prefetch_v1.PROFILE',m):
                self.assertEqual(audit(run)['status'],'PASS_GC_RECOVERY_PREFETCH_INTEGRITY')
                renderer['library_prefetch']={};target.write_text(json.dumps(renderer))
                with self.assertRaises(ValueError):audit(run)

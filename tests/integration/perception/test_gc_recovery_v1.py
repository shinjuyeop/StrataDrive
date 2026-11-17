import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from audit_admission_window_v1 import validate_profile,validate_receipt
from audit_gc_recovery_v1 import audit
from audit_owner_three_v1 import PLAN,audit as prior_audit

class GcRecoveryTests(unittest.TestCase):
    def receipt(self):
        return dict(model_step_ns='5000000',admission_profile='whole-interval-v1',
            original_actual=dict(admitted_actual=dict(empty_init=False,normal=True,
                command_checked_through_ns='100000000',exclusive_expiry_ns='100300001',oldest_actuator_ns='70300000')))

    def profile(self):
        return dict(structured_state=True,incremental_purge_slice=True,recovery_preview=True,
            wall_preview_reserve_ns='300000',model_step_ns='5000000',admission_profile='whole-interval-v1')

    def test_three_tenths_ms_retains_exclusive_expiry_and_original_age(self):
        validate_profile(self.profile(),300_000);validate_receipt(self.receipt(),300_000)
        for reserve in (1_000_000,2_000_000):
            with self.assertRaises(ValueError):validate_profile(self.profile(),reserve)
        for key,value in [('exclusive_expiry_ns','100300000'),('oldest_actuator_ns','70299999')]:
            r=self.receipt();r['original_actual']['admitted_actual'][key]=value
            with self.assertRaises(ValueError):validate_receipt(r,300_000)
        for reserve in (0,299_999,500_000):
            with self.assertRaises(ValueError):validate_profile(self.profile(),reserve)

    def fixture(self,run):
        processes=[dict(role=role,affinity=PLAN['observer' if role=='client' else role],scheduler=0,priority=0)
                   for role in ('owner','renderer','client')]
        processes += [dict(role='client/child',affinity=PLAN['native'],scheduler=1,priority=18),
                      dict(role='client/child',affinity=PLAN['renderer'],scheduler=0,priority=0)]
        server=dict(profile_owner_gc=True,profile_state_path=True,owner_purge_slice=True,owner_recovery_preview=True,
            endurance_seconds=30,host_resources=dict(cpus=copy.deepcopy(PLAN)),resources=[dict(wall_ns=100,processes=processes)],
            argv=dict(owner=['-StrataM10GcProfile','-StrataM10PurgeSlice','-StrataM10RecoveryPreview'],renderer=[]))
        result=dict(binding=self.profile(),final_server=self.profile(),requested_intervals=1)
        files={'server.json':server,'capture/result.json':result,'capture/native.json':dict(initial=100),
            'capture/owner-gc.json':dict(errors=0,active=False,parallel=1,period_seconds=61.1,cycles=[],
                incremental_purge=dict(enabled=True,budget_ns=100_000,errors=0,cycles=[]))}
        for name,data in files.items():
            p=run/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data))
        with gzip.open(run/'capture/trace.jsonl.gz','wt') as stream:stream.write(json.dumps(dict(receipt=self.receipt()))+'\n')
        return files

    def test_explicit_owner_only_selection_and_actual_readback(self):
        with tempfile.TemporaryDirectory() as folder:
            run=Path(folder);files=self.fixture(run)
            self.assertEqual(audit(run)['status'],'PASS_GC_RECOVERY_PREVIEW_INTEGRITY')
            with self.assertRaises(ValueError):prior_audit(run)
            mutations=[('server.json',lambda d:d.update(owner_recovery_preview=False)),
                ('server.json',lambda d:d.update(owner_recovery_preview='true')),
                ('server.json',lambda d:d['argv']['renderer'].append('-StrataM10RecoveryPreview')),
                ('server.json',lambda d:d['argv']['owner'].remove('-StrataM10RecoveryPreview')),
                ('capture/result.json',lambda d:d['binding'].update(recovery_preview=False)),
                ('capture/result.json',lambda d:d['final_server'].update(recovery_preview=1)),
                ('capture/result.json',lambda d:d['final_server'].update(wall_preview_reserve_ns='1000000'))]
            for name,mutate in mutations:
                with self.subTest(name=name,mutation=mutate):
                    data=copy.deepcopy(files[name]);mutate(data);(run/name).write_text(json.dumps(data))
                    with self.assertRaises(ValueError):audit(run)
                    (run/name).write_text(json.dumps(files[name]))

    def test_recovery_option_does_not_allow_overlap_or_short_physics(self):
        with tempfile.TemporaryDirectory() as folder:
            run=Path(folder);files=self.fixture(run)
            server=copy.deepcopy(files['server.json']);server['host_resources']['cpus']['renderer'].append(4)
            (run/'server.json').write_text(json.dumps(server))
            with self.assertRaises(ValueError):audit(run)
            (run/'server.json').write_text(json.dumps(files['server.json']))
            r=self.receipt();r['model_step_ns']='4000000'
            with gzip.open(run/'capture/trace.jsonl.gz','wt') as stream:stream.write(json.dumps(dict(receipt=r))+'\n')
            with self.assertRaises(ValueError):audit(run)

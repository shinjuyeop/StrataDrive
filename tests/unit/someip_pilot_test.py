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


class SomeipAdapterBookkeepingTest(unittest.TestCase):
    def test_complete_binding_contract_without_sdk_or_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary=Path(tmp)/'binding'
            subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror',str(ROOT/'tests/integration/someip/binding_check.cpp'),'-o',str(binary)],check=True,capture_output=True)
            r=subprocess.run([str(binary)],check=True,capture_output=True,text=True)
            self.assertIn('4274 binding assertions passed',r.stdout)

    def test_attempt02_cohort_exclusion_preserves_individual_exit(self):
        rows=json.loads((ROOT/'docs/test-plan/evidence/m5_someip_pilot/results-summary.json').read_text())
        cohort=next(c for c in rows if c['cohort']=='attempt-02')
        self.assertFalse(cohort['cohort_eligible'])
        self.assertEqual(len(cohort['cases']),10)
        self.assertTrue(all(c['exit']==0 and not c['eligible_case_result'] for c in cohort['cases']))
        ready=next(c for c in cohort['cases'] if c['case']=='ready-timeout')
        self.assertTrue(ready['individual_observed_pass'])

    def test_build_obeys_same_exclusive_lock_before_mutation(self):
        # Use a temporary checkout-shaped root; no existing SDK/build is needed.
        import shutil, fcntl
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);dest=root/'tests/integration/someip';dest.mkdir(parents=True)
            for name in ('build.py','run.py'):shutil.copy2(ROOT/'tests/integration/someip'/name,dest/name)
            with runner.open_lock(root) as lock:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                p=subprocess.run([sys.executable,str(dest/'build.py'),'normal'],capture_output=True,text=True)
            self.assertNotEqual(p.returncode,0)
            self.assertIn('BlockingIOError',p.stderr)
            self.assertFalse((root/'build/m5-someip-deps').exists())

    def test_pilot_locks_before_reading_binary_identity(self):
        import shutil, fcntl
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);dest=root/'tests/integration/someip';dest.mkdir(parents=True)
            shutil.copy2(ROOT/'tests/integration/someip/run.py',dest/'run.py')
            with runner.open_lock(root) as lock:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                p=subprocess.run([sys.executable,str(dest/'run.py'),str(root/'result'),'--cases','normal'],capture_output=True,text=True)
            self.assertNotEqual(p.returncode,0);self.assertIn('BlockingIOError',p.stderr)
            self.assertNotIn('FileNotFoundError',p.stderr)

    def test_adapter_failure_cleanup_cannot_create_pass(self):
        import importlib.util
        path=ROOT/'tests/integration/someip'
        with mock.patch.dict(sys.modules,{'run':runner}), mock.patch.object(sys,'path',[str(path),*sys.path]):
            spec=importlib.util.spec_from_file_location('front_runner',path/'front_run.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(module.subprocess,'check_output',side_effect=subprocess.CalledProcessError(1,['mount'])):
                self.assertEqual(module.inside(Path(tmp),Path('/absent/adapter'),'normal'),1)
            self.assertFalse(json.loads((Path(tmp)/'result.json').read_text())['pass'])
        a=module.config('front',1);b=module.config('front',2)
        self.assertNotEqual(a['applications'][0]['id'],b['applications'][0]['id'])
        self.assertEqual([s['reliable']['port'] for s in a['services']],[30501,30502])
        self.assertEqual([s['reliable']['port'] for s in module.config('central')['services']],[30503,30504])

    def test_preinjection_protection_or_exit_fails_without_waiting_for_timeout(self):
        import importlib.util
        path=ROOT/'tests/integration/someip'
        with mock.patch.dict(sys.modules,{'run':runner}), mock.patch.object(sys,'path',[str(path),*sys.path]):
            spec=importlib.util.spec_from_file_location('front_runner_precondition',path/'front_run.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);central=mock.Mock();central.poll.return_value=None
            self.assertFalse(module.normal_prerequisite(d,central))
            (d/'control-established').touch();self.assertTrue(module.normal_prerequisite(d,central))
            for role in ('front','central','rear'):
                p=d/(role+'-protected');p.write_text('1')
                with self.assertRaisesRegex(RuntimeError,'before declared injection'):module.normal_prerequisite(d,central)
                p.unlink()
            central.poll.return_value=1
            with self.assertRaisesRegex(RuntimeError,'exited'):module.normal_prerequisite(d,central)

class ThreeEcuBookkeepingTest(unittest.TestCase):
    def test_three_routes_do_not_reuse_endpoint_or_routing_resources(self):
        path=ROOT/'tests/integration/someip'
        with mock.patch.dict(sys.modules,{'run':runner}),mock.patch.object(sys,'path',[str(path),*sys.path]):
            spec=importlib.util.spec_from_file_location('three_runner',path/'front_run.py')
            m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        configs=[m.config(r,1,True) for r in ('central','front','rear')]
        for field in ('network','unicast','routing','diagnosis'):self.assertEqual(len({c[field] for c in configs}),3)
        services=[x for c in configs for x in c['services']]
        self.assertEqual(len({x['service'] for x in services}),8)
        self.assertEqual(len({x['reliable']['port'] for x in services}),8)
        for c in configs:
            self.assertEqual(int(c['applications'][0]['id'],16)>>8,int(c['diagnosis'],16))
            self.assertEqual(c['endpoint-queue-limit-external'],8192)
        self.assertNotEqual(m.config('rear',1,True)['applications'][0]['id'],m.config('rear',2,True)['applications'][0]['id'])

    def test_missing_rear_evidence_is_failure(self):
        path=ROOT/'tests/integration/someip'
        with mock.patch.object(sys,'path',[str(path),*sys.path]):
            spec=importlib.util.spec_from_file_location('rear_oracle',path/'rear_oracle.py')
            m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(m.rear_oracle(Path(tmp),'normal',{})['pass'])

    def test_paused_consumer_overflow_requires_prior_independent_fault(self):
        path=ROOT/'tests/integration/someip'
        with mock.patch.object(sys,'path',[str(path),*sys.path]):
            spec=importlib.util.spec_from_file_location('rear_oracle_overflow',path/'rear_oracle.py')
            m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        summary={'overflow':True,'rx_overflow_ns':110,'authority_highwater':8,'authority_rejected':3}
        watch={'fault_ns':105}
        self.assertTrue(m.expected_paused_overflow('owner-pause','rear','rear',summary,watch,100))
        for case,role,target,s,w in [('normal','rear','rear',summary,watch),('owner-pause','front','rear',summary,watch),('owner-pause','rear','rear',summary,{'fault_ns':115}),('owner-pause','rear','rear',dict(summary,authority_rejected=0),watch)]:
            self.assertFalse(m.expected_paused_overflow(case,role,target,s,w,100))

class SdkOutcomeTest(unittest.TestCase):
    def test_only_exact_injected_lease_loss_with_protection_and_rejoin_is_expected(self):
        import importlib.util
        from datetime import datetime
        spec=importlib.util.spec_from_file_location('sdk_outcomes',ROOT/'tests/integration/someip/sdk_outcomes.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        line='2026-10-21 16:34:40.275379 central [error] tcei::write_completion_condition: Connection reset by peer(104) bytes transferred: 0 bytes to sent: 101 remote:10.88.0.2:30502 (1311): [5345.0050.0140]'
        wall=int(datetime(2026,10,21,16,34,40,275379).timestamp()*1e9)
        result={'case':'restart-live','injected_crash':{'role':'front','generation':1,'ns':1_000_000_000},
                'surviving_central_rejoined':True,'clock_sample':{'monotonic_ns':1_001_000_000,'wall_ns':wall,'utc_offset_s':datetime.now().astimezone().utcoffset().total_seconds()},
                'processes':[{'role':'front','generation':1,'expected_abrupt_stop':True},
                             {'role':'central','summary':{'pass':True,'epoch':2,'release_ack_mask':255,'diagnostic_rejected':1,'batches':24}}]}
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);(folder/'central-protected').write_text('1020000000')
            (folder/'central-1.events.csv').write_text('ns,event,epoch,role,value,deadline\n990000000,credit-issued,1,7,12,1050000000\n')
            self.assertIsNotNone(module.expected_injected_lease_reset(line,'central-1.stdout',result,folder))
            for changed in (dict(result,case='normal'),dict(result,surviving_central_rejoined=False),dict(result,injected_crash={})):
                self.assertIsNone(module.expected_injected_lease_reset(line,'central-1.stdout',changed,folder))
            for bad in (line.replace('0050','0020'),line.replace('101','102'),line.replace('30502','30501'),line.replace('104','32')):
                self.assertIsNone(module.expected_injected_lease_reset(bad,'central-1.stdout',result,folder))
            (folder/'central-protected').write_text('1200000000')
            self.assertIsNone(module.expected_injected_lease_reset(line,'central-1.stdout',result,folder))

class RenewalBookkeepingTest(unittest.TestCase):
    def test_actual_leaf_gap_missing_and_expiry_mutation_fail(self):
        spec=importlib.util.spec_from_file_location('renewal_oracle',ROOT/'tests/integration/someip/renewal_oracle.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        import csv
        def fixture(d,late=False,missing=False,mutate=False):
            with (d/'central-1.transport.csv').open('w') as f:
                f.write('event,epoch,payload_source,operation,peer,inner_deadline,sent,deadline\n')
                for i in range(10):
                    for peer in (0,1):f.write(f'central-enqueued,1,{100+i*10},3,{peer},{130+i*10},{100+i*10},{120+i*10}\n')
            for role,owners in [('front',(2,3)),('central',(4,))]:
                with (d/(role+'-1.leaf-events.csv')).open('w') as f:
                    f.write('event,ns,owner,epoch,source,deadline,detail\n')
                    for owner in owners:
                        for i in range(10):
                            if missing and owner==2 and i==5:continue
                            ns=100+i*10+(31 if late and i==9 else 1)
                            f.write(f'valid-input,{ns},{owner},1,{100+i*10},{130+i*10+(1 if mutate else 0)},1\n')
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);fixture(d);self.assertTrue(m.renewal_oracle(d)['pass'])
            for bad in ('late','missing','mutate'):
                fixture(d,**{bad:True});self.assertFalse(m.renewal_oracle(d)['pass'])
            (d/'front-1.leaf-events.csv').unlink();self.assertFalse(m.renewal_oracle(d)['pass'])

    def test_three_ecu_token_path_and_front_result_order_are_required(self):
        spec=importlib.util.spec_from_file_location('renewal_oracle',ROOT/'tests/integration/someip/renewal_oracle.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        import csv
        fields=['event','ns','epoch','token','payload_source','operation','peer','original_source','inner_deadline','sent','deadline']
        def fixture(d,bad=None):
            central=[];peers={'front':[],'rear':[]}
            for i in range(10):
                t=100+i*10
                for peer in (0,1):
                    request=dict(zip(fields,['central-enqueued',t+peer,1,i*2+peer+1,t,3,peer,t-2,t+30,t+peer,t+20+peer]))
                    central.append(request)
                    central.append(dict(request,event='central-result-accepted',ns=t+1+peer))
                    role='front' if peer==0 else 'rear'
                    peers[role].append(dict(request,event='zone-received',ns=t+2))
                    for owner in ((2,3) if peer==0 else (4,)):
                        peers[role].append(dict(request,event='zone-leaf-enqueued',ns=t+3,peer=owner,operation=0))
            if bad=='token':peers['rear'][0]['token']=999
            if bad=='source':peers['rear'][0]['original_source']=0
            if bad=='order':central[1]['ns']=110
            if bad=='missing':central=[r for r in central if not(r['event']=='central-result-accepted' and r['token']==2)]
            for name,rows in [('central',central),*peers.items()]:
                with (d/(name+'-1.transport.csv')).open('w') as f:
                    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
            for name,owners in [('front',(2,3)),('rear',(4,))]:
                with (d/(name+'-1.leaf-events.csv')).open('w') as f:
                    f.write('event,ns,owner,epoch,source,deadline,detail\n')
                    for owner in owners:
                        for i in range(10):f.write(f'valid-input,{104+i*10},{owner},1,{100+i*10},{130+i*10},1\n')
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);fixture(d);self.assertTrue(m.renewal_oracle(d,three=True)['pass'])
            for bad in ('token','source','order','missing'):
                fixture(d,bad);self.assertFalse(m.renewal_oracle(d,three=True)['pass'],bad)

class NativeWatchBookkeepingTest(unittest.TestCase):
    def module(self):
        spec=importlib.util.spec_from_file_location('native_oracle',ROOT/'tests/integration/someip/native_oracle.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

    def fixture(self,folder):
        for role,owner,cpu in [('central',7,1),('front',0,2),('plant',8,3)]:
            info={'origin':900000000,'quiesced':1010000000,'fault_ns':0,'fault_deadline':0,'monitor':{'policy':0,'priority':0,'allowed_cpus':[0]},'owner':{'policy':0,'priority':0,'allowed_cpus':[cpu]}}
            (folder/f'{role}-1.native.watch.json').write_text(json.dumps(info))
            (folder/f'{role}-1.native.watch.csv').write_text('owner,slot,release,deadline,start,end,cpu,detected,requested\n'+f'{owner},0,1000000000,1004000000,1000010000,1000020000,1000,0,1000000000\n')
            (folder/f'{role}.runtime.json').write_text(json.dumps({'pid':100,'threads':[{'tid':100,'affinity':[cpu],'policy':0,'priority':0},{'tid':101,'affinity':[0],'policy':0,'priority':0}]}))

    def test_normal_deadline_miss_is_not_protection_success(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);self.fixture(d);self.assertTrue(m.native_oracle(d,'late',{},False)['pass'])
            p=d/'front-1.native.watch.csv';p.write_text(p.read_text().replace('1000020000','1005000000'))
            r=m.native_oracle(d,'late',{'protected':True},False)
            self.assertFalse(r['pass']);self.assertFalse(r['normal_timing_ok'])

    def test_wrong_requested_slot_cannot_hide_a_delayed_wake(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);self.fixture(d);p=d/'front-1.native.watch.csv'
            p.write_text(p.read_text().replace('1000,0,1000000000','1000,0,998000000'))
            self.assertFalse(m.native_oracle(d,'late',{},False)['pass'])

    def test_missing_watch_or_wrong_actual_policy_fails(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);self.fixture(d)
            self.assertFalse(m.native_oracle(d,'normal',{},True)['pass'])
            (d/'front.runtime.json').unlink()
            self.assertFalse(m.native_oracle(d,'late',{},False)['pass'])

    def test_full_queue_without_real_extra_rejection_is_not_overflow(self):
        m=self.module();f={'rx_highwater':8,'overflow':True,'rx_rejected':1,'rx_overflow_token':1000000008,'fifo_preserved':True,'overflow_drained':8,'unprocessed_rejected':8,'rx_overflow_ns':10,'pre_shutdown_protection':11,'selected_ns':12}
        c={'diagnostic_sent':8,'diagnostic_rejected':0,'diagnostic_expired':8}
        self.assertTrue(m.overflow_counters_ok(f,c,True))
        for bad in (dict(f,overflow=False),dict(f,rx_rejected=0),dict(f,fifo_preserved=False),dict(f,pre_shutdown_protection=9),dict(f,overflow_drained=7)):
            self.assertFalse(m.overflow_counters_ok(bad,c,True))
        self.assertFalse(m.overflow_counters_ok(f,dict(c,diagnostic_expired=7),True))

if __name__=='__main__':unittest.main()

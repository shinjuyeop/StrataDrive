import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from audit_owner_four_v1 import PLAN
from audit_owner_three_v1 import PLAN as THREE,validate_placement
from audit_owner_gc_v1 import declared_owner_cpus,validate
from endurance_host_v1 import validate as validate_plan

class OwnerFourTests(unittest.TestCase):
    def fixture(self,plan=PLAN):
        rows=[dict(role=role,affinity=plan['observer' if role=='client' else role],scheduler=0,priority=0)
              for role in ('owner','renderer','client')]
        rows += [dict(role='client/child',affinity=plan['native'],scheduler=1,priority=18),
                 dict(role='client/child',affinity=plan['renderer'],scheduler=0,priority=0)]
        return dict(host_resources=dict(cpus=copy.deepcopy(plan)),endurance_seconds=30,
                    resources=[dict(wall_ns=100,processes=rows)])

    def test_disjoint_profile_transfers_one_complete_core(self):
        root=Path(__file__).resolve().parents[3]
        plan=json.loads((root/'profiles/perception-endurance-host-v5.json').read_text())['cpus']
        self.assertEqual(plan,PLAN)
        self.assertEqual(validate_plan(plan,set(range(16)),{c:(0,c%8) for c in range(16)}),plan)
        self.assertEqual(set(plan['owner'])-set(THREE['owner']),{5,13})
        self.assertEqual(set(THREE['renderer'])-set(plan['renderer']),{5,13})
        self.assertEqual(declared_owner_cpus(self.fixture()),tuple(PLAN['owner']))
        for mutate in (lambda p:p['renderer'].append(5),lambda p:p['owner'].append(0),lambda p:p.update(native=[0,8])):
            bad=self.fixture();mutate(bad['host_resources']['cpus'])
            with self.assertRaises(ValueError):declared_owner_cpus(bad)

    def test_actual_placement_and_scheduler_remain_required(self):
        good=self.fixture()
        self.assertEqual(validate_placement(good,100,PLAN),dict(owner=1,renderer=1,client=1,native=1,pipeline=1))
        for mutate in (lambda s:s['resources'][-1]['processes'][0].update(affinity=THREE['owner']),
                       lambda s:s['resources'][-1]['processes'][1].update(affinity=THREE['renderer']),
                       lambda s:s['resources'][-1]['processes'][2].update(affinity=[1,9]),
                       lambda s:s['resources'][-1]['processes'][3].update(priority=17),
                       lambda s:s['resources'][-1]['processes'][4].update(affinity=THREE['renderer']),
                       lambda s:s.update(resources=[])):
            bad=copy.deepcopy(good);mutate(bad)
            with self.assertRaises(ValueError):validate_placement(bad,100,PLAN)

    def test_three_core_default_does_not_accept_four_core_case(self):
        self.assertEqual(validate_placement(self.fixture(THREE),100)['owner'],1)
        with self.assertRaises(ValueError):validate_placement(self.fixture(),100)
        with self.assertRaises(ValueError):validate_placement(self.fixture(THREE),100,PLAN)

    def test_gc_journal_cannot_report_an_image_core(self):
        def stamp(t):return dict(wall_ns=t,cpu_ns=t,voluntary=0,involuntary=0,minor_faults=0,major_faults=0,processor=5,valid=1)
        p=dict(errors=0,active=False,parallel=1,period_seconds=61.1,cycles=[dict(completed_frame=10,begin=stamp(10),memory_trim=stamp(15),end=stamp(20))])
        self.assertEqual(len(validate(p,False,tuple(PLAN['owner']))),1)
        with self.assertRaises(ValueError):validate(p,False,tuple(THREE['owner']))
        p['cycles'][0]['end']['processor']=6
        with self.assertRaises(ValueError):validate(p,False,tuple(PLAN['owner']))

    def test_model_setup_uses_exact_two_image_core_mask(self):
        root=Path(__file__).resolve().parents[3];path=root/'docs/test-plan/evidence/m10_gc_owner4_v1/audit-workspace.py'
        spec=importlib.util.spec_from_file_location('owner_four_workspace',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        prep=dict(state='READY',calls=[dict(elapsed_wall_ns=10_000_000)]*3,started_wall_ns=1,finished_wall_ns=30_000_001)
        owner=dict(tensor_workspace=True,model_setup_cpus=PLAN['renderer'],observer_cpus_after_setup=PLAN['observer'],preparation_thread_overrides=dict(cv=4,resize=4),preparation=prep,preparation_final=copy.deepcopy(prep))
        renderer=dict(host_pipeline=dict(tensor_workspace=True,cv_threads=4,resize_threads=4),errors=[],preparation=[{},{},{}])
        with tempfile.TemporaryDirectory() as folder:
            run=Path(folder);(run/'capture/paired/renderer').mkdir(parents=True)
            (run/'server.json').write_text(json.dumps(dict(tensor_workspace=True)))
            target=run/'capture/perception.json';target.write_text(json.dumps(owner))
            (run/'capture/paired/renderer/result.json').write_text(json.dumps(renderer))
            self.assertEqual(module.audit(run)['model_cpus'],PLAN['renderer'])
            owner['model_setup_cpus']=THREE['renderer'];target.write_text(json.dumps(owner))
            with self.assertRaises(ValueError):module.audit(run)

    def test_standalone_auditor_without_repository_environment(self):
        script=Path(__file__).with_name('audit_owner_four_v1.py').resolve()
        with tempfile.TemporaryDirectory() as folder:
            run=Path(folder);output=run/'audit.json';env={k:v for k,v in os.environ.items() if k!='PYTHONPATH'}
            result=subprocess.run([sys.executable,str(script),'--help'],cwd=run,env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            result=subprocess.run([sys.executable,str(script),'--run',str(run),'--output',str(output)],cwd=run,env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,1,result.stderr)
            self.assertEqual(json.loads(output.read_text())['status'],'FAIL')
            self.assertNotIn('ModuleNotFoundError',result.stderr)

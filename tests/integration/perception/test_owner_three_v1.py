import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from audit_owner_gc_v1 import declared_owner_cpus,validate
from audit_owner_three_v1 import PLAN,validate_placement
from endurance_host_v1 import validate as validate_plan

class OwnerThreeTests(unittest.TestCase):
    def test_workspace_preparation_uses_three_image_cores(self):
        root=Path(__file__).resolve().parents[3]
        path=root/'docs/test-plan/evidence/m10_gc_owner3_v1/audit-workspace.py'
        spec=importlib.util.spec_from_file_location('owner_three_workspace',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        prep=dict(state='READY',calls=[dict(elapsed_wall_ns=10_000_000)]*3,
                  started_wall_ns=1,finished_wall_ns=30_000_001)
        owner=dict(tensor_workspace=True,model_setup_cpus=PLAN['renderer'],
                   observer_cpus_after_setup=PLAN['observer'],preparation_thread_overrides=dict(cv=4,resize=4),
                   preparation=prep,preparation_final=copy.deepcopy(prep))
        renderer=dict(host_pipeline=dict(tensor_workspace=True,cv_threads=4,resize_threads=4),
                      errors=[],preparation=[{}, {}, {}])
        with tempfile.TemporaryDirectory() as folder:
            run=Path(folder);(run/'capture/paired/renderer').mkdir(parents=True)
            (run/'server.json').write_text(json.dumps(dict(tensor_workspace=True)))
            target=run/'capture/perception.json';target.write_text(json.dumps(owner))
            (run/'capture/paired/renderer/result.json').write_text(json.dumps(renderer))
            self.assertEqual(module.audit(run)['model_cpus'],PLAN['renderer'])
            owner['model_setup_cpus']=[4,5,6,7,12,13,14,15]
            target.write_text(json.dumps(owner))
            with self.assertRaises(ValueError):module.audit(run)

    def fixture(self):
        rows=[dict(role=role,affinity=PLAN['observer' if role=='client' else role],scheduler=0,priority=0)
              for role in ('owner','renderer','client')]
        rows += [dict(role='client/child',affinity=PLAN['native'],scheduler=1,priority=18),
                 dict(role='client/child',affinity=PLAN['renderer'],scheduler=0,priority=0)]
        return dict(host_resources=dict(cpus=copy.deepcopy(PLAN)),endurance_seconds=30,
                    resources=[dict(wall_ns=100,processes=rows)])

    def test_profile_keeps_smt_pairs_and_native_observer_isolation(self):
        root=Path(__file__).resolve().parents[3]
        plan=json.loads((root/'profiles/perception-endurance-host-v4.json').read_text())['cpus']
        self.assertEqual(plan,PLAN)
        self.assertEqual(validate_plan(plan,set(range(16)),{c:(0,c%8) for c in range(16)}),plan)
        self.assertEqual(declared_owner_cpus(self.fixture()),tuple(PLAN['owner']))
        for mutate in [lambda p:p['owner'].append(0),lambda p:p['renderer'].append(4),lambda p:p.update(native=[0,8])]:
            server=self.fixture();mutate(server['host_resources']['cpus'])
            with self.assertRaises(ValueError):declared_owner_cpus(server)

    def test_actual_placement_is_required_after_startup(self):
        good=self.fixture();self.assertEqual(validate_placement(good,100),dict(owner=1,renderer=1,client=1,native=1,pipeline=1))
        # The first observer snapshot may precede exec-time taskset; it is not a
        # measured sample and must not replace validation of actual runtime masks.
        good['resources'].insert(0,dict(wall_ns=99,processes=[dict(role='client',affinity=list(range(16)),scheduler=0,priority=0)]))
        self.assertEqual(validate_placement(good,100)['client'],1)
        for mutate in [lambda s:s['resources'][-1]['processes'][0].update(affinity=[2,3,10,11]),
                       lambda s:s['resources'][-1]['processes'][1].update(affinity=[4,5,6,7,12,13,14,15]),
                       lambda s:s['resources'][-1]['processes'][2].update(affinity=[1,9]),
                       lambda s:s['resources'][-1]['processes'][3].update(priority=17),
                       lambda s:s['resources'][-1]['processes'][4].update(affinity=[4,5,6,7,12,13,14,15]),
                       lambda s:s['resources'][-1]['processes'][0].update(scheduler=2,priority=8),
                       lambda s:s.update(resources=[]),lambda s:s['host_resources'].update(owner_scheduler={'policy':'SCHED_RR','priority':8})]:
            bad=copy.deepcopy(good);mutate(bad)
            with self.assertRaises(ValueError):validate_placement(bad,100)

    def test_gc_observation_must_match_explicit_owner_cores(self):
        def stamp(t):return dict(wall_ns=t,cpu_ns=t,voluntary=0,involuntary=0,minor_faults=0,major_faults=0,processor=4,valid=1)
        profile=dict(errors=0,active=False,parallel=1,period_seconds=61.1,cycles=[dict(completed_frame=10,begin=stamp(10),memory_trim=stamp(15),end=stamp(20))])
        with self.assertRaises(ValueError):validate(profile,False)
        self.assertEqual(len(validate(profile,False,tuple(PLAN['owner']))),1)
        profile['cycles'][0]['end']['processor']=5
        with self.assertRaises(ValueError):validate(profile,False,tuple(PLAN['owner']))

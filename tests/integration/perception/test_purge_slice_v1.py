import copy
import gzip
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from audit_purge_slice_v1 import audit, validate_purge

class PurgeSliceTests(unittest.TestCase):
    def test_short_run_record_shape_and_actual_configuration(self):
        server=dict(profile_owner_gc=True,profile_state_path=True,owner_purge_slice=True,
                    endurance_seconds=30,argv=dict(owner=['-StrataM10GcProfile','-StrataM10PurgeSlice'],renderer=[]))
        server['host_resources']=dict(cpus=dict(owner=[2,3,10,11],native=[1,9],renderer=[4,5,6,7,12,13,14,15],observer=[0,8]))
        binding=dict(structured_state=True,incremental_purge_slice=True,wall_preview_reserve_ns='1000000',
                     model_step_ns='5000000',admission_profile='whole-interval-v1')
        receipt=dict(model_step_ns='5000000',admission_profile='whole-interval-v1',
                     original_actual=dict(admitted_actual=dict(empty_init=False,normal=True,
                        command_checked_through_ns='100000000',exclusive_expiry_ns='101000001',oldest_actuator_ns='71000000')))
        profile=self.profile();profile['cycles']=[];profile['incremental_purge']['cycles']=[]
        with tempfile.TemporaryDirectory() as folder:
            run=Path(folder);(run/'capture').mkdir()
            (run/'server.json').write_text(json.dumps(server))
            (run/'capture/owner-gc.json').write_text(json.dumps(profile))
            result=dict(binding=binding,final_server=dict(binding),requested_intervals=1)
            target=run/'capture/result.json';target.write_text(json.dumps(result))
            with gzip.open(run/'capture/trace.jsonl.gz','wt') as stream:stream.write(json.dumps(dict(receipt=receipt))+'\n')
            self.assertEqual(audit(run)['status'],'PASS_PURGE_SLICE_INTEGRITY')
            for side in ('binding','final_server'):
                bad=copy.deepcopy(result);bad[side]['incremental_purge_slice']=False
                target.write_text(json.dumps(bad))
                with self.assertRaises(ValueError):audit(run)
            target.write_text(json.dumps(result));server['argv']['renderer'].append('-StrataM10PurgeSlice')
            (run/'server.json').write_text(json.dumps(server))
            with self.assertRaises(ValueError):audit(run)

    def profile(self):
        def stamp(t):
            return dict(wall_ns=t,cpu_ns=t,voluntary=0,involuntary=0,minor_faults=0,major_faults=0,processor=2,valid=1)
        return dict(errors=0,active=False,parallel=1,period_seconds=61.1,
            cycles=[dict(completed_frame=10,begin=stamp(10),memory_trim=stamp(15),end=stamp(20)),
                    dict(completed_frame=12230,begin=stamp(100),memory_trim=stamp(105),end=stamp(110))],
            incremental_purge=dict(enabled=True,budget_ns=100000,errors=0,cycles=[
                dict(pending_at_collection_end=True,complete=True,first_frame=12,last_frame=13,first=stamp(30),last=stamp(60),
                     work=dict(count=2,wall_ns=20,cpu_ns=20,errors=0,longest_begin=stamp(30),longest_end=stamp(40))),
                dict(pending_at_collection_end=True,complete=True,first_frame=12232,last_frame=12232,first=stamp(120),last=stamp(130),
                     work=dict(count=1,wall_ns=10,cpu_ns=10,errors=0,longest_begin=stamp(120),longest_end=stamp(130)))]))

    def test_rejects_hidden_or_unfinished_purge_and_changed_cadence(self):
        self.assertEqual(len(validate_purge(self.profile())),2)
        for change in [lambda p:p['incremental_purge'].update(enabled=False),
                       lambda p:p['incremental_purge'].update(budget_ns=2000000),
                       lambda p:p['incremental_purge'].update(errors=1),
                       lambda p:p['incremental_purge']['cycles'][0].update(complete=False),
                       lambda p:p['incremental_purge']['cycles'][0].update(last_frame=14),
                       lambda p:p['cycles'][1].update(completed_frame=12231),
                       lambda p:p['incremental_purge']['cycles'][0].update(pending_at_collection_end=False),
                       lambda p:p['incremental_purge']['cycles'][0]['work'].update(errors=1),
                       lambda p:p['incremental_purge']['cycles'][0]['last'].update(wall_ns=101),
                       lambda p:p['incremental_purge']['cycles'].pop()]:
            profile=self.profile();change(profile)
            with self.assertRaises(ValueError):validate_purge(profile)

    def test_cpp_once_per_frame_progress_completion_and_bounded_journal(self):
        root=Path(__file__).resolve().parents[3]
        source=r'''#include "gc_profile.hpp"
#include <cassert>
using namespace stratadrive::m7_native;
int main(){
 PurgeProfile p{};unsigned calls=0,delays=0;bool pending=true;OwnerStamp t{};t.valid=1;
 auto step=[&](unsigned frame){p.step(frame,[&]{return pending;},[&]{++calls;},[&]{++delays;},[&]{t.wall+=10;t.cpu+=10;return t;});};
 step(1);assert(!calls && !delays); // no observed GC: engine owns startup
 p.collection_end(true);step(2);step(2);assert(calls==1 && delays==1 && !p.cycles[0].complete);
 p.step(3,[&]{return pending;},[&]{++calls;pending=false;},[&]{++delays;},[&]{t.wall+=10;t.cpu+=10;return t;});
 assert(p.cycles[0].complete && calls==2 && delays==2 && p.cycles[0].work.count==2);
 step(4);assert(calls==2 && delays==2); // nothing pending: never suppress collection
 p.collection_end(false);step(5);assert(calls==2 && delays==2 && !p.errors);
 p={};p.collection_end(true);pending=false;step(6);assert(p.errors==1); // cannot silently lose work
 p={};p.collection_end(true);p.collection_end(true);assert(p.errors==1);
 p={};for(unsigned i=0;i<64;++i)p.collection_end(false);p.collection_end(false);assert(p.count==64 && p.errors==1);
 p={};step(8);step(7);assert(p.errors==1);
 static_assert(PurgeProfile::BudgetNs==100000,"declared work budget");
}'''
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);(base/'check.cpp').write_text(source)
            subprocess.run(['g++','-std=c++17','-I'+str(root/'tools/carla/m7_nodrive'),str(base/'check.cpp'),'-o',str(base/'check')],check=True,capture_output=True)
            subprocess.run([str(base/'check')],check=True,capture_output=True)

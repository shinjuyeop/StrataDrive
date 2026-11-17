import copy
from pathlib import Path
import subprocess
import tempfile
import unittest
from audit_owner_gc_v1 import validate,declared_policy

class OwnerGcTests(unittest.TestCase):
    def test_gc_policy_does_not_leak_to_renderer_or_change_period(self):
        good=dict(profile_owner_gc=True,profile_state_path=True,endurance_seconds=300,owner_serial_gc=True,
            argv=dict(owner=['-StrataM10GcProfile','-ExecCmds=r.Render 1,gc.AllowParallelGC 0'],renderer=['-ExecCmds=r.Render 1']))
        self.assertTrue(declared_policy(good))
        for mutate in [lambda x:x['argv']['renderer'].append('-ExecCmds=gc.AllowParallelGC 0'),
                lambda x:x['argv']['owner'].append('-ExecCmds=gc.TimeBetweenPurgingPendingKillObjects 600'),
                lambda x:x.update(profile_state_path=False),lambda x:x.update(owner_serial_gc=False),
                lambda x:x['argv']['owner'].remove('-StrataM10GcProfile')]:
            value=copy.deepcopy(good);mutate(value)
            with self.assertRaises(ValueError):declared_policy(value)
        baseline=copy.deepcopy(good);baseline['owner_serial_gc']=False
        baseline['argv']['owner']=['-StrataM10GcProfile','-ExecCmds=r.Render 1']
        self.assertFalse(declared_policy(baseline))

    def test_gc_journal_policy_and_invalid_observations(self):
        begin=dict(wall_ns=100,cpu_ns=20,voluntary=1,involuntary=0,minor_faults=1,major_faults=0,processor=2,valid=1)
        end=dict(begin,wall_ns=200,cpu_ns=30,voluntary=3)
        trim=dict(begin,wall_ns=150,cpu_ns=25)
        good=dict(errors=0,active=False,parallel=0,period_seconds=61.099998474,cycles=[dict(completed_frame=12,begin=begin,memory_trim=trim,end=end)])
        self.assertEqual(validate(good,True)[0]['delta']['wall_ns'],100)
        parallel=copy.deepcopy(good);parallel['parallel']=1
        self.assertEqual(validate(parallel,False)[0]['delta']['wall_ns'],100)
        with self.assertRaises(ValueError):validate(good,False)
        for mutate in [lambda x:x.update(errors=1),lambda x:x.update(active=True),lambda x:x.update(parallel=1),
                lambda x:x.update(period_seconds=600),lambda x:x['cycles'].append(x['cycles'][0]),
                lambda x:x['cycles'][0]['end'].update(wall_ns=99),
                lambda x:x['cycles'][0]['end'].update(voluntary=0),
                lambda x:x['cycles'][0]['begin'].update(valid=0),
                lambda x:x['cycles'][0]['memory_trim'].update(wall_ns=210),
                lambda x:x['cycles'][0]['end'].update(processor=4)]:
            value=copy.deepcopy(good);mutate(value)
            with self.assertRaises(ValueError):validate(value,True)
        self.assertEqual(validate(dict(good,cycles=[]),True),[])

    def test_real_cpp_fixed_journal_bounds_and_invalid_order(self):
        root=Path(__file__).resolve().parents[3]
        source=r'''
#include "gc_profile.hpp"
#include <cassert>
using namespace stratadrive::m7_native;
int main(){
  GcProfile p{};OwnerStamp a{};a.valid=1;a.wall=100;a.cpu=10;
  auto b=a;b.wall=120;b.cpu=20;
  p.end(b);assert(p.errors==1 && p.count==0);
  p={};p.begin(a,12);p.begin(a,13);assert(p.errors==1 && p.active);
  p.trim(a);p.end(b);assert(p.count==1 && !p.active && p.cycles[0].completed_frame==12);
  p={};for(unsigned i=0;i<64;++i){p.begin(a,i+1);p.trim(a);p.end(b);}
  assert(p.count==64 && p.errors==0);p.begin(a,65);p.end(b);
  assert(p.count==64 && p.errors==2);
  p={};p.begin(b,1);p.end(a);assert(p.errors && p.count==1);
  p={};p.begin(a,1);p.trim(a);p.trim(a);p.end(b);assert(p.errors==1);
  p={};p.begin(a,1);p.end(b);assert(p.errors);
  p={};auto now=owner_stamp();p.begin(now,1);p.trim(owner_stamp());p.end(owner_stamp());assert(p.count==1 && !p.errors);
}
'''
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder);(path/'test.cpp').write_text(source)
            subprocess.run(['g++','-std=c++17','-I'+str(root/'tools/carla/m7_nodrive'),str(path/'test.cpp'),'-o',str(path/'test')],check=True,capture_output=True)
            subprocess.run([str(path/'test')],check=True,capture_output=True)

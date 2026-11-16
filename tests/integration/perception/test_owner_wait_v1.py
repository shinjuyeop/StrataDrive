import copy
from pathlib import Path
import subprocess
import tempfile
import unittest
from audit_owner_wait_v1 import PHASES, REASONS, validate

class OwnerWaitTests(unittest.TestCase):
    def fixture(self):
        def point(t):return dict(wall_ns=t,cpu_ns=t//2,voluntary=1,involuntary=2,minor_faults=3,major_faults=0,processor=2,valid=1)
        value={n:dict(wall_ns=1000+i*100,cpu_ns=(1000+i*100)//2) for i,n in enumerate(PHASES)}
        value['scheduling']={n:point(1000+i*100) for i,n in enumerate(PHASES)}
        aggregate=dict(count=1,errors=0,wall_ns=100,cpu_ns=50,voluntary=0,involuntary=0,minor_faults=0,major_faults=0,longest_begin=point(500),longest_end=point(600))
        value['owner_wait']=dict(active=dict(aggregate,count=2,wall_ns=200,cpu_ns=100),idle=copy.deepcopy(aggregate),outside=copy.deepcopy(aggregate),
            reasons=dict.fromkeys(REASONS,0),requested_sleep_ns=50_000,reason_truncated=0,last_ineligible='')
        value['owner_wait']['reasons'].update(ready=1,not_due=1)
        return value
    def test_original_acquisition_and_wait_coverage(self):
        value=self.fixture();value['scheduling']['acquired_begin']['wall_ns']+=5
        self.assertEqual(validate(value)['reasons']['ready'],1)
    def test_invalid_or_incomplete_counter_evidence_is_rejected(self):
        for mode in ('counter','valid','identity','ready','calls','sleep','truncate','longest','empty'):
            value=self.fixture();wait=value['owner_wait']
            if mode=='counter':value['scheduling']['after_tick']['voluntary']=0
            if mode=='valid':value['scheduling']['after_tick']['valid']=0
            if mode=='identity':value['after_tick']['wall_ns']+=1
            if mode=='ready':wait['reasons']['ready']=2
            if mode=='calls':wait['idle']['count']=2
            if mode=='sleep':wait['requested_sleep_ns']=50_001
            if mode=='truncate':wait['reason_truncated']=1
            if mode=='longest':wait['outside']['wall_ns']=1
            if mode=='empty':wait['outside']['count']=0
            with self.subTest(mode=mode),self.assertRaises(ValueError):validate(value)
    def test_cpp_aggregation_preserves_longest_and_flags_regression(self):
        root=Path(__file__).resolve().parents[3]
        source=r'''
#include "owner_wait_profile.hpp"
#include <cassert>
#include <type_traits>
using namespace stratadrive::m7_native;
int main(){
 static_assert(std::is_trivially_copyable<OwnerWait>::value,"fixed POD");
 OwnerStamp a{100,20,1,2,3,0,2,1},b{200,30,2,4,3,0,3,1};
 WaitAggregate x;x.add(a,b);assert(x.count==1 && x.wall==100 && x.cpu==10 && x.voluntary==1 && x.involuntary==2);
 b.wall=150;b.cpu=25;x.add(a,b);assert(x.count==2 && x.wall==150 && x.longest_end.wall==200);
 b.cpu=1;x.add(a,b);assert(x.errors==1 && x.wall==150);
 OwnerWait w;w.reason(PumpReason::Ineligible,"old_input");assert(w.last_ineligible[0]=='o');
 const auto sample=owner_stamp();assert(sample.valid && sample.wall && sample.cpu);
}
'''
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);(folder/'test.cpp').write_text(source)
            subprocess.run(['g++','-std=c++17','-O2','-Wall','-Wextra','-Werror','-I'+str(root/'tools/carla/m7_nodrive'),str(folder/'test.cpp'),'-o',str(folder/'test')],check=True,capture_output=True)
            subprocess.run([str(folder/'test')],check=True,capture_output=True)

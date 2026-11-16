"""One predeclared cold process; retain preparation failure and thread counters."""
import argparse
import json
import os
from pathlib import Path
import resource
import sys
import time
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT),str(ROOT/'tests/integration/perception')]
from control_shadow_capture_v1 import Capture
from physical_ai.perception import staged_kernel_2k_v1, tensor_2k_v1

p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
timing=[]
def stamp():
    usage=resource.getrusage(resource.RUSAGE_THREAD)
    return dict(wall_ns=time.monotonic_ns(),cpu_ns=time.thread_time_ns(),minor_faults=usage.ru_minflt,
        major_faults=usage.ru_majflt,voluntary=usage.ru_nvcsw,involuntary=usage.ru_nivcsw)
def profile(function):
    def wrapped(*args,**kwargs):
        begin=stamp()
        try:return function(*args,**kwargs)
        finally:
            end=stamp();timing.append(dict(begin=begin,end=end,delta={k:end[k]-begin[k] for k in begin}))
    return wrapped
staged_kernel_2k_v1.prepare_staged=profile(staged_kernel_2k_v1.prepare_staged)
tensor_2k_v1.TensorWorkspace.prepare=profile(tensor_2k_v1.TensorWorkspace.prepare)
args=SimpleNamespace(output=a.output,wall_clock=1,step_ms=5,camera_absent_control=True,
    detector=ROOT/'build/m10-resolution-v2/models/dfine-960.onnx',models=ROOT/'build/m10-resolution-v2/models.json',
    library=ROOT/'build/m10-source-compare-v1/native/libstrata_resize_2k_v1.so')
world=SimpleNamespace(id=1,on_tick=lambda callback:1,remove_on_tick=lambda token:None)
capture=Capture(args);error=None
try:capture.attach(world,None,None)
except Exception as exc:error=str(exc)
finally:capture.stop()
report=capture.report;prep=report['preparation']
result=dict(status='RECORDED',preparation_state=prep['state'],error=error,
    workspace=report['tensor_workspace'],calls_ms=[r['elapsed_wall_ns']/1e6 for r in prep['calls']],
    preprocessing=timing,model_cpus=report['model_setup_cpus'],observer_cpus=report['observer_cpus_after_setup'],
    scope='synthetic no CARLA; thread counters around full preprocessing; not live acceptance')
assert result['observer_cpus']==[0,8]
(a.output/'profile.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='preprocessing'}))

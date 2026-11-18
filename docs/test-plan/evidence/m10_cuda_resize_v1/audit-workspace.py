"""Verify effective candidate selection from both original process reports."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[4]/'tests/integration/perception'))
from audit_cuda_resize_v1 import validate as validate_cuda

def audit(run):
    read=lambda name:json.loads((run/name).read_text())
    server=read('server.json');owner=read('capture/perception.json')
    if server.get('tensor_workspace') is not True or owner.get('tensor_workspace') is not True:
        raise ValueError('workspace not explicitly enabled in server and preparation')
    if owner['model_setup_cpus']!=[6,7,14,15] or owner['observer_cpus_after_setup']!=[0,8]:
        raise ValueError('declared preparation/observer CPU placement')
    if owner['preparation_thread_overrides']!=dict(cv=4,resize=0):
        raise ValueError('declared preparation thread settings')
    # Shutdown cancels the worker after a successful run; readiness is captured
    # before live work, while the final report must preserve those exact calls.
    prep=owner['preparation']
    if prep['state']!='READY' or len(prep['calls'])!=3:
        raise ValueError('original preparation did not reach READY in three calls')
    if prep['calls']!=owner['preparation_final']['calls']:
        raise ValueError('original preparation calls changed at shutdown')
    elapsed=[r['elapsed_wall_ns']/1e6 for r in prep['calls']]
    if max(elapsed[1:])>=100 or prep['finished_wall_ns']-prep['started_wall_ns']>10_000_000_000:
        raise ValueError('unchanged settled preparation deadline')
    renderer=read('capture/paired/renderer/result.json')
    pipeline=renderer['host_pipeline']
    if pipeline.get('tensor_workspace') is not True or pipeline['cv_threads']!=4 or pipeline['resize_threads']!=0:
        raise ValueError('declared renderer workspace and thread settings')
    if renderer['errors'] or len(renderer['preparation'])!=3:
        raise ValueError('renderer preparation/errors')
    cuda=validate_cuda(server,owner,renderer)
    return dict(status='PASS_EXPLICIT_WORKSPACE_ONLY',cuda_resize=cuda,preparation_ms=elapsed,
        model_cpus=owner['model_setup_cpus'],observer_cpus=owner['observer_cpus_after_setup'],
        renderer_pipeline=pipeline,native_perception_accepted=False)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:result=audit(a.run);code=0
    except Exception as e:result=dict(status='FAIL',error=str(e));code=1
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    raise SystemExit(code)

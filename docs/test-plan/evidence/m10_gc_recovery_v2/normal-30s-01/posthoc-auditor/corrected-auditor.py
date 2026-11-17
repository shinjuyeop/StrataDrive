"""Verify original recovery gates plus byte-pinned, non-inference startup I/O."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

# Standalone execution and frozen archive replay must resolve their own tree.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from audit_gc_recovery_v1 import audit as recovery_audit
from physical_ai.perception.library_prefetch_v1 import READ_BUDGET_NS

PROFILE=Path(__file__).resolve().parents[3]/'profiles/perception-inference-libraries-host-v1.json'


def validate(report, profile_bytes, before_ns):
    expected=json.loads(profile_bytes)
    if (report.get('status')!='PASS'
            or report.get('manifest_sha256')!=hashlib.sha256(profile_bytes).hexdigest()
            or report.get('read_budget_ns')!=READ_BUDGET_NS
            or report.get('declared_bytes')!=sum(x['bytes'] for x in expected['files'])
            or type(report.get('model_calls')) is not int or report['model_calls']!=0
            or type(report.get('control_writes')) is not int or report['control_writes']!=0):
        raise ValueError('declared byte-only library preparation')
    begin,end=report['begin_wall_ns'],report['end_wall_ns']
    if (any(type(x) is not int or x<0 for x in (begin,end,before_ns))
            or not begin<=end<=before_ns or end-begin>=READ_BUDGET_NS):
        raise ValueError('bounded library read before original preparation')
    if len(report['files'])!=len(expected['files']):raise ValueError('all declared libraries required')
    prior=begin
    for got,want in zip(report['files'],expected['files']):
        if {k:got[k] for k in ('path','bytes','sha256')}!=want:
            raise ValueError('original library bytes required')
        a,b=got['begin_wall_ns'],got['end_wall_ns']
        if type(a) is not int or type(b) is not int or not prior<=a<=b<=end:
            raise ValueError('ordered library read clocks')
        prior=b
    return dict(files=len(report['files']),bytes=report['declared_bytes'],elapsed_ns=end-begin)


def audit(run):
    read=lambda name:json.loads((run/name).read_text())
    if read('server.json').get('prefetch_inference_libraries') is not True:
        raise ValueError('explicit inference library prefetch selection')
    profile=PROFILE.read_bytes();owner=read('capture/perception.json')
    renderer=read('capture/paired/renderer/result.json')
    checks=dict(owner=validate(owner['library_prefetch'],profile,owner['preparation']['started_wall_ns']),
                renderer=validate(renderer['library_prefetch'],profile,renderer['preparation'][0]['begin_ns']))
    result=recovery_audit(run)
    result.update(status='PASS_GC_RECOVERY_PREFETCH_INTEGRITY',library_prefetch=checks,
        scope='same recovery/physics gates; recorded pinned library reads before unchanged model probes; not physical acceptance')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:result=audit(a.run)
    except Exception as error:result=dict(status='FAIL',error=str(error).replace(str(a.run),'<run>'))
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    raise SystemExit(0 if result['status']=='PASS_GC_RECOVERY_PREFETCH_INTEGRITY' else 1)

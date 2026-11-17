"""Verify the explicit three-core owner comparison and original purge/preview checks."""
import argparse
import json
from pathlib import Path
from audit_owner_gc_v1 import declared_owner_cpus
from audit_purge_slice_v1 import audit as purge_audit

PLAN=dict(owner=[2,3,4,10,11,12],native=[1,9],renderer=[5,6,7,13,14,15],observer=[0,8])

def validate_placement(server,initial):
    if server['host_resources']['cpus']!=PLAN or declared_owner_cpus(server)!=tuple(PLAN['owner']):
        raise ValueError('explicit three-owner/three-image physical-core plan')
    if server['host_resources'].get('owner_scheduler'):
        raise ValueError('unchanged owner SCHED_OTHER policy')
    end=initial+server['endurance_seconds']*1_000_000_000
    counts={role:0 for role in ('owner','renderer','client','native','pipeline')}
    for row in server['resources']:
        if not initial<=row['wall_ns']<=end:continue
        for proc in row['processes']:
            role=proc['role']
            if role=='client/child':
                role='native' if proc['scheduler']==1 and proc['priority']==18 else 'pipeline'
            if role not in counts:continue
            expected=PLAN['observer' if role=='client' else 'renderer' if role=='pipeline' else role]
            policy,priority=(1,18) if role=='native' else (0,0)
            if proc['affinity']!=expected or proc['scheduler']!=policy or proc['priority']!=priority:
                raise ValueError('actual measured process placement/policy: '+role)
            counts[role]+=1
    if not all(counts.values()):raise ValueError('measured process placement evidence required')
    return counts

def audit(run):
    read=lambda name:json.loads((run/name).read_text())
    counts=validate_placement(read('server.json'),read('capture/native.json')['initial'])
    result=purge_audit(run)
    result.update(status='PASS_OWNER_THREE_INTEGRITY',owner_cpus=PLAN['owner'],renderer_cpus=PLAN['renderer'],
                  measured_placement_samples=counts,scope='explicit CPU placement and original purge/preview integrity; not physical acceptance')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:result=audit(a.run)
    except Exception as e:result=dict(status='FAIL',error=str(e).replace(str(a.run),'<run>'))
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    raise SystemExit(0 if result['status']=='PASS_OWNER_THREE_INTEGRITY' else 1)

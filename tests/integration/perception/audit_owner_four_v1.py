"""Check the explicit four-owner/two-image layout with unchanged recovery gates."""
import argparse
import json
from pathlib import Path
from audit_library_prefetch_v1 import audit as prefetch_audit
from audit_owner_three_v1 import validate_placement
from audit_purge_slice_v1 import audit as purge_audit

PLAN=dict(owner=[2,3,4,5,10,11,12,13],native=[1,9],renderer=[6,7,14,15],observer=[0,8])

def recovery_audit(run):
    read=lambda name:json.loads((run/name).read_text())
    counts=validate_placement(read('server.json'),read('capture/native.json')['initial'],PLAN)
    result=purge_audit(run,300_000)
    result.update(owner_cpus=PLAN['owner'],renderer_cpus=PLAN['renderer'],measured_placement_samples=counts)
    return result

def audit(run):
    result=prefetch_audit(run,recovery_audit)
    result.update(status='PASS_OWNER_FOUR_PREFETCH_INTEGRITY',
                  scope='four owner/two image cores; unchanged library, recovery and final gates; not physical acceptance')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:result=audit(a.run)
    except Exception as error:result=dict(status='FAIL',error=str(error).replace(str(a.run),'<run>'))
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    raise SystemExit(0 if result['status']=='PASS_OWNER_FOUR_PREFETCH_INTEGRITY' else 1)

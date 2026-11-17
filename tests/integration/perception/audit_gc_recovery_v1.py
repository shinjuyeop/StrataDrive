"""Verify explicit 300us preview with the original three-core/purge/physics gates."""
import argparse
import json
from pathlib import Path
from audit_owner_three_v1 import audit as owner_three_audit

def audit(run):
    result=owner_three_audit(run,300_000)
    result.update(status='PASS_GC_RECOVERY_PREVIEW_INTEGRITY',
                  scope='explicit 300us preview, unchanged whole 5ms interval and HV30ms; not physical acceptance')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:result=audit(a.run)
    except Exception as error:result=dict(status='FAIL',error=str(error).replace(str(a.run),'<run>'))
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    raise SystemExit(0 if result['status']=='PASS_GC_RECOVERY_PREVIEW_INTEGRITY' else 1)

#!/usr/bin/env python3
"""Reject continuity/identity/normal-authority corruption in a real saved run."""
import argparse
import json
from pathlib import Path
from audit_m7_simulation import audit


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    baseline=audit(a.directory,'continuous')
    mutations={
        'duplicate_source_frame':lambda r:r.update(frame=r['frame']-1),
        'skipped_physics_frame':lambda r:r['receipt'].update(frame=str(int(r['receipt']['frame'])+1)),
        'hidden_reset':lambda r:r['receipt']['physics'].update(generation=0),
        'changed_session':lambda r:r['receipt'].update(session='0'),
        'restamped_interval':lambda r:r['receipt'].update(simulation_begin_seconds=r['simulation_seconds']+.001),
        'lost_normal_authority':lambda r:r['receipt']['original_actual']['admitted_actual'].update(normal=False),
    }
    rejected={}
    for name,mutate in mutations.items():
        try:audit(a.directory,'continuous',mutate)
        except ValueError as error:rejected[name]=str(error)
        else:raise AssertionError('corruption accepted: '+name)
    a.output.write_text(json.dumps(dict(status='PASS_CORRUPTION_REJECTION',baseline=baseline,rejected=rejected),indent=2)+'\n')


if __name__=='__main__':main()

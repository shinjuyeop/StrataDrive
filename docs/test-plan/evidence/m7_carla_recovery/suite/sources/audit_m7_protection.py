#!/usr/bin/env python3
"""Audit physical continuation after trusted protection; no full-stop acceptance."""
import argparse
import copy
import gzip
import json
from pathlib import Path
from audit_m7_1q_native import audit,check

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    model=json.loads((Path(__file__).resolve().parents[3]/'tools/carla/m7_nodrive/virtual_ev_v1.json').read_text())
    result=audit(a.directory,model,work_mode=True)
    path=a.directory/'trace.jsonl';opening=open
    if not path.exists():path=path.with_suffix('.jsonl.gz');opening=gzip.open
    with opening(path,'rt') as f:rows=[json.loads(line) for line in f]
    applied=[r for r in rows if 'receipt' in r]
    check(len(applied)==400 and result['protection_intervals']==200,'400 intervals, 200 protection')
    before=applied[199]['receipt']['physics'];last=applied[-1]['receipt']['physics']
    check(before['body_forward_velocity_m_s']>0,'actual initial motion')
    check(abs(last['body_forward_velocity_m_s'])<before['body_forward_velocity_m_s'],'observed deceleration')
    for row in applied[300:]:
        act=row['receipt']['original_actual']['admitted_actual']
        check(act['torque_nm']==0 and act['pressure_pa']>=1000000,'actual protection zero torque and brake floor')
        check(all(w['solver_omega_rad_s']==0 for w in row['receipt']['physics']['wheels']),'stable exact wheel zero')
    faults={
        'missing_selection':lambda proof:proof.__setitem__('protection_selected_mask',127),
        'changed_selection_time':lambda proof:proof.__setitem__('protection_since_ns',str(int(proof['protection_since_ns'])+1)),
        'resume_normal':lambda proof:proof.__setitem__('normal',True),
        'lost_actual':lambda proof:proof['actual'].__setitem__(1,None),
    }
    rejected={}
    for name,mutate in faults.items():
        def corrupt(row):
            proof=row['native']['native_export'];mutate(proof)
            submitted=copy.deepcopy(proof)
            for k in ('service_mask','credit_mask','release_mask'):submitted[k]=str(row['native'][k])
            row['receipt']['original_actual']['native']=submitted
        try:audit(a.directory,model,corrupt,True,220)
        except ValueError as error:rejected[name]=str(error)
        else:raise AssertionError('corruption escaped '+name)
    tail=[r['receipt']['physics']['body_forward_velocity_m_s'] for r in applied[300:]]
    result.update(status='PASS_FUNCTIONAL_PROTECTION_CONTINUATION',before_protection_m_s=before['body_forward_velocity_m_s'],
                  final_m_s=last['body_forward_velocity_m_s'],last_100_body_velocity_range_m_s=[min(tail),max(tail)],
                  exact_zero_wheel_intervals_last_100=100,corruptions_rejected=rejected,
                  full_body_stationary_accepted=False,wall_deadlines_accepted=False)
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()

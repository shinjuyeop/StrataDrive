#!/usr/bin/env python3
"""Independent complete NoDrive solver trace/work validation, no EV claims."""
import argparse
import copy
import gzip
import json
import math
from pathlib import Path
import struct
from audit_m7_1q_native import check


def f32(x):
    return struct.unpack('<f',struct.pack('<f',x))[0]


def validate(row):
    r = row['receipt']
    w = r['solver_work']
    check(w['source']=='PhysX3.4.NoDrive.integrator.postOmega.v1','solver identity')
    check(r['interval_work_valid'] and r['solver_substep_work_observed'] and w['valid'],'work validity')
    check((w['abi'],w['begins'],w['ends'],w['wheels'],w['overflow'])==(1,1,1,4,0),'whole invocation')
    check(w['solver_dt_s']==f32(.01),'solver world interval')
    steps = w['steps']
    sleeping = w['sleeping']==1
    check((sleeping and w['count']==len(steps)==0) or
          (w['sleeping']==0 and w['count']==len(steps)==320),'complete substeps')
    final = r['physics']['wheels']
    effort = [q['set_drive_nm'] for q in final]
    sums = [0.]*4
    minimum = math.inf
    maximum_residual = 0.
    for k,s in enumerate(steps):
        check((s['ordinal'],s['count'],s['block'])==(k,320,0),'ordered unique substeps')
        check(s['dt_s']==f32(f32(.01)*f32(1/320)),'actual solver dt')
        for field in ('before_rad_s','after_rad_s','drive_nm','brake_nm','tire_nm','damping_nm_s'):
            check(len(s[field])==4 and all(type(v) in (int,float) and math.isfinite(v) for v in s[field]),'finite complete wheel tuple')
        for j in range(4):
            check(s['drive_nm'][j]==effort[j],'applied torque binding')
            check(not k or s['before_rad_s'][j]==steps[k-1]['after_rad_s'][j],'omega continuity')
            if k==319: check(s['after_rad_s'][j]==final[j]['solver_omega_rad_s'],'final direct solver readout')
            # Validate original integrator equation independently in SI. The
            # error bound accounts only for binary32 intermediate arithmetic.
            old=s['before_rad_s'][j];dt_i=s['dt_s']/final[j]['inertia_kg_m2']
            terms=[s[name][j] for name in ('drive_nm','brake_nm','tire_nm')]
            predicted=(old+dt_i*sum(terms))/(1+s['damping_nm_s'][j]*dt_i)
            if final[j]['set_friction_nm']!=0 and old*predicted<=0: predicted=0.
            residual=abs(predicted-s['after_rad_s'][j]);maximum_residual=max(maximum_residual,residual)
            scale=abs(old)+dt_i*sum(abs(v) for v in terms)+abs(predicted)
            check(residual <= 16*2**-23*scale+2**-126,'integrator equation')
            sums[j]+=s['drive_nm'][j]*s['after_rad_s'][j]*s['dt_s']
        if effort[2] or effort[3]: minimum=min(minimum,(s['after_rad_s'][2]+s['after_rad_s'][3])/2)
    if sleeping:
        check(all(q['set_drive_nm']==q['set_steer_right_rad']==q['solver_omega_rad_s']==0 for q in final),'explicit sleeping zero-work witness')
    check(len(w['motor_work_j'])==4 and all(math.isclose(a,b,rel_tol=1e-13,abs_tol=1e-15) for a,b in zip(sums,w['motor_work_j'])),'signed work sum')
    eligible = all(s['drive_nm'][0]==s['drive_nm'][1]==0 and s['drive_nm'][2]==s['drive_nm'][3] and
                   (not s['drive_nm'][2] or 0 <= (s['after_rad_s'][2]+s['after_rad_s'][3])/2 <= 100) for s in steps)
    check(w['forward_energy_eligible']==eligible,'EV forward eligibility')
    return sums,minimum,maximum_residual


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory',type=Path)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    path=a.directory/'trace.jsonl'
    opening=open
    if not path.exists(): path=path.with_suffix('.jsonl.gz');opening=gzip.open
    count=0;totals=[0.]*4;minimum=math.inf;residual=0.;sample=None;negative=[]
    with opening(path,'rt') as file:
        for line in file:
            row=json.loads(line)
            if 'receipt' not in row: continue
            sums,m,e=validate(row)
            count+=1;totals=[x+y for x,y in zip(totals,sums)];minimum=min(minimum,m);residual=max(residual,e)
            if m<0: negative.append(row['index'])
            if row['index']==150: sample=row
    mutations={
        'missing_step':lambda w:w['steps'].pop(10),
        'duplicate_ordinal':lambda w:w['steps'][10].update(ordinal=9),
        'missing_end':lambda w:w.update(ends=0),
        'overflow':lambda w:w.update(overflow=1),
        'wrong_dt':lambda w:w['steps'][10].update(dt_s=.01),
        'torque':lambda w:w['steps'][10]['drive_nm'].__setitem__(2,999),
        'omega':lambda w:w['steps'][10]['after_rad_s'].__setitem__(2,999),
        'nonfinite':lambda w:w['steps'][10]['after_rad_s'].__setitem__(2,float('nan')),
        'sum':lambda w:w['motor_work_j'].__setitem__(2,999),
        'source':lambda w:w.update(source='corrected public wheel getter'),
        'false_sleep':lambda w:w.update(sleeping=1),
    }
    checks={}
    check(sample is not None,'mutation sample')
    for name,mutate in mutations.items():
        bad=copy.deepcopy(sample);mutate(bad['receipt']['solver_work'])
        try: validate(bad)
        except ValueError as e: checks[name]=str(e)
        else: raise ValueError('accepted corruption: '+name)
    result=dict(status='PASS_COMPLETE_SOLVER_OBSERVATION',intervals=count,motor_work_j=totals,
                minimum_loaded_rear_mean_rad_s=None if minimum==math.inf else minimum,
                forward_ineligible=negative,maximum_equation_residual_rad_s=residual,
                rejected_corruptions=checks,ev_settlement_connected=False)
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()

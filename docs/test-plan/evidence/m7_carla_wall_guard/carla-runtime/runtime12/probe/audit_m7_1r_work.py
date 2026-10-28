#!/usr/bin/env python3
"""Independent complete NoDrive solver trace/work validation, no EV claims."""
import argparse
import copy
import gzip
import json
import math
from pathlib import Path
import struct
from audit_m7_1q_native import check, audit as audit_native


def f32(x):
    return struct.unpack('<f',struct.pack('<f',x))[0]


def validate_hold(row, previous):
    r=row['receipt'];w=r['solver_work']
    held=w.get('protected_steer_hold',False)
    check(type(held) is bool,'typed held-steer witness')
    if w['abi']==1:
        check(not held and not r.get('protected_held_steer_sleep',False),'legacy observer cannot attest held steer')
    else:
        check(type(r.get('protected_held_steer_sleep')) is bool and
              held==r['protected_held_steer_sleep'],'server/solver held-steer agreement')
    if not held:return
    check(previous is not None,'held policy needs preceding completed interval')
    prev=previous['receipt']
    check(int(prev['frame'])+1==int(r['frame']) and
          all(prev[k]==r[k] for k in ('actor','run','session','physics_generation')),'held predecessor identity')
    for q in (prev,r):
        act=q['original_actual']['admitted_actual']
        check(act['protection'] and not act['normal'] and act['torque_nm']==0 and
              act['pressure_pa']>=1000000,'held policy original protective Actual')
    for old,new in zip(prev['physics']['wheels'],r['physics']['wheels']):
        check(old['set_drive_nm']==new['set_drive_nm']==0 and
              0<old['set_friction_nm']==new['set_friction_nm'] and
              old['set_steer_right_rad']==new['set_steer_right_rad'],'identical preceding protected effort')


def validate(row, previous=None):
    r = row['receipt']
    w = r['solver_work']
    check(w['source']=='PhysX3.4.NoDrive.integrator.postOmega.v1','solver identity')
    check(r['interval_work_valid'] and r['solver_substep_work_observed'] and w['valid'],'work validity')
    check(w['abi'] in (1,2) and (w['begins'],w['ends'],w['wheels'],w['overflow'])==(1,1,4,0),'whole invocation')
    validate_hold(row,previous)
    check(w['solver_dt_s']==f32(.01),'solver world interval')
    steps = w['steps']
    if 'trace_delivery' in w:
        check(w['trace_delivery']=='bounded_raw_journal; drain_before_close','compact trace provenance')
        reply=row['solver_trace_binding']
        check(reply['ok'] and reply['ticket']==r['ticket'] and reply['trace_frame']==r['frame'] and
              all(reply[k]==r[k] for k in ('run','session','actor','physics_generation')),'raw journal scope')
        check(w['rear_mean_rad_s']==[(q['after_rad_s'][2]+q['after_rad_s'][3])/2 for q in steps],'compact means equal original solver')
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
        check(r['physics']['sleeping'] and all(q['set_drive_nm']==q['solver_omega_rad_s']==0 and
              (q['set_steer_right_rad']==0 or w.get('protected_steer_hold',False)) for q in final),'explicit sleeping zero-work witness')
    check(len(w['motor_work_j'])==4 and all(math.isclose(a,b,rel_tol=1e-13,abs_tol=1e-15) for a,b in zip(sums,w['motor_work_j'])),'signed work sum')
    eligible = all(s['drive_nm'][0]==s['drive_nm'][1]==0 and s['drive_nm'][2]==s['drive_nm'][3] and
                   (not s['drive_nm'][2] or 0 <= (s['after_rad_s'][2]+s['after_rad_s'][3])/2 <= 100) for s in steps)
    check(w['forward_energy_eligible']==eligible,'EV forward eligibility')
    return sums,minimum,maximum_residual


def validate_settlement(row, previous, cumulative):
    n=row['native'];s=n['settlement'];r=previous['receipt']
    begin=int(r['logical_begin_ns']);end=math.floor(r['simulation_end_seconds']*1e9+.5)
    check(n['energy_basis']=='OBSERVED_SOLVER_WORK_SINGLE_EV' and n['carla_work_valid'],'single EV basis')
    check(s['frame']==int(r['frame']) and s['end_ns']==end,'settlement identity')
    check(math.isclose(s['total_mechanical_j'],cumulative,rel_tol=1e-13,abs_tol=1e-12),'solver/EV work conservation')
    check(abs(s['balance_j'])<=.00072,'original M6 energy tolerance')
    accounted=s['total_mechanical_j']+sum(s[k] for k in ('motor_loss_j','auxiliary_j','ohmic_j','capacitor_delta_j','circuit_loss_j'))
    check(abs(s['chemical_j']-accounted-s['balance_j'])<1e-10,'independent energy ledger')
    check(abs(s['soc']-(.63-s['chemical_j']/180000000))<3e-16,'SOC/chemical energy')
    cursor=begin;total=0.;w=r['solver_work'];duration=end-begin
    torque=sum(q['set_drive_nm'] for q in r['physics']['wheels'])
    admitted=r['original_actual']['admitted_actual']
    oldest=begin if admitted['empty_init'] else int(admitted['oldest_actuator_ns'])
    for e in n['electrical_steps']:
        check(e['begin_ns']==cursor and cursor<e['end_ns']<=min(cursor+1000000,end),'complete native energy coverage')
        check(e['wheel_source_ns']==begin and e['wheel_oldest_ns']==oldest and e['actual_torque_nm']==torque,'original source and applied torque')
        expected=0.
        for k,q in enumerate(w['steps']):
            lo=duration*k/320;hi=duration*(k+1)/320
            fraction=max(0.,min(e['end_ns']-begin,hi)-max(cursor-begin,lo))/(hi-lo)
            expected+=sum(q['drive_nm'][j]*q['after_rad_s'][j]*q['dt_s'] for j in (2,3))*fraction
        check(abs(e['mechanical_j']-expected)<1e-11,'conservative per-model-interval work')
        cursor=e['end_ns'];total+=e['mechanical_j']
    check(cursor==end and abs(total-sum(w['motor_work_j']))<1e-11,'complete frame settled once')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory',type=Path)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--model',type=Path,default=Path(__file__).resolve().parents[3]/'tools/carla/m7_nodrive/virtual_ev_v1.json')
    a=p.parse_args()
    path=a.directory/'trace.jsonl'
    opening=open
    if not path.exists(): path=path.with_suffix('.jsonl.gz');opening=gzip.open
    report=json.loads((a.directory/'result.json').read_text())
    connected=report.get('ev_settlement_connected',False)
    count=0;totals=[0.]*4;minimum=math.inf;residual=0.;sample=None;negative=[]
    previous=None;settlement_sample=None;settlements=0;accepted_acks=0;max_balance=0.
    with opening(path,'rt') as file:
        for line in file:
            row=json.loads(line)
            accepted_acks+=int(row.get('settlement_ack',{}).get('ok',False))
            if connected and row.get('native',{}).get('settlement'):
                validate_settlement(row,previous,sum(totals));settlements+=1
                max_balance=max(max_balance,abs(row['native']['settlement']['balance_j']))
                if row['index']==150:settlement_sample=(copy.deepcopy(row),copy.deepcopy(previous),sum(totals))
            if 'receipt' not in row: continue
            sums,m,e=validate(row,previous)
            count+=1;totals=[x+y for x,y in zip(totals,sums)];minimum=min(minimum,m);residual=max(residual,e)
            if m<0: negative.append(row['index'])
            if row['index']==150: sample=row
            previous=row
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
    if 'trace_delivery' in sample['receipt']['solver_work']:
        for name in ('ticket','trace_frame','session','physics_generation','compact_mean'):
            bad=copy.deepcopy(sample)
            if name=='compact_mean':bad['receipt']['solver_work']['rear_mean_rad_s'][10]+=1e-12
            else:bad['solver_trace_binding'][name]=str(int(bad['solver_trace_binding'][name])+1)
            try:validate(bad)
            except ValueError as error:checks['journal_'+name]=str(error)
            else:raise ValueError('accepted journal corruption '+name)
    energy_checks={}
    if connected:
        check(report['settlements']==accepted_acks,'reported accepted ACK count')
        check(settlement_sample is not None,'settlement mutation sample')
        mutations={
            'duplicate_energy_interval':lambda n:n['electrical_steps'].insert(1,copy.deepcopy(n['electrical_steps'][0])),
            'missing_energy_interval':lambda n:n['electrical_steps'].pop(1),
            'restamped_wheel':lambda n:n['electrical_steps'][1].update(wheel_source_ns=n['electrical_steps'][1]['begin_ns']),
            'predicted_work':lambda n:n.update(energy_basis='MODEL_ZOH_PREDICTION_NOT_CARLA_WORK'),
            'changed_work_total':lambda n:n['settlement'].update(total_mechanical_j=999),
            'changed_SOC':lambda n:n['settlement'].update(soc=.63),
            'changed_loss':lambda n:n['settlement'].update(motor_loss_j=999),
        }
        for name,mutate in mutations.items():
            row,prev,cumulative=copy.deepcopy(settlement_sample);mutate(row['native'])
            try:validate_settlement(row,prev,cumulative)
            except ValueError as e:energy_checks[name]=str(e)
            else:raise ValueError('accepted energy corruption: '+name)
        if report['fault']=='none':check(settlements==count==report['settlements'],'all receipt settlements')
        else:check(settlements>=report['settlements'],'partial fault settlement counts')
    result=dict(status='PASS_SOLVER_WORK_SINGLE_EV' if connected else 'PASS_COMPLETE_SOLVER_OBSERVATION',intervals=count,motor_work_j=totals,
                minimum_loaded_rear_mean_rad_s=None if minimum==math.inf else minimum,
                forward_ineligible=negative,maximum_equation_residual_rad_s=residual,
                rejected_corruptions=checks,ev_settlement_connected=connected,
                independently_verified_settlements=settlements,max_abs_energy_balance_j=max_balance,
                rejected_energy_corruptions=energy_checks,
                native_actual_audit=audit_native(a.directory,json.loads(a.model.read_text()),work_mode=True))
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()

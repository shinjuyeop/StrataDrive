#!/usr/bin/env python3
"""Independent allocation-selection/PI oracle. Combine with route and work audits."""
import argparse
import copy
import json
import math
from pathlib import Path
from audit_m7_1q_native import check,wire,frame
from evidence_io import json_rows
from m8_reference_feasibility import require_feasible_route


def audit(directory,rows=None):
    result=json.loads((directory/'result.json').read_text())
    check(result['propulsion_aware'] is True,'explicit propulsion mode')
    check(result['reference_feasibility']==require_feasible_route(result['route_profile']['definition']),'frozen feasibility report')
    controls={};selections={};held={};integral=previous=0.;target=None
    clipped=frozen=negative=0;max_error=0.
    for row in json_rows(directory/'trace.jsonl') if rows is None else rows:
        native=row.get('native',{});s=native.get('speed_control');a=native.get('allocation_selection')
        proof=native.get('native_export')
        if a is not None:
            ns=a['selection_ns']
            check(type(ns) is int and ns<=native['now_ns'],'selection clock')
            check(all(math.isfinite(a[k]) for k in ('requested_acceleration_mps2','requested_propulsion_nm','selected_propulsion_nm')),'finite selection')
            wanted=max(0.,a['requested_acceleration_mps2'])*(1696*.355)
            check(abs(a['requested_propulsion_nm']-wanted)<1e-12,'inertial torque selection request')
            check(0<=a['selected_propulsion_nm']<=min(300.,wanted),'positive selection bounds')
            check(type(a['limited']) is bool and a['limited']==(wanted>a['selected_propulsion_nm']),'selection limited flag')
            if ns in selections:check(a==selections[ns],'immutable allocation record')
            else:
                check(proof and proof['normal'],'successful normal allocation provenance')
                q=wire(proof['commands'][2],1,4,5);q.get('IQQQI');command=frame(q,2,False)
                check(q.get('B')==1,'allocation child context')
                epoch,seq,source,expiry,accel,curve,brake,hold=q.get('IIQQdddB')
                check(a['epoch']==epoch==command['epoch']==42 and a['request_sequence']==seq==command['causal'] and
                      a['selection_ns']==command['source'] and a['requested_acceleration_mps2']==accel,'original command selection ancestry')
                check(0<=a['selected_propulsion_nm']-max(0.,command['value'])<.10000000001,'selection agrees with quantized command')
                selections[ns]=copy.deepcopy(a)
        if not s:continue
        check(all(math.isfinite(s[k]) for k in ('target_mps','speed_mps','acceleration_mps2','integral')),'finite PI state')
        seq=s['sequence'];feedback=native.get('speed_selection');used=native.get('saturation_used')
        check(type(used) is bool,'typed saturation flag')
        if seq in controls:
            check(s==controls[seq] and (feedback,used)==held[seq],'immutable held PI/selection');continue
        check(seq==len(controls),'contiguous PI sequence')
        if seq==0:check(feedback is None and used,'conservative bootstrap')
        else:
            old=controls[seq-1]
            check(feedback is not None,'missing previous selection')
            check(feedback['selection_ns'] in selections and feedback==selections[feedback['selection_ns']],'original prior allocation selection')
            check(feedback['epoch']==42 and feedback['request_sequence']==seq-1 and
                  old['release_ns']<=feedback['selection_ns']<s['release_ns'] and
                  s['release_ns']-feedback['selection_ns']<=30000000 and
                  feedback['requested_acceleration_mps2']==old['acceleration_mps2'],'previous cycle identity/time')
            check(used==feedback['limited'],'saturation input matches selection')
            check(s['release_ns']-old['release_ns']==20000000,'fixed PI period')
        rate=0. if target is None else (s['target_mps']-target)/.02
        error=max(0.,s['target_mps']+.12*min(0.,rate))-s['speed_mps']
        raw=rate+error+integral
        output=max(previous-.04,min(previous+.04,max(-5.,min(2.,raw))))
        internal=(raw-output)*error<=0
        if internal and not(used and error>0):integral+=.2*error*.02
        clipped+=bool(used);frozen+=bool(used and error>0 and internal)
        negative+=bool(used and error<0 and internal)
        diff=max(abs(s['acceleration_mps2']-output),abs(s['integral']-integral));max_error=max(max_error,diff)
        check(math.isfinite(diff) and diff<=1e-12,'independent PI output/integral')
        controls[seq]=copy.deepcopy(s);held[seq]=(copy.deepcopy(feedback),used)
        target=s['target_mps'];previous=output
    check(len(controls)>10 and len(selections)>10,'nonempty controller/allocation stream')
    return dict(status='PASS_PROPULSION_SELECTION_AND_PI',controls=len(controls),allocations=len(selections),
        saturated_controls=clipped,positive_integral_freezes=frozen,negative_integrations_while_limited=negative,max_pi_error=max_error)


def mutations(directory):
    # Small audit-specific view; do not retain physics/work megabytes per row.
    rows=[]
    for row in json_rows(directory/'trace.jsonl'):
        n=row.get('native',{});rows.append(dict(native={k:v for k,v in n.items() if k in
            ('now_ns','speed_control','allocation_selection','speed_selection','saturation_used','native_export')}))
    baseline=audit(directory,rows)
    i=next(i for i,r in enumerate(rows) if r['native'].get('speed_selection') and r['native']['speed_control']['sequence']>5)
    changes={
        'missing_feedback':lambda n:n.update(speed_selection=None),
        'wrong_epoch':lambda n:n['speed_selection'].update(epoch=41),
        'wrong_parent':lambda n:n['speed_selection'].update(request_sequence=999),
        'future_selection':lambda n:n['speed_selection'].update(selection_ns=n['speed_control']['release_ns']),
        'wrong_acceleration':lambda n:n['speed_selection'].update(requested_acceleration_mps2=99),
        'wrong_selected_torque':lambda n:n['speed_selection'].update(selected_propulsion_nm=999),
        'wrong_limited':lambda n:n['speed_selection'].update(limited=not n['speed_selection']['limited']),
        'wrong_used_flag':lambda n:n.update(saturation_used=not n['saturation_used']),
        'wrong_integral':lambda n:n['speed_control'].update(integral=n['speed_control']['integral']+.01),
        'nonfinite_integral':lambda n:n['speed_control'].update(integral=float('nan')),
        'wrong_output':lambda n:n['speed_control'].update(acceleration_mps2=n['speed_control']['acceleration_mps2']+.01),
        'wrong_allocation':lambda n:n['allocation_selection'].update(selected_propulsion_nm=999),
    };verdicts=[]
    for name,change in changes.items():
        original=rows[i];rows[i]=copy.deepcopy(original);change(rows[i]['native'])
        try:audit(directory,rows)
        except (ValueError,KeyError,TypeError) as e:verdicts.append(dict(case=name,rejected=True,reason=str(e)))
        else:raise ValueError('mutation accepted: '+name)
        finally:rows[i]=original
    return dict(status='PASS_PROPULSION_MUTATIONS',baseline=baseline,mutations=verdicts)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--mutations',action='store_true');a=p.parse_args()
    try:report=mutations(a.directory) if a.mutations else audit(a.directory)
    except (ValueError,KeyError,TypeError) as e:report=dict(status='FAIL',error=str(e))
    a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));return int(report['status']=='FAIL')
if __name__=='__main__':raise SystemExit(main())

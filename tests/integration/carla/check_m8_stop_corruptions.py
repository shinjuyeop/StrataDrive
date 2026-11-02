#!/usr/bin/env python3
"""Mutation tests on copies of original terminal evidence, including valid CRCs."""
import argparse,copy,json,struct
from pathlib import Path
from audit_m8_stop import audit
from evidence_io import json_rows

def rewrite(value,offset,fmt,new):
    raw=bytearray.fromhex(value);struct.pack_into('<'+fmt,raw,offset if offset>=0 else len(raw)+offset,new)
    crc=0xffffffff
    for b in raw[:-4]:
        crc^=b
        for _ in range(8):crc=(crc>>1)^(0x82f63b78 if crc&1 else 0)
    struct.pack_into('<I',raw,len(raw)-4,crc^0xffffffff)
    return raw.hex()

def main():
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    rows=[]
    for row in json_rows(a.directory/'trace.jsonl'):
        r={k:v for k,v in row.items() if k in ('index','frame','simulation_seconds','native','physics','vehicle_state','route_pose','pose_input')}
        if 'receipt' in row:r['receipt']={}
        rows.append(r)
    baseline=audit(a.directory,rows);mode=baseline['mode']
    trigger=next(i for i,r in enumerate(rows) if r['native']['speed_terminal']['trigger_ns'])
    tail=len(rows)-2
    changes={
        'trigger_shift':(trigger,lambda r:r['native']['speed_terminal'].update(trigger_ns=1)),
        'missing_event':(trigger,lambda r:r['native']['speed_terminal'].update(trigger_ns=0)),
        'continued_PI':(trigger,lambda r:r['native']['speed_control'].update(sequence=750)),
        'changed_integral':(trigger,lambda r:r['native']['speed_control'].update(integral=99)),
        'moving_final_body':(tail,lambda r:r['physics'].update(body_forward_velocity_m_s=1)),
        'moving_final_wheel':(tail,lambda r:r['physics']['wheels'][0].update(solver_omega_rad_s=1)),
        'stop_pose_drift':(tail,lambda r:r['vehicle_state']['position_ue_m'].__setitem__(0,999)),
        'pose_source_changed':(tail,lambda r:r['vehicle_state'].update(timestamp=0)),
    }
    if mode in ('normal-stop','stop-protection','normal-stop30'):
        hold=next(i for i,r in enumerate(rows) if r['native']['admission']['normal_stop'])
        def req(field,fmt,value):
            def change(r):
                q=r['native']['native_export']['stop_requests'];q[0]=rewrite(q[0],field,fmt,value)
            return change
        def ack(r):
            q=r['native']['native_export']['stop_results'];q[0]=rewrite(q[0],-5,'B',0)
        changes.update({
            'missing_stop_ACK':(hold,lambda r:r['native']['native_export']['stop_results'].__setitem__(0,None)),
            'rejected_ACK_valid_crc':(hold,ack),
            'wrong_lease_epoch_valid_crc':(hold,req(-28,'I',41)),
            'changed_lease_identity_valid_crc':(hold,req(-24,'I',999)),
            'expired_lease_valid_crc':(hold,req(-12,'Q',0)),
            'future_lease_valid_crc':(hold,req(-20,'Q',999999999999)),
        })
        if mode in ('normal-stop','normal-stop30'):
            complete=next(i for i,r in enumerate(rows) if r['native']['speed_terminal']['stop_state']==5)
            changes.update({
                'false_HV_confirmation':(complete,lambda r:r['native']['speed_terminal'].update(power_off=False)),
                'missing_original_PowerStatus':(complete,lambda r:r['native']['speed_terminal'].update(power_status=None)),
            })
        else:
            injected=next(i for i,r in enumerate(rows) if r['native']['speed_terminal']['detection_ns'])
            changes.update({
                'handoff_restamp':(injected,lambda r:r['native'].update(stop_handoff_ns=1)),
                'missing_injection':(injected,lambda r:r['native']['speed_terminal'].update(detection_ns=0)),
                'early_injection':(injected,lambda r:r['native']['speed_terminal'].update(detection_ns=r['native']['stop_handoff_ns'])),
                'reopened_credit':(injected,lambda r:r['native'].update(credit_mask=255)),
                'missing_protection_owner':(injected,lambda r:r['native']['native_export'].update(protection_selected_mask=127)),
                'reopened_hold':(injected,lambda r:r['native']['admission'].update(normal_stop=True)),
                'false_complete':(injected,lambda r:r['native']['speed_terminal'].update(stop_state=5,power_off=True)),
                'moving_during_protection':(injected,lambda r:r['physics'].update(body_forward_velocity_m_s=.1)),
            })
    else:
        changes.update({
            'missing_speed_fault':(trigger,lambda r:r['native']['speed_terminal'].update(speed_fault=0)),
            'detection_restamp':(trigger,lambda r:r['native']['speed_terminal'].update(detection_ns=0)),
            'reopened_credit':(trigger,lambda r:r['native'].update(credit_mask=255)),
            'missing_protection_owner':(trigger,lambda r:r['native']['native_export'].update(protection_selected_mask=127)),
        })
    if mode=='normal-stop30':
        changes.update({
            'changed_stop_budget':(trigger,lambda r:r['native']['stop_configuration'].update(braking_timeout_ns=5000000000)),
            'changed_stop_deceleration':(trigger,lambda r:r['native']['stop_configuration'].update(deceleration_mps2=2)),
            'pose_wire_restamp':(trigger,lambda r:r['route_pose'].update(source_ns=1)),
            'lateral_result_mutation':(trigger,lambda r:r['native']['lateral_control'].update(curvature_inv_m=1)),
        })
    rejected={}
    for name,(i,change) in changes.items():
        original=rows[i];rows[i]=copy.deepcopy(original);change(rows[i])
        try:audit(a.directory,rows)
        except (ValueError,KeyError,TypeError,AssertionError) as error:rejected[name]=str(error)
        else:raise ValueError('accepted mutation '+name)
        finally:rows[i]=original
    result=dict(status='PASS_TERMINAL_ORACLE_MUTATIONS',baseline=baseline,rejected=rejected)
    a.output.write_text(json.dumps(result,indent=2)+'\n');print('PASS',len(rejected),'terminal mutations')
if __name__=='__main__':main()

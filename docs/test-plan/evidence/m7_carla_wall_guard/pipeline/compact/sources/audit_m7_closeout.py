#!/usr/bin/env python3
"""Audit natural protected stop, client-loss shutdown, and clock feasibility together."""
import argparse
import copy
import gzip
import json
from pathlib import Path
import re
from audit_m7_1q_native import check


def load_rows(directory):
    path=directory/'trace.jsonl'
    with (path.open() if path.exists() else gzip.open(str(path)+'.gz','rt')) as stream:
        return [json.loads(line) for line in stream]


def clock_evidence(rows):
    windows=[];widths=[];latencies=[];native_gaps=[];unpaused_latencies=[];unpaused_gaps=[]
    for left,right in zip(rows,rows[1:]):
        if 'receipt' not in left:continue
        receipt=left['receipt']
        check(receipt['physics_acquisition_clock']=='host_CLOCK_MONOTONIC; diagnostic_not_CAN_mapping','clock provenance')
        low=int(receipt['physics_acquisition_begin_ns']);high=int(receipt['physics_acquisition_end_ns'])
        check(left['wall_advance_begin_ns']<=low<=high<=left['wall_receipt_ns']<=right['wall_native_begin_ns'],'original acquisition bracket/order')
        ns=round(receipt['simulation_end_seconds']*1e9)
        check(ns==right['native']['now_ns'],'original simulation source unchanged')
        windows.append((low-ns,high-ns));widths.append(high-low)
        latencies.append(right['wall_native_end_ns']-low)
        native_gaps.append(right['wall_native_begin_ns']-left['wall_native_end_ns'])
        # i=150 deliberately pauses for 250ms after its receipt.
        if left['index']!=150:
            unpaused_latencies.append(latencies[-1]);unpaused_gaps.append(native_gaps[-1])
    check(len(windows)>100,'clock acquisition observations')
    low=max(w[0] for w in windows);high=min(w[1] for w in windows)
    return dict(samples=len(windows),acquisition_bracket_max_ns=max(widths),
        acquisition_to_next_native_end_max_ns=max(latencies),acquisition_to_next_native_end_over_30ms=sum(x>30000000 for x in latencies),
        native_input_gaps_over_2ms=sum(x>2000000 for x in native_gaps),native_input_gap_max_ns=max(native_gaps),
        excluding_intentional_pause=dict(excluded_left_index=150,samples=len(unpaused_latencies),
            acquisition_to_next_native_end_max_ns=max(unpaused_latencies),
            acquisition_to_next_native_end_over_30ms=sum(x>30000000 for x in unpaused_latencies),
            native_input_gap_max_ns=max(unpaused_gaps),native_input_gaps_over_2ms=sum(x>2000000 for x in unpaused_gaps)),
        constant_offset_intersection_ns=[low,high],constant_offset_possible=low<=high,
        clock_mapping_accepted=False,normal_wall_runtime_accepted=False,
        note='offset intervals are mapping candidates only; ages use same-host monotonic pairs; no CAN rewrite')


def natural_stop(rows):
    applied=[r for r in rows if 'receipt' in r]
    check(len(applied)==400,'original 400-interval protection scenario')
    first=None;tail=applied[300:];position=tail[0]['receipt']['physics']['body_world_position_m'];orientation=tail[0]['receipt']['physics']['body_quaternion_xyzw']
    held=0
    for r in applied:
        q=r['receipt'];p=q['physics'];act=q['original_actual']['admitted_actual']
        if q['protected_held_steer_sleep']:
            held+=1
            check(act['protection'] and not act['normal'] and act['torque_nm']==0 and act['pressure_pa']>=1000000,'held policy only original protective Actual')
        if p['sleeping'] and act['protection'] and first is None:first=r['index']
    check(first is not None and held>100,'natural sleep reached under protected hold')
    for r in applied[first:]:
        p=r['receipt']['physics']
        check(p['sleeping'] and p['body_forward_velocity_m_s']==0 and p['com_velocity_world_m_s']==[0,0,0] and
              p['angular_velocity_world_rad_s']==[0,0,0],'exact natural body sleep persists')
        check(all(w['solver_omega_rad_s']==0 for w in p['wheels']),'original solver wheel exact zero')
    for r in tail:
        p=r['receipt']['physics'];q=r['receipt']
        check(p['body_world_position_m']==position and p['body_quaternion_xyzw']==orientation,'stationary pose unchanged')
        check(q['solver_work']['sleeping']==1 and q['solver_work']['count']==0,'original zero-work sleeping solver')
    return dict(status='PASS_EXACT_NATURAL_STOP_FIXED_SCENARIO',first_sleep_index=first,
                sustained_sleep_intervals=len(applied)-first,exact_stationary_tail_intervals=100,
                held_policy_intervals=held,velocity_epsilon_used=False,forced_sleep_or_pose_setter_used=False)


def client_loss(directory,server):
    result=json.loads((directory/'result.json').read_text());rows=load_rows(directory)
    check(result['status']=='CLIENT_LOSS_INJECTED_NOT_CLEANUP' and server['probe_exit']==73,'actual abrupt client exit')
    check(result['receipts']==result['settlements']==199 and len(rows)==200,'settled loss boundary')
    loss=result['client_loss']
    check(loss['no_cleanup'] and loss['no_stage_pending'] and loss['synchronous_mode'],'no cleanup/tick disguised as disconnect')
    check(server['server_exit']==130 and 'forced_stop' not in server,'graceful server exit')
    elapsed=server['exit_observed_monotonic_ns']-server['stop_requested_monotonic_ns']
    check(0<elapsed<=30000000000,'original 30s shutdown bound')
    archived=directory.parent/(directory.name+'-runtime')/'server.log'
    path=archived if archived.exists() or Path(str(archived)+'.gz').exists() else Path(server['logs']['server.log']['path'])
    with (path.open() if path.exists() else gzip.open(str(path)+'.gz','rt')) as f:log=f.read()
    frames=re.findall(r'M7Shutdown: cancelled tick wait; frame=(\d+); physics disabled',log)
    check(frames and all(int(x)==result['frame'] for x in frames),'exit wait cancelled without advancing frame')
    return dict(status='PASS_CLIENT_LOSS_SHUTDOWN_LIMITED',server_exit=130,shutdown_elapsed_ns=elapsed,
                original_frame=result['frame'],cancelled_wait_frames=list(map(int,frames)),cleanup_called=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path)
    p.add_argument('--kind',choices=('clock','sleep','client-loss'),required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=dict(status='FAIL')
    try:
        rows=load_rows(a.directory)
        result={'clock':clock_evidence(rows)}
        if a.kind=='sleep':
            result['stop']=natural_stop(rows)
            from audit_m7_1r_work import validate
            rejected={}
            for name in ('residual_body','changed_pose','missing_solver_hold','changed_previous_effort','missing_previous_protection'):
                bad=list(rows);bad[349]=copy.deepcopy(rows[349]);bad[350]=copy.deepcopy(rows[350])
                r=bad[350]['receipt']
                if name=='residual_body':r['physics']['com_velocity_world_m_s'][0]=1e-30
                if name=='changed_pose':r['physics']['body_world_position_m'][0]+=1e-9
                if name=='missing_solver_hold':r['solver_work']['protected_steer_hold']=False
                if name=='changed_previous_effort':bad[349]['receipt']['physics']['wheels'][0]['set_steer_right_rad']+=1e-12
                if name=='missing_previous_protection':bad[349]['receipt']['original_actual']['admitted_actual']['protection']=False
                try:
                    validate(bad[350],bad[349]);natural_stop(bad)
                except ValueError as error:rejected[name]=str(error)
                else:raise ValueError('accepted stop corruption '+name)
            result['rejected_stop_corruptions']=rejected
        bad=list(rows);bad[10]=copy.deepcopy(rows[10]);bad[10]['receipt']['physics_acquisition_end_ns']=str(bad[10]['wall_receipt_ns']+1)
        try:clock_evidence(bad)
        except ValueError as error:result['rejected_clock_corruption']=str(error)
        else:raise ValueError('accepted acquisition timestamp outside original bracket')
        if a.kind=='client-loss':result['shutdown']=client_loss(a.directory,json.loads((a.directory.parent/('server-'+a.directory.name+'.json')).read_text()))
        result['status']='PASS_REQUESTED_SCOPE_ONLY'
    except Exception as error:result.update(status='FAIL',error=repr(error))
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));return int(result['status']=='FAIL')

if __name__=='__main__':raise SystemExit(main())

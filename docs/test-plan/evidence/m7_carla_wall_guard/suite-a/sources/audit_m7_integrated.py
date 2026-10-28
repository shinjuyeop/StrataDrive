#!/usr/bin/env python3
"""Scenario, sensor-source, and wall-gap audit supplementing the raw-wire/work oracle."""
import argparse
import gzip
import json
import math
from pathlib import Path
from audit_m7_1q_native import check, wire, frame


def stats(values):
    values=sorted(values)
    if not values:return None
    return dict(count=len(values),mean_ms=sum(values)/len(values)/1e6,
                p95_ms=values[math.ceil(len(values)*.95)-1]/1e6,
                p99_ms=values[math.ceil(len(values)*.99)-1]/1e6,max_ms=values[-1]/1e6,
                above_2ms=sum(v>2000000 for v in values),above_4ms=sum(v>4000000 for v in values))


def audit(directory):
    result=json.loads((directory/'result.json').read_text())
    check(result['status'].startswith('PASS'),'runtime did not pass')
    path=directory/'trace.jsonl'
    opening=open if path.exists() else gzip.open
    if not path.exists():path=path.with_suffix('.jsonl.gz')
    with opening(path,'rt') as f:rows=[json.loads(line) for line in f]
    complete=[r for r in rows if 'receipt' in r]
    phase_checks=[]
    if 'scenario' in result:
        phases=[list(map(float,line.split())) for line in result['scenario']['text'].splitlines() if line and not line.startswith('#')]
        initial=int(result['binding']['logical_begin_ns'])
        for row in complete:
            proof=row['native']['native_export']
            if not proof['normal']:continue
            for role,packet in enumerate(proof['commands']):
                q=wire(packet,0 if role<2 else 1,role+2,5)
                q.get('IQQQI');frame(q,role,False);check(q.get('B')==1,'original root request missing')
                epoch,seq,source,expiry,accel,curvature,braking,hold=q.get('IIQQdddB')
                phase=next(p for p in phases if source-initial<p[0]*1000000)
                check([accel,curvature,braking,hold]==phase[1:],'controller request phase/source mismatch')
        if result['fault']=='none':
            for lo,hi,name in ((100,350,'acceleration_left'),(350,450,'regeneration'),(450,650,'friction_hold'),(650,900,'restart_right')):
                part=[r['receipt'] for r in complete if lo<=r['index']<hi]
                check(len(part)==hi-lo,'scenario phase coverage')
                actual=[r['original_actual']['admitted_actual'] for r in part]
                speed=[r['physics']['body_forward_velocity_m_s'] for r in part]
                work=[sum(r['solver_work']['motor_work_j']) for r in part]
                zero=[r for r in part if all(w['solver_omega_rad_s']==0 for w in r['physics']['wheels'])]
                if name=='acceleration_left':check(speed[-1]>speed[0] and any(a['angle_rad']>0 for a in actual),'acceleration/left Actual')
                if name=='regeneration':check(any(a['torque_nm']<0 for a in actual) and min(work)<0,'signed regeneration not observed')
                if name=='friction_hold':check(zero and any(a['pressure_pa']>0 for a in actual),'friction/wheel stop not observed')
                if name=='restart_right':check(speed[-1]>speed[0] and any(a['angle_rad']<0 for a in actual),'restart/right Actual')
                phase_checks.append(dict(name=name,frames=len(part),speed_m_s_range=[min(speed),max(speed)],
                    actual_torque_nm_range=[min(a['torque_nm'] for a in actual),max(a['torque_nm'] for a in actual)],
                    pressure_pa_range=[min(a['pressure_pa'] for a in actual),max(a['pressure_pa'] for a in actual)],
                    negative_motor_work_frames=sum(v<0 for v in work),motor_work_j=sum(work),zero_wheel_frames=len(zero),
                    zero_wheel_body_velocity_m_s_range=([min(r['physics']['body_forward_velocity_m_s'] for r in zero),max(r['physics']['body_forward_velocity_m_s'] for r in zero)] if zero else None)))
    state_times={r['frame']:r['simulation_seconds'] for r in rows}
    for row in rows:
        state=row.get('vehicle_state')
        if state is None:continue
        check(state['frame']==row['frame'] and state['timestamp']==row['simulation_seconds'],'state source/time')
        check(state['valid'] or row['index']==0,'missing noninitial state')
    sensors=None
    if (directory/'sensors.json').exists():
        sensors=json.loads((directory/'sensors.json').read_text())
        check(not sensors['gt_control_use'],'GT must never be a control input')
        start=int(result['binding']['frame']);end=start+result['receipts']
        expected=list(range((start//5+1)*5,end+1,5))
        # Receipt end snapshot may be absent only on a deliberately interrupted stream.
        for row in complete:state_times[int(row['receipt']['frame'])]=row['receipt']['simulation_end_seconds']
        for name,stream in sensors['streams'].items():
            observed=[r['frame'] for r in stream]
            dropped=[r['frame'] for r in sensors['dropped'] if r['source_identity']=='CARLA.'+name]
            check(observed==[f for f in expected if f not in dropped],'camera frame coverage/50ms schedule')
            check(len(set(observed))==len(observed),'camera duplicate')
            for r in stream:
                check(r['timestamp']==state_times[r['frame']],'camera timestamp must equal original matching state')
                check(r['bytes']==320*240*4 and r['width']==320 and r['height']==240,'camera payload geometry')
                check(r['ego_id']==int(result['binding']['actor']) and r['validity']=='VALID','camera identity/validity')
                if name=='gt':check(r['use']=='TRAIN_EVAL_ONLY','GT isolation')
        if result['fault']=='rgb-drop':check(len(sensors['dropped'])==1 and sensors['errors'] and result['fault_observed'],'drop must block next tick')
        else:check(not sensors['errors'] and not sensors['dropped'],'unexpected sensor gap')
        sensors=dict(rgb=len(sensors['streams']['rgb']),gt=len(sensors['streams']['gt']),
                     intentional_drops=len(sensors['dropped']),first_frame=expected[0],last_frame=expected[-1],
                     original_timestamp_match=True,gt_control_use=False)
    native=[r['wall_native_end_ns']-r['wall_native_begin_ns'] for r in rows if 'wall_native_end_ns'in r]
    gaps=[b['wall_native_begin_ns']-a['wall_native_end_ns'] for a,b in zip(rows,rows[1:]) if 'wall_native_end_ns'in a and 'wall_native_begin_ns'in b]
    advance=[r['wall_receipt_ns']-r['wall_advance_begin_ns'] for r in complete]
    # This process blocks in stdin between bursts. A >2ms gap demonstrates no
    # native owner execution opportunity; it is not a per-job deadline latency.
    wall=dict(clock='host CLOCK_MONOTONIC; no simulation-to-wall subtraction',
              native_roundtrip=stats(native),native_idle_lower_bound=stats(gaps),advance_to_receipt=stats(advance),
              production_2ms_4ms_gate='NOT_ACCEPTED',per_job_4ms_deadlines='NOT_INSTRUMENTED',
              observed_native_opportunity_gap_violation=any(v>2000000 for v in gaps),
              includes_json_solver_trace_and_explicit_250ms_pause=True)
    return dict(status='PASS_BOUNDED_INTEGRATED_AUDIT',receipts=len(complete),phases=phase_checks,sensors=sensors,wall=wall,
                full_m7_closed=False,body_stationary_acceptance=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=audit(a.directory)
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':main()

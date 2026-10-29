#!/usr/bin/env python3
"""Independent raw-trace oracle; limited to wheel sensor / native feedback."""
import argparse
import ast
import json
import math
from pathlib import Path


def require(value, why):
    if not value:
        raise ValueError(why)


def analyze(path):
    summary=json.loads((path/'capture/summary.json').read_text())
    process=json.loads((path/'process.json').read_text())
    rows=[json.loads(line) for line in (path/'capture/frames.jsonl').read_text().splitlines()]
    require(summary['status']=='OBSERVED' and len(rows)==400,'complete observation missing')
    require(summary['cleanup']['settings_restored'] and not summary['cleanup']['remaining_owned'] and not summary['cleanup'].get('errors'),'cleanup')
    require(process['client_exit']==0 and process['remaining_listeners']=='','client/listeners')
    require(summary['apply_calls']==0 and summary['driving'] is False,'actuation claim')
    forbidden={'apply_control','apply_batch','apply_batch_sync','apply_ackermann_control','apply_physics_control',
               'set_transform','set_location','set_target_velocity','add_force','add_impulse','add_torque',
               'set_wheel_pitch_angle','set_wheel_steer_direction','set_autopilot','set_simulate_physics'}
    calls={n.func.attr for n in ast.walk(ast.parse((path/'runner.py').read_text())) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
    require(not calls.intersection(forbidden),'actuation API in runner')
    sources={}
    returned=armed=0
    max_age=max_quant=0
    for i,row in enumerate(rows):
        require(row['index']==i and row['frame']==row['bracket_after_frame'] and row['repeated_omega_equal'],'frame/bracket')
        require(row['actor']==summary['ego']['id'] and (row['run'],row['application'],row['plant'])==(1,42,7),'identity')
        require(row['clock']==0x4D3746554E435449 and abs(row['delta_s']-.01)<1e-6,'clock')
        if i:
            require(row['frame']==rows[i-1]['frame']+1 and abs(row['sim_s']-rows[i-1]['sim_s']-.01)<1e-6,'cadence')
        require(len(row['wheel'])==4 and all(math.isfinite(w['omega']) for w in row['wheel']),'wheel validity')
        source=round(row['sim_s']*1e9)
        sources[source]=(row['wheel'][2]['omega']+row['wheel'][3]['omega'])/2
        if 'native' not in row:
            continue
        n=row['native']
        require(n['status']=='WHEEL_SHADOW_BARRIER' and not n['driving'] and
                n['normal_apply']=='BLOCKED_CALIBRATION_AND_PLANT_OWNERSHIP','native boundary')
        require(n['now_ns']==source and n['next_frame']==row['frame']+1 and n['service_mask']==255,'native tick')
        if n['sensor_wheel']:
            w=n['sensor_wheel']
            require(w['source_ns'] in sources and w['rad_s']==sources[w['source_ns']], 'sensor source/value changed')
            require(0<=source-w['source_ns']<=10001000,'pending sample lost or future')
        if n['returned_wheel']:
            returned+=1
            w=n['returned_wheel']
            require(w['source_ns'] in sources,'returned acquisition not an observed source')
            expected=math.floor(sources[w['source_ns']]/.01+.5)*.01
            err=abs(w['rad_s']-expected)
            max_quant=max(max_quant,err)
            require(err<1e-10,'CAN value differs from original .01 rad/s quantization')
            age=source-w['source_ns']
            require(0<=age and age+10000000<=30000000,'wheel interval freshness')
            max_age=max(max_age,age)
        if n['armed_fixture']:
            armed+=1
            require(n['credit_mask']==n['release_mask']==255 and n['returned_wheel'] is not None,'armed without evidence')
        if n['regen_oldest_ns'] is not None:
            require(n['regen_oldest_ns']<=source,'future capability dependency')
    if 'native' in rows[0]:
        require(armed>0 and returned>0,'native path did not arm/return')
        neg=summary['negative']
        require(neg['reply']['status']=='FAIL' and neg['reply']['next_frame'] is None and
                neg['before_frame']==neg['after_frame'] and summary['native_exit']==1,'negative tick')
        require(len(summary['injections'])==1 and summary['injections'][0]['wall_end_ns']-summary['injections'][0]['wall_begin_ns']>=250000000,'pause')
    moving=max(abs(w['omega']) for row in rows for w in row['wheel'])
    residual=max(abs(w['torque']+w['long_force']*summary['radii_cm'][i]/100)
                 for row in rows for i,w in enumerate(row['wheel']) if w['torque'] is not None and w['long_force'] is not None)
    return dict(wheel_observation='PASS',native_feedback='PASS' if 'native' in rows[0] else 'NOT_RUN',
                rows=len(rows),native_armed_rows=armed,native_returned_rows=returned,
                max_abs_omega_rad_s=moving,max_forward_m_s=max(r['forward_m_s'] for r in rows),
                max_returned_source_age_ns=max_age,max_CAN_roundtrip_error=max_quant,
                telemetry_torque_plus_long_force_radius_max_Nm=residual,
                normal_driving='NOT_CONNECTED',energy_fidelity='NOT_VALIDATED',
                server_shutdown='PASS' if process['server_exit']==0 else 'FAIL',server_exit=process['server_exit'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('attempt',type=Path)
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    try:
        result=analyze(args.attempt)
        code=0
    except Exception as e:
        result=dict(wheel_observation='FAIL',native_feedback='NOT_ACCEPTED',error=str(e))
        code=1
    text=json.dumps(result,indent=2)+'\n'
    if args.output:
        args.output.write_text(text)
    print(text,end='')
    return code


if __name__=='__main__':
    raise SystemExit(main())

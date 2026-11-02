#!/usr/bin/env python3
"""Original speed, physical stopping, StopLease ACK and PowerStatus evidence."""
import argparse
import binascii
import copy
import json
import math
from pathlib import Path
import struct
import sys
from audit_m7_1q_native import check,wire,frame
from evidence_io import json_rows
from m8_stop_wire import stop_selection
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'models/longitudinal'))
from model import SpeedPI,Sample


def power_status(packet,now):
    q=wire(packet,1,7,9);check(q.get('B')==3 and q.get('IBBB')==(0x283,1,0,64),'original PowerStatus envelope')
    p=q.take(64)
    check(binascii.crc_hqx(p[:29]+p[31:]+struct.pack('<H',0x1302),0xffff)==int.from_bytes(p[29:31],'little'),'PowerStatus P05')
    seq,epoch,source,causal=struct.unpack_from('<IIQI',p,4)
    input_ns=int.from_bytes(p[44:52],'little')
    check(epoch==42 and input_ns<=source<=now and now-source<=50000000 and now-input_ns<=70000000,'original PowerStatus acquisition')
    return dict(source_ns=source,input_ns=input_ns,off=p[:2]==b'\0\0' and p[3]==1 and p[32:35]==b'\0\0\0' and p[42]==1 and int.from_bytes(p[40:42],'little')*.1<=30,
        bus_v=int.from_bytes(p[40:42],'little')*.1,contactors=list(p[32:35]))


def audit(directory,rows=None):
    result=json.loads((directory/'result.json').read_text());mode=result['speed_terminal']
    server=json.loads((directory.parent/('server-'+directory.name+'.json')).read_text())
    high=mode=='normal-stop30';ticks=6000 if high else 4000;control_count=1750 if high else 750
    event_ns=35000000000 if high else 15000000000;budget_ns=10000000000 if high else 5000000000
    route_audit=None
    if high:
        from m8_stop30_oracle import audit_route
        route_audit=audit_route(directory,rows)
    check(mode in ('normal-stop','input-loss','stop-protection','normal-stop30') and result['status'].startswith('PASS') and result['requested_ticks']==ticks,'terminal scope/runtime')
    check(all(c['status']=='PASS' for c in result['cases']) and server['server_exit']==130 and 'forced_stop' not in server,'lifecycle and owned shutdown')
    check(result['receipts']==result['settlements']==ticks and not result['wall_runtime_accepted'],'complete functional work denominators')
    c=SpeedPI();c.initialize(42);controls={};physics={};actual_wheel={};origin=trigger=None;count=0
    state=[];lease=None;causal=None;held=0;complete_ns=None;hold_ns=None;off=None;response={};trigger_speed=None;stop_point=None;streak=0;max_error=0.;handoff=None;injection=None;last_hold=None
    for i,row in enumerate(json_rows(directory/'trace.jsonl') if rows is None else rows):
        now=math.floor(row['simulation_seconds']*1e9+.5);n=row['native'];proof=n['native_export'];t=n['speed_terminal'];s=n.get('speed_control');ph=row['physics']
        check(i==row['index'] and row['frame']==int(result['binding']['frame'])+i,'continuous observation/frame')
        if high:check(n['stop_configuration']==dict(id='normal-stop30-a1-t10-v1',deceleration_mps2=1,braking_timeout_ns=10000000000,confirmation_ns=60000000,shutdown_timeout_ns=2000000000),'original stop30 config')
        v=ph['body_forward_velocity_m_s'];check(math.isfinite(v),'finite body velocity')
        omega=[w['solver_omega_rad_s'] for w in ph['wheels']];check(all(math.isfinite(x) for x in omega),'finite solver wheels')
        physics[now]=(omega[2]+omega[3])/2
        a=[frame(wire(p,0 if j<2 else 1,7,9),j,True,require_wheel=False) for j,p in enumerate(proof['actual']) if p]
        if len(a)==3 and a[2]['wheel_valid']:actual_wheel[a[2]['wheel_source']]=a[2]['wheel']
        if s:
            seq=s['sequence']
            if origin is None:origin=s['origin_ns'];trigger=origin+event_ns
            if seq in controls:check(s==controls[seq],'unchanged held final PI state')
            else:
                check(seq==len(controls) and s['release_ns']==origin+seq*20000000 and s['release_ns']<trigger,'original PI grid stops at event')
                source=s['source_ns'];check(source in actual_wheel and source in physics and 0<=s['release_ns']-source<=30000000,'original current Drive acquisition')
                check(abs(actual_wheel[source]-physics[source])<=.005+1e-12 and s['speed_mps']==actual_wheel[source]*.355,'original wheel speed')
                expected_target=((30 if high else 10)/3.6)*min((s['release_ns']-origin)*1e-9/(20 if high else 10),1)
                check(abs(s['target_mps']-expected_target)<1e-12 and s['expiry_ns']==s['release_ns']+30000001 and s['input_expiry_ns']==source+60000001,'unchanged target and authority')
                out=c.step(s['release_ns'],s['target_mps'],Sample(42,source,source,s['speed_mps']),True)
                check(out.valid and all(math.isfinite(s[k]) for k in ('integral','acceleration_mps2')),'finite PI result')
                error=max(abs(out.acceleration-s['acceleration_mps2']),abs(out.integral-s['integral']));max_error=max(max_error,error)
                check(error<=1e-12,'independent original PI arithmetic');controls[seq]=copy.deepcopy(s)
        if t['trigger_ns']:
            check(t['trigger_ns']==trigger and now>=trigger,'fixed original terminal event')
            if trigger_speed is None:trigger_speed=v*3.6;check((29 if high else 9)<=trigger_speed<=(31 if high else 11),'moving at frozen terminal speed')
            check(len(controls)==control_count,'no new PI after terminal event')
            if high and n['stop_handoff_ns']:
                if handoff is None:check(t['stop_state']==4 and now-10000000<=n['stop_handoff_ns']<=now,'stop30 first PowerDown job');handoff=n['stop_handoff_ns']
                check(n['stop_handoff_ns']==handoff and handoff>trigger,'stop30 immutable handoff')
            if mode=='stop-protection' and n['stop_handoff_ns']:
                if handoff is None:
                    check(t['stop_state']==4 and now-10000000<=n['stop_handoff_ns']<=now,'first original PowerDown job')
                    handoff=n['stop_handoff_ns']
                check(n['stop_handoff_ns']==handoff and handoff>trigger,'immutable acknowledged handoff')
                if t['detection_ns']:
                    check(t['detection_ns']==handoff+100000000 and now>=t['detection_ns'],'fixed handoff protection injection')
                    injection=t['detection_ns']
                    check(last_hold is not None and last_hold<injection and held>0,'accepted hold precedes protection')
                    check(not t['power_off'] and t['stop_state']!=5,'no false NormalStop completion')
                    check(abs(v)<=.001 and all(w==0 for w in omega),'stationary throughout protection')
                else:check(now<handoff+100000000,'missing handoff protection injection')
            if mode=='input-loss' or (mode=='stop-protection' and injection is not None):
                response_origin=trigger if mode=='input-loss' else injection
                if mode=='input-loss':check(t['detection_ns']==trigger and t['speed_fault']==3,'current speed input rejected in original job')
                else:check(t['speed_fault']==0,'separate safety injection from speed input loss')
                check(int(proof['protection_since_ns'])==response_origin and proof['protection_selected_mask']==255 and n['credit_mask']==0,'local protection selected')
                check(n['admission']['protection'] and not n['admission']['normal_stop'] and not proof['normal'],'exclusive terminal protection')
                for label,j,predicate in [('torque',2,lambda x:x==0),('brake',1,lambda x:x>=1000000)]:
                    if label not in response and len(a)==3 and a[j]['origin']==2 and predicate(a[j]['value']):
                        response[label]=dict(source_delay_ns=a[j]['source']-response_origin,observed_delay_ns=now-response_origin)
            else:
                check(t['stop_fault']==t['speed_fault']==0 and t['stop_state'] in (2,3,4,5),'NormalStop state without protection')
                if n['admission']['normal_stop']:
                    if high:check(abs(v)<=.001 and all(w==0 for w in omega),'stop30 stationary during terminal hold')
                    if hold_ns is None:hold_ns=now
                    lease=stop_selection(proof,a,now,lease,causal);held+=1;last_hold=now
                    check(lease[2]>=trigger and (lease[2]-trigger)%20000000==0 and lease[1]==(lease[2]-trigger)//20000000,'stop issuer original 20ms roots')
                elif proof['normal']:causal=[v['causal'] for v in a]
                if t['stop_state']==5:
                    p=power_status(t['power_status'],now)
                    check(t['power_off'] and p['off'] and held>0 and a[2]['value']==0,'independent terminal HV-off')
                    if complete_ns is None:complete_ns=now;off=p
            stationary=abs(v)<=.001 and all(w==0 for w in omega)
            streak=streak+1 if stationary else 0
            if streak==100 and stop_point is None:stop_point=now-99*10000000
        elif trigger is not None:check(now<trigger,'missing fixed event')
        vs=row['vehicle_state']
        if vs['valid']:
            check(vs['frame']==row['frame'] and vs['timestamp']==row['simulation_seconds'] and vs['source_identity']=='CARLA.ActorSnapshot','original pose for stop')
            state.append((now,vs['position_ue_m'],v,omega))
        if 'receipt' in row:count+=1
    check(count==ticks and len(controls)==control_count and trigger_speed is not None and stop_point is not None,'complete control/stop evidence')
    check(0<=stop_point-trigger<=budget_ns,'physical stop within braking budget')
    tail=state[-101:];check(len(tail)==101 and tail[-1][0]-tail[0][0]>=999999000,'last second original coverage')
    drift=max(math.dist(tail[0][1],r[1]) for r in tail)
    check(drift<=.001 and all(abs(r[2])<=.001 and all(w==0 for w in r[3]) for r in tail),'physical stop and pose held')
    if mode in ('normal-stop','normal-stop30'):
        check(complete_ns is not None and complete_ns-trigger<=budget_ns+2000000000 and hold_ns-trigger<=budget_ns,'original braking/shutdown deadlines')
        if high:check(handoff is not None and 0<=complete_ns-handoff<=2000000000,'stop30 independent shutdown budget')
    else:
        if mode=='stop-protection':check(handoff is not None and injection is not None and held>0 and complete_ns is None,'complete stop-to-protection evidence')
        check(set(response)=={'torque','brake'} and all(0<=r['source_delay_ns']<=230000000 and r['observed_delay_ns']<=260000000 for r in response.values()),'physical protection response deadlines')
    result=dict(status='PASS_M8_CARLA_TERMINAL_RESPONSE',mode=mode,controls=len(controls),physics=count,settlements=result['settlements'],
        trigger_ns=trigger,trigger_speed_kmh=trigger_speed,stop_delay_s=(stop_point-trigger)*1e-9,final_pose_drift_m=drift,
        normal_stop_intervals=held,hold_delay_s=None if hold_ns is None else (hold_ns-trigger)*1e-9,
        complete_delay_s=None if complete_ns is None else (complete_ns-trigger)*1e-9,power_off=off,protection_response=response,max_pi_error=max_error,
        wall_realtime_accepted=False)
    if mode=='stop-protection':result.update(handoff_ns=handoff,injection_ns=injection,last_hold_ns=last_hold)
    if high:result.update(handoff_ns=handoff,route=route_audit)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    try:result=audit(a.directory)
    except (ValueError,KeyError,TypeError,AssertionError) as e:result=dict(status='FAIL',error=str(e))
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));return int(result['status']=='FAIL')
if __name__=='__main__':raise SystemExit(main())

#!/usr/bin/env python3
"""M8 simulation-time speed/provenance oracle; wire/work have separate auditors."""
import argparse
import json
import math
from pathlib import Path
from audit_m7_1q_native import check, wire, frame
from evidence_io import json_rows


def target(seconds):
    if seconds < 0:return 0.
    if seconds < 10:return (10/3.6)*seconds/10
    if seconds < 20:return 10/3.6
    if seconds < 30:return (10/3.6)*(30-seconds)/10
    return 0.


def metrics(samples):
    plateau=[abs(speed-10/3.6)*3.6 for t,speed in samples if 15<=t<20]
    stopped=[abs(speed)*3.6 for t,speed in samples if 35<=t<38]
    overspeed=[max(0.,(speed-target(t))/target(t))*100 for t,speed in samples if target(t)>0]
    check(plateau and stopped and overspeed,'complete speed windows')
    return dict(samples=len(samples),plateau_samples=len(plateau),stop_samples=len(stopped),
        max_plateau_error_kmh=max(plateau),max_stop_error_kmh=max(stopped),
        max_positive_target_overspeed_percent=max(overspeed))


def audit(directory,case,corrupt=None):
    result=json.loads((directory/'result.json').read_text())
    events=json.loads((directory/'events.json').read_text())
    server=json.loads((directory.parent/('server-'+directory.name+'.json')).read_text())
    check(result['status'].startswith('PASS') and result['execution_profile']=='m8-speed-v1' and
          result['speed_loop'] and result['continuous_simulation'],'M8 runtime profile')
    check(not result['wall_runtime_accepted'],'functional scope')
    check(all(r['status']=='PASS' for r in result['cases']),'runtime assertions')
    checks={r['name']:r['status'] for r in result['cases']}
    for key in ('speed_calibration','foreign_batch_writer_denied','foreign_tick_denied','ticket_single_use',
                'wall_pause_no_tick_or_restamp','containment_pause_clear_no_tick','latched_no_resume',
                'reset_requires_new_init','ego_destroyed','restored_settings_actors','native_expected_exit'):
        check(checks.get(key)=='PASS','lifecycle: '+key)
    binding=result['binding'];start=int(binding['frame']);count=normal=0
    controls={};wheel_samples={};physics={};body=[];wheel=[];origin=None;last_control=None;last_receipt=None
    terminal=None;seen_normal=False
    for index,row in enumerate(json_rows(directory/'trace.jsonl')):
        if corrupt:corrupt(index,row)
        terminal=row;now=math.floor(row['simulation_seconds']*1e9+.5)
        check(row['index']==index and row['frame']==start+index,'continuous observation identity')
        p=row['physics'];omega=p['wheels']
        physical_speed=(omega[2]['solver_omega_rad_s']+omega[3]['solver_omega_rad_s'])/2
        check(math.isfinite(p['body_forward_velocity_m_s']) and math.isfinite(physical_speed),'finite physics')
        physics[now]=physical_speed;body.append((now,p['body_forward_velocity_m_s']))
        native=row.get('native',{});proof=native.get('native_export')
        if proof and proof['actual'][2]:
            q=wire(proof['actual'][2],1,7,9);act=frame(q,2,True,require_wheel=False)
            if act['wheel_valid']:wheel_samples[act['wheel_source']]=act['wheel']
        s=native.get('speed_control')
        if s:
            seq=s['sequence']
            check(all(type(s[k]) is int for k in ('release_ns','origin_ns','source_ns','expiry_ns','input_expiry_ns','sequence')),'typed control times')
            check(all(math.isfinite(s[k]) for k in ('target_mps','speed_mps','acceleration_mps2','integral')),'finite control')
            if seq in controls:check(s==controls[seq],'unchanged held control')
            else:
                check(seq==len(controls),'control sequence')
                if origin is None:origin=s['origin_ns']
                check(s['origin_ns']==origin and s['release_ns']==origin+seq*20_000_000,'20ms control grid')
                check(s['source_ns'] in physics and s['source_ns'] in wheel_samples,'original wheel acquisition')
                check(s['source_ns']<=s['release_ns']<=now and s['release_ns']-s['source_ns']<=30_000_000,'current sensor age')
                check(s['expiry_ns']==s['release_ns']+30_000_001 and
                      s['input_expiry_ns']==s['source_ns']+60_000_001,'separate request/input authority')
                check(abs(s['speed_mps']-wheel_samples[s['source_ns']]*.355)<1e-12,'original decoded Drive speed')
                check(abs(wheel_samples[s['source_ns']]-physics[s['source_ns']])<=.005+1e-12,'physical wheel quantization')
                check(abs(s['target_mps']-target((s['release_ns']-origin)*1e-9))<1e-12,'fixed target profile')
                check(-5<=s['acceleration_mps2']<=2,'acceleration bounds')
                if last_control:
                    check(s['source_ns']>last_control['source_ns'],'no frozen acquisition reuse')
                    check(abs(s['acceleration_mps2']-last_control['acceleration_mps2'])<=.04+1e-12,'slew bound')
                else:check(abs(s['acceleration_mps2'])<=.04,'initial slew')
                controls[seq]=dict(s);last_control=s
                wheel.append(((s['source_ns']-origin)*1e-9,s['speed_mps']))
        if proof and proof['normal']:
            for role,packet in enumerate(proof['commands']):
                q=wire(packet,0 if role<2 else 1,role+2,5);q.get('IQQQI');frame(q,role,False)
                check(q.get('B')==1,'child context')
                epoch,seq,source,expiry,accel,curvature,braking,hold=q.get('IIQQdddB');oldest,child_expiry=q.get('QQ')
                check(seq in controls,'child has original computed request');s=controls[seq]
                check(epoch==42 and source==s['release_ns'] and expiry==s['expiry_ns'] and
                      accel==s['acceleration_mps2'] and curvature==braking==0 and hold==(s['target_mps']==0),'unchanged computed parent')
                check(oldest<=s['source_ns'] and child_expiry<=s['input_expiry_ns'],'child preserves sensor dependency')
        if 'receipt' not in row:continue
        receipt=row['receipt'];count+=1
        check(int(receipt['frame'])==start+count,'one physics advance per receipt')
        check(all(receipt[k]==binding[k] for k in ('run','session','actor','application','model_sha256')),'one session')
        check(receipt['physics']['generation']==binding['physics']['generation'],'no reset in trajectory')
        if last_receipt:check(receipt['simulation_begin_seconds']==last_receipt['simulation_end_seconds'],'simulation continuity')
        check(abs(receipt['simulation_end_seconds']-receipt['simulation_begin_seconds']-.01)<1e-6,'10ms physics')
        actual=receipt['original_actual']['admitted_actual'];normal+=actual['normal']
        if seen_normal:check(actual['normal'] and not actual['protection'],'uninterrupted normal authority')
        seen_normal|=actual['normal'];last_receipt=receipt
    check(origin is not None and count==result['receipts'] and normal==result['normal_intervals'],'original denominators')
    pause=next(e for e in events if e['request']['op']=='pause')['response']
    reset=next(e for e in events if e['request']['op']=='reset')['response']
    check(int(pause['frame'])==start+count and pause['latched'],'no cleanup/fault physics advance')
    check(reset['latched'] and reset['physics']['inputs_zero'],'reset invalidates authority')
    report=dict(status='PASS_M8_SPEED_SIMULATION_ONLY',case=case,receipts=count,normal_intervals=normal,
        controls=len(controls),origin_ns=origin,wall_realtime_accepted=False,normal_stop_hv_off_accepted=False,failures=[])
    if case=='nominal':
        check(count==result['requested_ticks']==4000 and result['settlements']==4000 and terminal.get('terminal_settlement'),'40s complete work settlement')
        check(checks.get('continuous_final_wheel_stop')=='PASS','terminal wheel stop')
        check(last_control['target_mps']==0 and all(w['solver_omega_rad_s']==0 for w in terminal['physics']['wheels']),'original terminal hold')
        report['body']=metrics([((t-origin)*1e-9,v) for t,v in body]);report['control_wheel']=metrics(wheel)
        for name in ('body','control_wheel'):
            m=report[name]
            for field,limit in (('max_plateau_error_kmh',1),('max_stop_error_kmh',1),('max_positive_target_overspeed_percent',10)):
                if m[field]>limit:report['failures'].append(name+'.'+field)
    elif case=='snapshot':
        check(count==200 and result['status']=='PASS_EXPECTED_SNAPSHOT_STOP' and 'native' not in terminal and
              'snapshot missing/skipped' in terminal['error'],'snapshot withheld before native/advance')
    elif case=='work-missing':
        check(count==200 and terminal['native']['status']=='FAIL' and terminal['native']['next_frame'] is None,'missing work blocks next advance')
    else:raise ValueError('unknown case')
    report['server_clean_exit']=server['status']=='COMPLETE_ISOLATED_RUN' and server['server_exit']==130 and 'forced_stop' not in server
    if not report['server_clean_exit']:report['failures'].append('owned_server_shutdown')
    if report['failures']:report['status']='FAIL'
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path)
    p.add_argument('--case',choices=('nominal','snapshot','work-missing'),required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:result=audit(a.directory,a.case)
    except (ValueError,KeyError,StopIteration,TypeError) as e:result=dict(status='FAIL',error=str(e))
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));return int(result['status']=='FAIL')


if __name__=='__main__':raise SystemExit(main())

#!/usr/bin/env python3
"""Independent raw wall-wire, solver, energy, source and actual job audit."""
import argparse
import binascii
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import struct
from audit_m7_1q_native import check, frame, wire as decode_wire
from audit_m7_1r_work import validate as validate_work
WALL=0x4d374d4f4e4f3031

def wire(value, source, target, tag):return decode_wire(value,source,target,tag,WALL)

def read(path):
    if path.exists():return path.read_text()
    with gzip.open(str(path)+'.gz','rt') as f:return f.read()

def audit(directory):
    result=json.loads(read(directory/'result.json'));meta=json.loads(read(directory/'native.json'))
    rows=[json.loads(s) for s in read(directory/'trace.jsonl').splitlines()]
    jobs=[{k:int(v) for k,v in r.items()} for r in csv.DictReader(read(directory/'native-wall.csv').splitlines())]
    owner=[{k:int(v) for k,v in r.items()} for r in csv.DictReader(read(directory/'native.csv').splitlines())]
    b=result['binding'];initial=meta['initial'];last_frame=int(b['frame']);model=int(b['logical_begin_ns'])
    step=result.get('model_step_ns',10000000)
    check(step in (5000000,10000000),'explicit wall model step')
    if step==5000000:
        check(int(b['model_step_ns'])==step==result['native_initial']['model_step_ns'],'server/native step identity')
    model_file=Path(__file__).resolve().parents[3]/'tools/carla/m7_nodrive/virtual_ev_v1.json'
    check(hashlib.sha256(model_file.read_bytes()).hexdigest()==b['model_sha256'],'accepted V1 model identity')
    vehicle=json.loads(model_file.read_text());L=vehicle['wheels'][0]['offset_x_m']-vehicle['wheels'][2]['offset_x_m']
    half=(vehicle['wheels'][1]['offset_y_right_m']-vehicle['wheels'][0]['offset_y_right_m'])/2
    history={};previous=None;normal=protection=empty=0;since=0;releases=None;total=0.;cursors={};max_age=0;min_margin=10**18
    latencies=[];commit_latencies=[];protected_pressure=[];max_balance=0.;expired=0;terminal=False
    ingress_path=directory/'ingress.json'
    ingress=json.loads(read(ingress_path)) if ingress_path.exists() or Path(str(ingress_path)+'.gz').exists() else []
    ingress_cursor=0;last_ingress=0;permission_cursor=None
    def actual_cursor(role,packet):
        act=frame(wire(packet,0 if role<2 else 1,7,9),role,True,False)
        prev=cursors.get(role)
        if prev:
            if act['seq']==prev['seq']:check(packet==prev['packet'],'cached Actual bytes immutable')
            else:check(act['seq']>prev['seq'] and act['source']>=prev['source'] and
                       0<(act['counter']-prev['counter'])%256<=10,'CAN cursor/P05 progression')
        act['packet']=packet;cursors[role]=act
        return act
    def consume_ingress(reply,upper):
        nonlocal last_ingress,permission_cursor
        check(reply['ok'] and all(reply[k]==b[k] for k in ('run','session','actor')),'ingress scope')
        e=reply['ingress'];at=int(e['at_ns']);observed=int(e['observed_ns']);enable=int(e['enable_ns'])
        check(e['accepted'] and initial<=enable<=observed<=at<=upper and at>last_ingress and at-observed<=4000000,'original ingress clock')
        last_ingress=at
        for role,packet in enumerate(e['actual']):
            act=actual_cursor(role,packet)
            check(act['epoch']==42 and enable<=act['source']<=at and at-act['source']<=30000000,'received original Actual age')
        if e['permission']:
            q=wire(e['permission'],1,4,5);epoch,token,sent,deadline,op=q.get('IQQQI')
            check(epoch==42 and op==0 and q.get('B')==3 and q.get('IBBB')==(0x194,1,0,64),'ingress permission route')
            payload=q.take(64);seq,epoch,source=struct.unpack_from('<IIQ',payload,4)
            check(binascii.crc_hqx(payload[:29]+payload[31:]+struct.pack('<H',0x1204),0xffff)==int.from_bytes(payload[29:31],'little') and
                  epoch==42 and enable<=source<=at and at-source<=50000000,'ingress permission P05/source')
            if permission_cursor:
                ps,pt,pc,pp=permission_cursor
                check((seq==ps and e['permission']==pp) or
                      (seq>ps and source>=pt and 0<(payload[31]-pc)%256<=10),'permission ingress progression')
            permission_cursor=(seq,source,payload[31],e['permission'])
    first_commit={}
    for sample in owner:first_commit.setdefault(sample['energy_end'],sample['now'])
    for row in rows:
        r=row['receipt'];proof=r['original_actual']['native'];out=r['original_actual']['admitted_actual']
        ns=int(r['wall_applied_ns']);end=ns+step
        acq=int(r['physics_acquisition_begin_ns']);upper=int(r['physics_acquisition_end_ns'])
        end=max(end,upper)  # include any actual wall overrun, never hide it behind model dt
        check(initial<=int(proof['observed_ns'])<=ns<=acq<=upper,'same host clock/order')
        check(ns-int(proof['observed_ns'])<=4000000,'original proof job completion age')
        check(int(r['frame'])==last_frame+1 and int(r['logical_begin_ns'])==model and
              int(r['logical_end_ns'])==model+step,'original CARLA frame/model time')
        upto=int(r.get('wall_ingress_count','0'))
        check(ingress_cursor<=upto<=len(ingress),'bounded ingress reference')
        while ingress_cursor<upto:
            consume_ingress(ingress[ingress_cursor],ns);ingress_cursor+=1
        if step==5000000:
            check(int(r['model_step_ns'])==step and ns>=initial+(row['index']+1)*step,'original absolute plant release; no early step')
        check(r['native_clock_domain']=='host_CLOCK_MONOTONIC; separate_CARLA_model_time','explicit two coordinates')
        check(all(r[k]==b[k] for k in ('actor','run','session','application','model_sha256','model_id')),'scope binding')
        check(r['inputs_cleared_after_physics'],'exclusive effort cleared')
        check(not terminal or not proof['normal'],'no normal physics after observed wall fault')
        terminal=terminal or r['wall_authority_expired_during_physics'] or r['wall_fault_after_physics']
        expired+=bool(r['wall_authority_expired_during_physics'])
        protecting=int(proof['protection_since_ns'])!=0
        if out['empty_init']:
            check(not any(proof['actual']) and not proof['normal'] and not protecting and ns-initial<80000000,'bounded zero bootstrap')
            values=[0,0,0];empty+=1
        else:
            check(int(proof['release_mask'])==int(proof['service_mask'])==255,'eight original owners')
            check(releases is None or proof['release']==releases,'immutable release session');releases=proof['release']
            if protecting:
                current=int(proof['protection_since_ns'])
                check(normal>0 and not proof['normal'] and int(proof['credit_mask'])==0 and int(proof['protection_selected_mask'])==255,'terminal protection authority')
                check(int(proof['enable_ns'])<=current<=ns and (not since or since==current),'one-way protection identity')
                since=current;protection+=1
            else:check(not since and int(proof['credit_mask'])==255 and int(proof['protection_selected_mask'])==0,'no normal rearm')
            check(out['protection']==protecting,'protection applied identity')
            plan=None
            for role,packet in enumerate(proof['release']):
                q=wire(packet,role,7,1);rr,phase=q.get('II');pp=q.get('IQQQQ');ack,accepted=q.get('QB')
                check((rr,phase,accepted)==(role,2,1) and pp[0]==42 and initial<=pp[1]<initial+80000000 and
                      pp[2]==pp[1]+2000000000 and pp[3]==int(proof['enable_ns']) and pp[3]>=pp[1]+20000000 and
                      pp[4]==pp[3]+20000000 and pp[3]<=ack<=ns and ack<pp[4]<=pp[2],'original INIT/Release budgets')
                check(plan is None or plan==pp,'same global plan');plan=pp
            credit=None
            for role,packet in enumerate(proof['credit'] if not protecting else []):
                q=wire(packet,7,role,2);pp=q.get('IQQQQ');cc=q.get('IQQ')
                check(pp==plan and cc[1]<=ns and cc[2]==cc[1]+60000000 and cc[2]>end,'original run credit')
                check(credit is None or credit==cc,'same global credit');credit=cc
            values=[];sources=[];actuals=[]
            for role,packet in enumerate(proof['actual']):
                q=wire(packet,0 if role<2 else 1,7,9);act=frame(q,role,True,not protecting)
                check(act['epoch']==42 and int(proof['enable_ns'])<=act['source']<=ns and end-act['source']<=30000000,'Actual original 30ms whole interval')
                if upto:check(cursors[role]['packet']==packet,'applied Actual matches latest original ingress')
                actual_cursor(role,packet)
                sources.append(act['source']);values.append(act['value']);actuals.append(act);max_age=max(max_age,end-act['source'])
            check(max(sources)-min(sources)<=10000000,'original Actual skew')
            drive=actuals[2]
            if not protecting:
                check(drive['wheel_source'] in history and end-drive['wheel_source']<=30000000 and
                      abs(drive['wheel']-history[drive['wheel_source']])<=.005+1e-12,'original wheel acquisition retained')
                max_age=max(max_age,end-drive['wheel_source'])
            else:
                check(values[2]==0 and all(x['state']==3 and x['origin']==2 and x['source']>=since for x in actuals),'zero-only original LocalProtection')
                check(int(out['exclusive_expiry_ns'])==min(sources)+30000001,'unrelaxed protective Actual freshness')
                if values[1]>=1000000:protected_pressure.append(ns)
            if proof['normal']:
                normal+=1
                q=wire(proof['permission'],1,4,5);epoch,token,sent,deadline,op=q.get('IQQQI')
                check(epoch==42 and op==0 and q.get('B')==3 and q.get('IBBB')==(0x194,1,0,64),'permission envelope')
                payload=q.take(64)
                check(binascii.crc_hqx(payload[:29]+payload[31:]+struct.pack('<H',0x1204),0xffff)==int.from_bytes(payload[29:31],'little'),'permission P05')
                check(payload[:4]==b'\x01\x00\x01\x01' and payload[24] in (1,2) and payload[25]==1,'AllowNormal')
                pe,ps,pc=struct.unpack_from('<IQI',payload,8);power_source,oldest,expiry=struct.unpack_from('<QQQ',payload,36)
                check(q.get('B')==0 and q.get('B')==1,'permission parent')
                epoch,seq,source,parent_expiry=q.get('IIQQ')
                check(pe==epoch==42 and pc==seq and source<=ps<=ns and oldest<=power_source<=ps and end-ps<=50000000 and
                      end-source<=50000000 and end-oldest<=70000000 and end<min(expiry,parent_expiry),'original permission coverage')
                for role,packet in enumerate(proof['commands']):
                    q=wire(packet,0 if role<2 else 1,role+2,5);epoch,token,sent,deadline,op=q.get('IQQQI');command=frame(q,role,False)
                    check(epoch==42 and op==0 and q.get('B')==1,'command context')
                    parent_epoch,parent_seq,parent_source,parent_expiry,accel,curvature,braking,hold=q.get('IIQQdddB')
                    oldest,expiry=q.get('QQ');act=actuals[role]
                    check(act['state'] in (1,2) and act['origin']==1 and act['causal']==command['seq'] and command['causal']==parent_seq,'native causal path')
                    check(parent_epoch==42 and command['epoch']==42 and oldest<=parent_source<=command['source']<=act['source'] and
                          end-parent_source<=30000000 and end-command['source']<=30000000 and end-oldest<=70000000 and
                          end<expiry<=min(parent_expiry,command['source']+30000001,parent_source+30000001,oldest+70000001),'unrelaxed command coverage')
                    min_margin=min(min_margin,expiry-end)
            elif not protecting:check(all(x['state']==0 and x['origin']==0 for x in actuals) and values[2]==0,'non-driving INIT')
        check(all(abs(out[k]-v)<1e-12 for k,v in zip(('angle_rad','pressure_pa','torque_nm'),values)),'Actual is sole effort input')
        t=math.tan(values[0]);steer=[-math.atan2(L*t,L-half*t),-math.atan2(L*t,L+half*t),0,0]
        for i,w in enumerate(r['physics']['wheels']):
            check(abs(w['set_drive_nm']-(values[2]/2 if i>=2 else 0))<=1e-5 and abs(w['set_friction_nm']-values[1]*.00025)<=1e-5 and
                  abs(w['set_steer_right_rad']-steer[i])<=1e-7,'V1 original Actual mapping')
            check(w['solver_omega_source']=='PhysX3.4.mWheelSpeeds.direct.v1' and math.isfinite(w['solver_omega_rad_s']),'original wheel source')
            if i>=2:check(w['solver_omega_rad_s']>=0,'raw rear negative')
        raw=row['raw_solver'];row['solver_trace_binding']={k:v for k,v in raw.items() if k!='trace'}
        r['solver_work']['steps']=raw['trace']['steps']
        sums,_,_=validate_work(row,previous,step/1e9);total+=sum(sums)
        settled=row['settlement'];check(settled is not None,'no lost/in-flight completed work')
        check(int(settled['end_ns'])==int(r['work_end_ns']),'one EV frame commit')
        check(math.isclose(settled['total_mechanical_j'],total,rel_tol=1e-13,abs_tol=1e-11),'all raw signed work counted exactly once')
        check(abs(settled['balance_j'])<=.00072,'unchanged M6 energy tolerance')
        accounted=settled['total_mechanical_j']+sum(settled[k] for k in ('motor_loss_j','auxiliary_j','ohmic_j','capacitor_delta_j','circuit_loss_j'))
        check(abs(settled['chemical_j']-accounted-settled['balance_j'])<1e-10,'independent energy ledger')
        check(abs(settled['soc']-(.63-settled['chemical_j']/180000000))<3e-16,'SOC/chemical ledger')
        check(int(settled['observed_ns'])>=upper,'no future receipt consumption')
        committed=first_commit.get(int(r['work_end_ns']))
        check(committed is not None and upper<=committed<=int(settled['observed_ns']),'actual independent owner settlement')
        commit_latencies.append(committed-acq)
        latencies.append(int(settled['observed_ns'])-acq);max_balance=max(max_balance,abs(settled['balance_j']))
        history[acq]=(r['physics']['wheels'][2]['solver_omega_rad_s']+r['physics']['wheels'][3]['solver_omega_rad_s'])/2
        last_frame+=1;model=int(r['work_end_ns']);previous=row
    check(rows and owner and len(rows)==result['receipts'],'complete original records')
    while ingress_cursor<len(ingress):
        consume_ingress(ingress[ingress_cursor],owner[-1]['now']+4000000);ingress_cursor+=1
    stop=owner[-1]['now'];complete=[r for r in jobs if r['deadline_ns']<=stop]
    check({r['owner'] for r in complete}==set(range(10)),'all ten owners measured')
    check(all(r['release_ns']==initial+1000000+r['slot']*2000000 and r['deadline_ns']==r['release_ns']+4000000 for r in complete),'original 2ms/4ms grid')
    check(all(not r['end_ns'] or r['release_ns']<=r['start_ns']<=r['end_ns'] for r in complete),'no fabricated execution')
    missing=sum(not r['end_ns'] for r in complete);late=sum(r['end_ns']>r['deadline_ns'] for r in complete)
    check(all(a['now']<b['now'] for a,b in zip(owner,owner[1:])),'monotonic owner, no replay')
    check(owner[-1]['energy_end']==model,'last completed work settled even after fault')
    check(result['pause']['stable'] and result['pause']['clear'] and result['pause']['latched'] and result['close']['ok'],'pause/close containment')
    reset=result['reset'];check(reset['ok'] and reset['latched'] and reset['reason']=='reset_requires_close_and_new_init' and
        reset['physics']['inputs_zero'] and int(reset['physics']['generation'])>int(b['physics']['generation']),
        'reset invalidates old physics; never evidence of protective stopping')
    sensors=None
    if (directory/'sensors.json').exists() or (directory/'sensors.json.gz').exists():
        s=json.loads(read(directory/'sensors.json'));check(not s['gt_control_use'] and not s['errors'] and not s['dropped'],'GT isolation/camera integrity')
        expected=list(range((int(b['frame'])//5+1)*5,last_frame+1,5));times={int(x['receipt']['frame']):x['receipt']['simulation_end_seconds'] for x in rows}
        for name,stream in s['streams'].items():
            check([x['frame'] for x in stream]==expected,'50ms camera completeness')
            for x in stream:
                check(x['timestamp']==times[x['frame']] and x['ego_id']==int(b['actor']) and x['validity']=='VALID','original camera time/identity')
                if name=='gt':check(x['use']=='TRAIN_EVAL_ONLY','GT never control')
        sensors={k:len(v) for k,v in s['streams'].items()}
    requested=result['status']=='EXECUTED_REQUIRES_AUDIT'
    check(result.get('native_exit')==0 and not result.get('native_forced_stop') and not result.get('cleanup_error'),'native clean lifecycle')
    writer_checks=result.get('writer_checks')
    if writer_checks:
        check(writer_checks['normal_before']>=10 and writer_checks['begin_ns']<=writer_checks['end_ns'] and
              all(writer_checks[k] for k in ('batch_denied','tick_denied','external_stage_denied')),'active writer rejection')
    if result['fault']=='none':accepted=requested and normal>100 and not protection and not meta['first_fault'] and not missing and not late and not expired
    else:accepted=requested and normal>=50 and protection>100 and bool(since) and bool(protected_pressure) and not missing and not late and not expired
    stopped=[x for x in rows if x['receipt']['physics']['sleeping'] and
             all(v==0 for k in ('com_velocity_world_m_s','angular_velocity_world_rad_s') for v in x['receipt']['physics'][k]) and
             all(w['solver_omega_rad_s']==0 for w in x['receipt']['physics']['wheels'])]
    stable_tail=len(rows)>=100 and all(x in stopped and all(x['receipt']['physics'][k]==rows[-1]['receipt']['physics'][k]
               for k in ('body_world_position_m','body_quaternion_xyzw')) for x in rows[-100:])
    if result['fault']!='none':accepted=accepted and stable_tail
    if since:
        check(result.get('fault_request',{}).get('wall_ns',since)<=since,'protection follows actual fault request')
    speeds=[abs(x['receipt']['physics']['body_forward_velocity_m_s']) for x in rows]
    first_stop=next((x for x in stopped if int(x['receipt']['wall_applied_ns'])>=since),None) if since else None
    first_protection=next((x for x in rows if x['receipt']['original_actual']['admitted_actual']['protection']),None)
    return dict(status='PASS_CASE_ONLY' if accepted else 'NOT_ACCEPTED',receipts=len(rows),normal=normal,protection=protection,
        empty=empty,missing_slots=missing,late_slots=late,eligible_slots=len(complete),expired_physics=expired,
        max_whole_interval_age_ns=max_age,min_command_margin_ns=min_margin if normal else None,
        max_receipt_to_ack_proof_ns=max(latencies),max_receipt_to_native_commit_ns=max(commit_latencies),
        model_step_ns=step,model_seconds=len(rows)*step/1e9,
        wall_seconds=(int(rows[-1]['receipt']['physics_acquisition_end_ns'])-initial)/1e9,
        maximum_forward_speed_m_s=max(speeds),active_writer_checks=bool(writer_checks),original_ingress_records=len(ingress),
        first_protective_physics_after_selection_ns=int(first_protection['receipt']['wall_applied_ns'])-since if first_protection else None,
        first_natural_stop_after_selection_ns=int(first_stop['receipt']['physics_acquisition_end_ns'])-since if first_stop else None,
        max_energy_balance_j=max_balance,first_fault=meta['first_fault'],stationary_frames=len(stopped),sensors=sensors,
        stable_last100_pose=stable_tail,first_full_brake_after_selection_ns=protected_pressure[0]-since if protected_pressure else None,full_m7_closed=False)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:r=audit(a.directory)
    except Exception as e:r={'status':'FAIL_AUDIT','error':str(e),'full_m7_closed':False}
    a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));return 0 if r['status']=='PASS_CASE_ONLY' else 1
if __name__=='__main__':raise SystemExit(main())

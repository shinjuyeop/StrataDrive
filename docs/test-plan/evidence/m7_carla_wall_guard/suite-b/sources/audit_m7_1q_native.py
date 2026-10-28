#!/usr/bin/env python3
"""Independent raw-wire/physics oracle; does not trust server admission booleans.

Canonical owner-wire CRC32C, original CAN P05, causal command and whole interval,
original solver -> native sensor/Actual provenance, V1 setter mapping. Functional
only; this is not a solver-work or wall-deadline validator.
"""
import argparse
import binascii
import copy
import gzip
import hashlib
import json
import math
from pathlib import Path
import struct


def check(value, reason):
    if not value: raise ValueError(reason)


class Reader:
    def __init__(self, data): self.data, self.pos = data, 0
    def get(self, fmt):
        fmt = '<'+fmt; size = struct.calcsize(fmt)
        value = struct.unpack_from(fmt,self.data,self.pos);self.pos += size
        return value[0] if len(value)==1 else value
    def take(self,n):
        value = self.data[self.pos:self.pos+n];self.pos+=n
        check(len(value)==n,'wire length');return value


def wire(value, source, target, tag):
    check(value is not None,'missing original owner packet')
    data=bytes.fromhex(value);crc=0xffffffff
    for b in data[:-4]:
        crc ^= b
        for _ in range(8): crc=(crc>>1)^(0x82f63b78 if crc&1 else 0)
    check(crc^0xffffffff == int.from_bytes(data[-4:],'little'),'owner CRC32C')
    r=Reader(data[:-4])
    check(r.get('IHHIIQB') == (0x56524453,1,0,source,target,0x4d3746554e435449,tag),'wire identity/route')
    return r


def frame(r, role, actual):
    check(r.get('B')==role,'frame role')
    can,fd,flags,length=r.get('IBBB')
    check(can==(0x280 if actual else 0x180)+role and fd==1 and flags&~4==0 and
          length==(64 if role==2 and actual else 32),'CAN envelope')
    payload=r.take(64 if role==2 else 32)[:length]
    data_id=0x1000+role*0x100+(2 if actual else 1)
    crc=binascii.crc_hqx(payload[:29]+payload[31:]+struct.pack('<H',data_id),0xffff)
    check(crc==int.from_bytes(payload[29:31],'little'),'P05 CRC')
    check(payload[2:4]==b'\x02\x01' and payload[26:29]==b'\0'*3,'valid schema')
    seq,epoch,source,causal=struct.unpack_from('<IIQI',payload,4)
    value=int.from_bytes(payload[:2],'little',signed=role!=1)*(.0001,1000,.1)[role]
    result=dict(seq=seq,epoch=epoch,source=source,causal=causal,value=value,state=payload[24],origin=payload[25],counter=payload[31])
    if role==2 and actual:
        check(payload[34]==1,'wheel validity')
        result.update(wheel=int.from_bytes(payload[32:34],'little')*.01,wheel_source=int.from_bytes(payload[40:48],'little'),
                      capability_source=int.from_bytes(payload[48:56],'little'),oldest=int.from_bytes(payload[56:64],'little'))
    return result


def audit(directory, model, corrupt=None, work_mode=False, corrupt_index=150):
    report=json.loads((directory/'result.json').read_text())
    b=report['binding'];initial=round(b['simulation_seconds']*1e9)
    path=directory/'trace.jsonl'
    opening=open if path.exists() else gzip.open
    if not path.exists():path=path.with_suffix('.jsonl.gz')
    history={};count=normal=empty=0;max_age=0;min_margin=10**12;max_quant=0;last_frame=int(b['frame'])
    last_end=b['simulation_seconds'];cursors={};torques=[];speed=[]
    protection_since=0;protection_count=0;release_packets=None
    L=model['wheels'][0]['offset_x_m']-model['wheels'][2]['offset_x_m']
    half=(model['wheels'][1]['offset_y_right_m']-model['wheels'][0]['offset_y_right_m'])/2
    with opening(path,'rt') as f:
        for line in f:
            row=json.loads(line)
            if corrupt and row['index']==corrupt_index: corrupt(row)
            ns=math.floor(row['simulation_seconds']*1e9+.5)
            check(row['frame']==last_frame and row['simulation_seconds']==last_end,'input continuity')
            wheels=row['physics']['wheels']
            check(len(wheels)==4 and all(w['solver_omega_source']=='PhysX3.4.mWheelSpeeds.direct.v1' and
                  math.isfinite(w['solver_omega_rad_s']) for w in wheels),'solver source')
            history[ns]=(wheels[2]['solver_omega_rad_s']+wheels[3]['solver_omega_rad_s'])/2
            if 'receipt' not in row:
                if work_mode and row.get('terminal_settlement'): continue
                check((row['index']==200 and report['fault']!='none') or
                      (report['fault']=='rgb-drop' and row['native']['admission']['ok'] and 'fault_observed' in report),
                      'unexpected incomplete interval');continue
            n=row['native'];proof=n['native_export'];r=row['receipt'];out=r['original_actual']['admitted_actual']
            check(n['now_ns']==ns and proof['observed_ns']==str(ns),'native original clock')
            check(all(r[k]==b[k] for k in ('run','session','actor','application','model_id','model_sha256','effort_profile')),'binding')
            check(r['clock_domain']=='m7-native-simulation-elapsed' and r['source_identity']=='native-eight-role-CAN-P05-Actual; authenticated-local-owner','receipt provenance')
            check(int(r['frame'])==last_frame+1 and r['simulation_begin_seconds']==last_end and
                  abs(r['simulation_end_seconds']-last_end-.01)<1e-6,'output continuity')
            check(int(r['logical_begin_ns'])==ns and int(r['logical_end_ns'])==ns+10000000,'original interval')
            submitted=copy.deepcopy(proof)
            for k in ('service_mask','credit_mask','release_mask'):submitted[k]=str(n[k])
            check(r['original_actual']['native']==submitted,'original proof preserved')
            check(r['inputs_cleared_after_physics'] and r['interval_work_valid']==work_mode and r['solver_substep_work_observed']==work_mode,'completion/work')
            check(r['physics_generation']==row['physics']['generation']==b['physics']['generation']==r['physics']['generation'],'generation')
            check(r['physics']['vehicle_substeps_low']==r['physics']['vehicle_substeps_high']==320,'profile')
            for key in ('sensor_wheel','returned_wheel'):
                w=n[key]
                if w:
                    error=abs(w['rad_s']-history[w['source_ns']]);max_quant=max(max_quant,error)
                    check(error <= (0 if key=='sensor_wheel' else .005+1e-12),'wheel value/source')
            if out['empty_init']:
                check(all(v is None for v in proof['actual']) and not proof['normal'] and ns-initial<80000000,'empty INIT')
                values=[0,0,0];empty+=1
            else:
                protecting=int(proof.get('protection_since_ns',0))!=0
                check(n['release_mask']==n['service_mask']==255,'eight-role masks')
                if release_packets is not None:check(proof['release']==release_packets,'immutable released session')
                release_packets=proof['release']
                if protecting:
                    since=int(proof['protection_since_ns'])
                    check(normal>0 and not proof['normal'] and n['credit_mask']==0 and proof['protection_selected_mask']==255,
                          'terminal local protection authority')
                    check(int(proof['enable_ns'])<=since<=ns and (not protection_since or protection_since==since),'protection identity')
                    protection_since=since;protection_count+=1
                else:check(not protection_since and n['credit_mask']==255 and not proof.get('protection_selected_mask',0),'normal authority cannot reopen')
                check(out.get('protection',False)==protecting,'applied protection mode')
                plan=None
                for role,packet in enumerate(proof['release']):
                    q=wire(packet,role,7,1);rr,phase=q.get('II');pp=q.get('IQQQQ');ack,accepted=q.get('QB')
                    check((rr,phase,accepted)==(role,2,1) and pp[0]==42 and pp[1]==initial+8000000 and
                          pp[2]==pp[1]+2000000000 and pp[3]==int(proof['enable_ns']) and pp[4]==pp[3]+20000000 and
                          pp[3]<=ack<=ns and ack<pp[4] and pp[4]<=pp[2],'Release ACK')
                    check(plan is None or plan==pp,'same plan');plan=pp
                credit=None
                for role,packet in enumerate(proof['credit'] if not protecting else []):
                    q=wire(packet,7,role,2);pp=q.get('IQQQQ');cc=q.get('IQQ')
                    check(pp==plan and cc[1]<=ns and cc[2]==cc[1]+60000000 and cc[2]>ns+10000000,'run credit')
                    check(credit is None or credit==cc,'same credit');credit=cc
                values=[];sources=[];actuals=[]
                for role,packet in enumerate(proof['actual']):
                    q=wire(packet,0 if role<2 else 1,7,9);act=frame(q,role,True)
                    check(act['epoch']==42 and int(proof['enable_ns'])<=act['source']<=ns and ns+10000000-act['source']<=30000000,'Actual whole interval')
                    prev=cursors.get(role)
                    if prev and act['seq']!=prev['seq']:
                        check(act['seq']>prev['seq'] and act['source']>=prev['source'] and 0<(act['counter']-prev['counter'])%256<=10,'Actual cursor')
                    cursors[role]=act;sources.append(act['source']);values.append(act['value']);actuals.append(act)
                    max_age=max(max_age,ns+10000000-act['source'])
                check(max(sources)-min(sources)<=10000000,'Actual skew')
                drive=actuals[2];check(drive['wheel_source'] in history and ns+10000000-drive['wheel_source']<=30000000 and abs(drive['wheel']-history[drive['wheel_source']])<=.005+1e-12,'CAN wheel source/age')
                max_age=max(max_age,ns+10000000-drive['wheel_source'])
                if proof['normal']:
                    normal+=1
                    q=wire(proof['permission'],1,4,5)
                    epoch,token,sent,deadline,op=q.get('IQQQI')
                    check(epoch==42 and op==0 and q.get('B')==3 and q.get('IBBB')==(0x194,1,0,64),'permission envelope')
                    payload=q.take(64)
                    check(binascii.crc_hqx(payload[:29]+payload[31:]+struct.pack('<H',0x1204),0xffff)==int.from_bytes(payload[29:31],'little'),'permission P05')
                    check(payload[:4]==b'\x01\x00\x01\x01' and payload[24] in (1,2) and payload[25]==1,'AllowNormal')
                    pe,ps,pc=struct.unpack_from('<IQI',payload,8)
                    power_source,oldest,expiry=struct.unpack_from('<QQQ',payload,36)
                    check(q.get('B')==0 and q.get('B')==1,'permission parent present')
                    epoch,seq,source,parent_expiry=q.get('IIQQ')
                    check(pe==epoch==42 and pc==seq and source<=ps<=ns and oldest<=power_source<=ps and
                          ns+10000000-ps<=50000000 and ns+10000000-source<=50000000 and
                          ns+10000000-oldest<=70000000 and ns+10000000<min(expiry,parent_expiry),'permission whole interval')
                    for role,packet in enumerate(proof['commands']):
                        q=wire(packet,0 if role<2 else 1,role+2,5)
                        epoch,token,sent,deadline,op=q.get('IQQQI');command=frame(q,role,False)
                        check(epoch==42 and op==0 and q.get('B')==1,'command context')
                        parent_epoch,parent_seq,parent_source,parent_expiry,accel,curvature,braking,hold=q.get('IIQQdddB')
                        oldest,expiry=q.get('QQ');act=actuals[role]
                        check(act['state'] in (1,2) and act['origin']==1 and act['causal']==command['seq'] and command['causal']==parent_seq,'causal native NormalPath')
                        check(parent_epoch==42 and command['epoch']==42 and oldest<=parent_source<=command['source']<=act['source'] and
                              ns+10000000-parent_source<=30000000 and ns+10000000-command['source']<=30000000 and ns+10000000-oldest<=70000000 and
                              ns+10000000<expiry<=min(parent_expiry,command['source']+30000001,parent_source+30000001,oldest+70000001),'command whole interval')
                        min_margin=min(min_margin,expiry-(ns+10000000))
                elif protecting:
                    check(all(x['state']==3 and x['origin']==2 and x['source']>=protection_since for x in actuals),'original LocalProtection Actual')
                    check(int(out['exclusive_expiry_ns'])==min(*sources,drive['wheel_source'])+30000001,'protection original freshness limit')
                else:check(all(x['state']==0 and x['origin']==0 for x in actuals) and values[2]==0,'bootstrap actual state')
            angle,pressure,torque=values
            check(all(abs(out[k]-v)<1e-12 for k,v in zip(('angle_rad','pressure_pa','torque_nm'),values)),'decoded Actual applied')
            t=math.tan(angle);steer=[-math.atan2(L*t,L-half*t),-math.atan2(L*t,L+half*t),0,0]
            for i,w in enumerate(r['physics']['wheels']):
                check(abs(w['set_drive_nm']-(torque*.5 if i>=2 else 0))<=1e-5 and abs(w['set_friction_nm']-pressure*.00025)<=1e-5 and
                      abs(w['set_steer_right_rad']-steer[i])<=1e-7,'wheel setter mapping')
                check(w['solver_omega_source']=='PhysX3.4.mWheelSpeeds.direct.v1' and math.isfinite(w['solver_omega_rad_s']),'post solver identity')
                if i>=2:check(w['solver_omega_rad_s']>=0,'raw rear negative')
            speed.append(r['physics']['body_forward_velocity_m_s']);torques.append(torque)
            count+=1;last_frame=int(r['frame']);last_end=r['simulation_end_seconds']
    check(count==report['receipts'] and normal==report['normal_intervals'] and empty==report['empty_init_intervals'],'reported counts')
    return dict(status='PASS_INDEPENDENT_FUNCTIONAL_AUDIT',receipts=count,normal_intervals=normal,empty_init_intervals=empty,
                max_whole_interval_source_age_ns=max_age,min_command_expiry_margin_ns=min_margin,max_wheel_quantization_error_rad_s=max_quant,
                torque_nm_range=[min(torques),max(torques)],final_forward_velocity_m_s=speed[-1],interval_work_valid=work_mode,
                protection_intervals=protection_count)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--model',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();model=json.loads(a.model.read_text());result=audit(a.directory,model)
    faults=[lambda r:r['receipt'].__setitem__('frame','0'),lambda r:r['native']['native_export']['actual'].__setitem__(2,None),
            lambda r:r['receipt']['physics']['wheels'][2].__setitem__('solver_omega_rad_s',-1e-12),
            lambda r:r['receipt']['physics']['wheels'][2].__setitem__('set_drive_nm',900),
            lambda r:r['receipt'].__setitem__('interval_work_valid',True),
            lambda r:r['receipt']['original_actual']['admitted_actual'].__setitem__('torque_nm',999)]
    rejected=0
    for fault in faults:
        try:audit(a.directory,model,fault)
        except (ValueError,KeyError):rejected+=1
        else:raise AssertionError('corruption escaped oracle')
    result['oracle_corruptions_rejected']=rejected
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':main()

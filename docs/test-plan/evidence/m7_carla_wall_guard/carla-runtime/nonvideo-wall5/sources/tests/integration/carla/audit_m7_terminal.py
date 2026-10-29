#!/usr/bin/env python3
"""Independent terminal native wire/clock/ledger audit; no CARLA clock acceptance."""
import argparse
import binascii
import copy
import csv
import gzip
import json
from pathlib import Path
import struct
from audit_m7_1q_native import check,wire


def decode(packet,role):
    r=wire(packet,0 if role<2 else 1,7,9)
    check(r.get('B')==role,'Actual role')
    can,fd,flags,length=r.get('IBBB');size=64 if role==2 else 32
    check(can==0x280+role and fd==1 and flags&~4==0 and length==size,'Actual CAN envelope')
    p=r.take(size);check(r.pos==len(r.data),'no trailing wire bytes')
    crc=binascii.crc_hqx(p[:29]+p[31:]+struct.pack('<H',0x1002+role*0x100),0xffff)
    check(crc==int.from_bytes(p[29:31],'little'),'Actual P05')
    check(p[2:4]==b'\x02\x01' and p[26:29]==b'\0'*3,'Actual schema')
    seq,epoch,source,causal=struct.unpack_from('<IIQI',p,4)
    result=dict(seq=seq,epoch=epoch,source=source,causal=causal,state=p[24],origin=p[25],
                value=int.from_bytes(p[:2],'little',signed=role!=1)*(.0001,1000,.1)[role])
    if role==2:
        check(p[34] in (0,1),'Drive wheel validity')
        result['wheel_valid']=p[34]==1
        result['wheel_source']=int.from_bytes(p[40:48],'little')
        result['wheel']=int.from_bytes(p[32:34],'little')*.01 if p[34] else None
    return result


def validate(samples,barrier,arm,stop,rows):
    check(len(samples)>=20,'real terminal response samples')
    first,last=samples[0],samples[-1];anchor=first['wall_anchor_ns'];base=barrier['now_ns']
    check(arm['period_ns']==2000000 and arm['deadline_ns']==4000000,'unchanged deadlines')
    check(stop['next_frame'] is None and not stop['normal'] and stop['credit_mask']==0 and
          stop['selected_mask']==255 and stop['logical_barrier_ns']==base,'terminal stop authority')
    check(not stop['actual_exported'] and not stop['physical_braking_accepted'],'no CARLA actuation claim')
    source_before=[decode(p,i)['source'] for i,p in enumerate(barrier['native_export']['actual'])]
    expected_energy=(barrier['settlement']['end_ns'],barrier['settlement']['total_mechanical_j'],barrier['settlement']['soc'])
    previous=None;cursors={};unique=[set(),set(),set()];first_floor=None;wheel_invalid=False
    for sample in samples:
        check(sample['clock']=='LOCAL_TERMINAL_RESPONSE_NOT_CARLA','distinct clock scope')
        check(sample['wall_anchor_ns']==anchor and sample['barrier_ns']==base and
              sample['local_ns']==base+sample['wall_ns']-anchor,'local elapsed clock; no wall/sim equality')
        check(anchor<sample['wall_ns'] and (previous is None or previous['wall_ns']<sample['wall_ns']),'monotonic service')
        check(sample['next_frame'] is None and not sample['normal'] and sample['credit_mask']==0 and
              sample['service_mask']==sample['selected_mask']==255 and sample['selection_ns']==base,'no rearm/permit')
        check(sample['controller_releases']==first['controller_releases'],'no new normal Controller requests')
        check((sample['energy_end_ns'],sample['mechanical_j'],sample['soc'])==expected_energy,'frozen original EV ledger')
        check(sample['wheel_source_ns']==first['wheel_source_ns']<=base,'original wheel source held')
        values=[]
        for role,packet in enumerate(sample['actual']):
            actual=decode(packet,role);values.append(actual)
            check(actual['epoch']==42 and actual['source']<=sample['local_ns'],'original Actual epoch/source')
            old=cursors.get(role)
            if old:
                check(actual['seq']>=old[0]['seq'] and actual['source']>=old[0]['source'],'Actual monotonic identity')
                if actual['seq']==old[0]['seq']:check(packet==old[1],'immutable cached Actual')
            cursors[role]=(actual,packet)
            if actual['source']>=base:
                check(actual['state']==3 and actual['origin']==2,'original FailSafe/LocalProtection Actual')
                unique[role].add(actual['source'])
            if sample['wall_ns']-anchor>=25000000:
                check(actual['source']>source_before[role] and actual['state']==3 and actual['origin']==2,'fresh protection delivery')
                check(sample['local_ns']-actual['source']<=30000000,'original Actual freshness')
            if role==2:
                if actual['wheel_valid']:
                    check(actual['wheel_source']<=base,'no wheel restamp')
                else:wheel_invalid=True
        if values[1]['value']>=1000000 and values[2]['value']==0 and first_floor is None:
            first_floor=sample['wall_ns']-anchor
        previous=sample
    check(last['wall_ns']-anchor>=290000000 and all(len(x)>20 for x in unique),'sustained actual delivery')
    check(first_floor is not None and wheel_invalid,'protective model response despite missing wheel')
    check(decode(last['actual'][1],1)['value']>=1000000 and decode(last['actual'][2],2)['value']==0,'terminal brake floor/zero torque')
    faults={};completed=[0]*10;missed=[0]*10;late=[0]*10;seen=set()
    for row in rows:
        owner,slot=row['owner'],row['slot']
        check(0<=owner<10 and slot>=0 and (owner,slot) not in seen,'wall job identity');seen.add((owner,slot))
        check(row['release_ns']==arm['first_release_ns']+slot*2000000 and row['deadline_ns']==row['release_ns']+4000000,'original wall grid')
        if row['start_ns']:
            check(row['start_ns']>=row['release_ns'] and row['end_ns']>=row['start_ns'],'real execution timestamps')
            if owner<9:check(row['start_ns']>=anchor,'no owner heartbeat while waiting for fault')
            if anchor<=row['start_ns']<=last['wall_ns']:completed[owner]+=1
        if row['detected_ns'] and row['deadline_ns']<=anchor and owner<9:faults[owner]=row['detected_ns']
        if anchor<=row['release_ns'] and row['deadline_ns']<=last['wall_ns']:
            if not row['end_ns']:missed[owner]+=1
            elif row['end_ns']>row['deadline_ns']:late[owner]+=1
    check(set(faults)==set(range(9)) and all(x>0 for x in completed),'independent fault then real owner/monitor execution')
    return dict(status='PASS_NATIVE_TERMINAL_RESPONSE_ONLY',samples=len(samples),unique_actual_sources=list(map(len,unique)),
                response_span_ns=last['wall_ns']-anchor,first_zero_torque_brake_floor_ns=first_floor,
                completed_jobs=completed,missed_jobs=missed,late_jobs=late,
                detection_to_selection_ns=stop['wall_selected_ns']-min(faults.values()),
                wall_runtime_accepted=False,clock_mapping_accepted=False,carla_physical_braking_accepted=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();d=a.directory
    def opening(path):
        return path.open('rt') if path.exists() else gzip.open(str(path)+'.gz','rt')
    with opening(d/'terminal.jsonl') as f:samples=[json.loads(line) for line in f]
    with opening(d/'native-wall.csv') as f:rows=[{k:int(v) for k,v in row.items()} for row in csv.DictReader(f)]
    if (d/'barrier.json').exists():
        barrier=json.loads((d/'barrier.json').read_text());result=json.loads((d/'result.json').read_text())
        arm,stop=result['arm'],result['stop'];carla=False
    else:
        path=d/'trace.jsonl';opener=open
        if not path.exists():path=path.with_suffix('.jsonl.gz');opener=gzip.open
        with opener(path,'rt') as f:trace=[json.loads(line) for line in f]
        check(len(trace)==200 and all('receipt' in r for r in trace[:-1]) and 'receipt' not in trace[-1],'199 CARLA intervals then blocked')
        check(all(r['settlement_ack']['ok'] for r in trace[1:]),'199 work settlements')
        terminal=trace[-1];barrier=terminal['native'];arm=terminal['wall_guard_arm'];stop=terminal['wall_guard_stop'];carla=True
        check(stop['wall_selected_ns']<=terminal['wall_stop_received_ns']<=terminal['wall_containment_ns'],'containment order')
        check(not any('protection_request' in r for r in trace),'no injected PROTECT')
    report=validate(samples,barrier,arm,stop,rows);report['carla_executed']=carla
    negatives=[]
    for name in ('restamp-wheel','invent-energy','resume-normal','cached-actual','bad-wire','missing-owner','relax-deadline','change-clock'):
        changed=copy.deepcopy(samples);jobs=copy.deepcopy(rows)
        if name=='restamp-wheel':changed[-1]['wheel_source_ns']+=1
        elif name=='invent-energy':changed[-1]['energy_end_ns']+=1
        elif name=='resume-normal':changed[-1]['normal']=True
        elif name=='cached-actual':changed[-1]['actual']=changed[0]['actual']
        elif name=='bad-wire':changed[-1]['actual'][1]='00'+changed[-1]['actual'][1][2:]
        elif name=='missing-owner':jobs=[r for r in jobs if r['owner']!=3]
        elif name=='relax-deadline':jobs[0]['deadline_ns']+=1
        else:changed[-1]['local_ns']+=1
        try:validate(changed,barrier,arm,stop,jobs)
        except (ValueError,AssertionError):negatives.append(name)
        else:raise AssertionError('oracle accepted '+name)
    report['rejected_corruptions']=negatives
    a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

if __name__=='__main__':main()

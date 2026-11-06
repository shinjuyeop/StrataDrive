#!/usr/bin/env python3
"""Actual three-ECU terminal service, physical sources and independent journal audit."""
import argparse
import copy
import json
from pathlib import Path
import struct
import zlib
from audit_control_diagnostics import csv_rows, event, require
from audit_central_restart import load as load_restart, judge as judge_restart
from audit_continuity_review import transaction
from audit_native_adoption import prefix
from audit_native_epochs import load as load_epochs, judge as judge_epochs
from audit_epoch_delivery import family
from audit_native_routing import SOURCES, DOMAIN


def load(root):
    epochs = json.loads((root.parent/'plan.json').read_text()).get('diagnostic_epochs', False)
    if epochs:
        raw = load_epochs(root)
        d = dict(raw, epoch_data=raw, streams={sid:dict(s, source=dict(rows=s['source']), replica=dict(rows=s['replica'])) for sid,s in raw['streams'].items()})
        entries, info = family(root/'native-diagnostics/central/service-case', service=True)
        store = dict(info, registry=4, rows=entries)
    else:
        d = load_restart(root);store = prefix(root/'native-diagnostics/central/service-case')
    d.update(case=store,
        ready=json.loads((root/'service-ready.json').read_text()), client=json.loads((root/'service-client.json').read_text()),
        service=json.loads((root/'service-result.json').read_text()), samples=csv_rows(root/'service-samples.csv'), requests=csv_rows(root/'service-requests.csv'), placement=json.loads((root/'service-writer.json').read_text()))
    d['freeze']={r:csv_rows(root/'native-diagnostics'/r/(r+('-2' if r=='central' else '-1')+'.freeze.csv')) for r in ('central','front','rear')}
    d['owners']={r:csv_rows(root/(('central-2-service' if r=='central' else r+'-1')+'.events.csv')) for r in ('central','front','rear')}
    d['physical_acquisitions']=csv_rows(root/'service-physical.csv');d['service_records']=csv_rows(root/'service-records.csv');d['transactions']=[transaction(r) for r in d['case']['rows'][d['service']['base']:]];return d


def physical_evidence(e, enable, after):
    now=e['now'];require(e['valid'] and e['inhibited'] and now['domain']==2 and now['instance']==DOMAIN and now['present'] and now['trusted'] and e['enable']==enable, 'trusted current inhibited service clock')
    require(0<=e['wheel_rad_s']<=.01 and abs(e['torque_nm'])<=.1 and 100000<=e['pressure_pa']<=1500000, 'original stationary bounds')
    times=[]
    for key in ('wheel','drive','brake'):
        s=e[key];require(s['present'] and s['trusted'] and s['domain']==2 and s['instance']==DOMAIN and max(enable['ns'],after)<=s['ns']<=now['ns'] and now['ns']-s['ns']<=30000000, 'fresh original physical acquisition after all journal writers stopped');times.append(s['ns'])
    require(max(times)-min(times)<=20000000,'original source skew')


def actuals(messages):
    result=set()
    for m in messages:
        raw=m['payload']
        if m['method']!=0x70 or len(raw)<69 or raw[:8]!=b'SDRV\x01\0\0\0' or raw[24]!=9 or raw[25] not in (1,2):continue
        crc=0xffffffff
        for byte in raw[:-4]:
            crc^=byte
            for _ in range(8):crc=(crc>>1)^(0x82f63b78 if crc&1 else 0)
        require(crc^0xffffffff==int.from_bytes(raw[-4:],'little'),'original control CRC32C')
        sender,receiver,domain=struct.unpack_from('<IIQ',raw,8);tag=raw[25];can_id,fd,flags,length=struct.unpack_from('<IBBB',raw,26);payload=raw[33:-4]
        require(receiver==7 and domain==DOMAIN and fd==1 and flags==0 and ((tag,can_id,length,len(payload),sender) in ((1,0x281,32,32,0),(2,0x282,64,64,1))), 'actual validated endpoint and CAN envelope')
        crc=0xffff
        for byte in payload[:29]+payload[31:]+struct.pack('<H',0x1102 if tag==1 else 0x1202):
            crc^=byte<<8
            for _ in range(8):crc=((crc<<1)^(0x1021 if crc&0x8000 else 0))&0xffff
        require(crc==int.from_bytes(payload[29:31],'little'),'actual independent CAN P05 CRC')
        if payload[3]!=1:continue
        epoch=struct.unpack_from('<I',payload,8)[0];source=struct.unpack_from('<Q',payload,12)[0]
        if tag==1:result.add(('brake',epoch,source,int.from_bytes(payload[:2],'little')*1000))
        else:
            result.add(('drive',epoch,source,struct.unpack_from('<h',payload)[0]*.1))
            if payload[34]==1:result.add(('wheel',epoch,struct.unpack_from('<Q',payload,40)[0],int.from_bytes(payload[32:34],'little')*.01))
    return result


def judge(d):
    report=judge_epochs(d["epoch_data"]) if "epoch_data" in d else judge_restart(d,True);require(d['placement']['allowed_cpus']==[(d['plan'].get('auxiliary_placement') or {}).get('cpu',15)] and d['placement']['policy']==d['placement']['priority']==0,'actual non-RT service writer placement');require(d['plan']['diagnostic_service'] and d['plan']['simple_vehicle'] and d['result']['vehicle']['pass'] and d['result']['service']['pass_'] and d['service']['pass'], 'actual service and moving SimpleVehicle profile')
    require(d['result']['vehicle']['max_speed_mps']>.01 and d['result']['vehicle']['distance_m']>.001 and d['result']['vehicle']['final_speed_mps']==0, 'real model motion and final physical standstill')
    all_rows=[]
    for role,mask in [('central',128),('front',13),('rear',114)]:
        stopped=[r for r in d['owners'][role] if r['event']=='service-capture-stop'];require(len(stopped)==1 and int(stopped[0]['epoch'])==3 and int(stopped[0]['value'])==mask,'real owner normal-gate closure before capture stop')
        rows=d['freeze'][role];require(len(rows)==(2 if role=='central' else 4 if role=='front' else 5),'whole ECU producer coverage')
        for r in rows:
            require(int(r['ns'])>=int(stopped[0]['ns']) and int(r['epoch'])==3 and int(r['committed'])==int(r['acknowledged'])>0 and not any(int(r[k]) for k in ('pending','dropped','first_lost','identity_error')), 'actual drained ACK and loss-free current recording cut')
        all_rows.extend(rows)
    after=max(int(r['ns']) for r in all_rows);require(max(int(r['ns']) for role in ('front','rear') for r in d['freeze'][role])<=min(int(r['ns']) for r in d['freeze']['central']), 'source drains precede collector freeze')
    store=d['case'];base=d['service']['base'];require(store['registry']==4 and store['stream']==8900 and len(store['rows'])==base+4 and store['rows'][:base]==d['merged'], 'separate service journal imports immutable original merged prefix')
    proof,review,passed,clear=d['transactions'];incident=(8001,(1<<32)|8,1);p=proof['event'];q=passed['event']
    original=next(event(raw) for raw in d['merged'] if event(raw)['_id']==incident);require(original['_unknown'] and original['_unmapped'] and original['kind']==1,'historical unknown facts unchanged')
    require(p['_id']==(8001,64,9) and p['kind']==0 and p['_proof']==8 and proof['related']==incident and p['_occurrence']==original['_occurrence'] and p['_unknown'] and not p['_unmapped'],'new service recording proof')
    require(review['tag']==2 and review['id']==(8001,64,10) and review['incident']==incident and review['proof']==p['_id'] and review['session']==(8001,3) and review['disposition']==1 and review['revision']==d['ready']['revision'],'explicit exact-scope unknown-history disposition')
    enable=p['_enable'];physical_evidence(review['evidence'],enable,after)
    require(len(review['streams'])==9,'whole nine-source manifest review')
    frozen={int(r['stream']):r for role in ('front','rear') for r in d['freeze'][role]}
    for i,cut in enumerate(review['streams']):
        sid=8200+i;source=d['streams'][sid]['source']['rows'];r=frozen[sid]
        require((cut['stream'],cut['producer'],cut['committed'],cut['tip'],cut['crc'])==(sid,SOURCES[i][0],len(source),event(source[-1])['_id'],zlib.crc32(source[-1])) and int(r['producer'])==SOURCES[i][0] and int(r['committed'])==len(source),'exact actual source cut/producer/tip/CRC')
    require(q['_id']==(8001,64,11) and q['kind']==5 and q['_proof_event']==p['_id'] and passed['related']==review['id'] and q['source_ns']==p['source_ns'] and q['observed_ns']>=review['evidence']['now']['ns'],'separate Passed preserves original proof acquisition')
    require(clear['tag']==1 and clear['id']==(8001,64,16) and clear['session']==(8001,3) and not clear['all'] and clear['targets']==[dict(key=(0x5001,3,10,8),revision=base+3)],'second explicit clear at exact Passed revision')
    physical_evidence(clear['evidence'],enable,after)
    require(len(d['samples'])==5 and int(d['samples'][0]['now'])==p['source_ns'] and int(d['samples'][1]['now'])==review['evidence']['now']['ns'] and int(d['samples'][2]['now'])==q['observed_ns'] and int(d['samples'][4]['now'])==clear['evidence']['now']['ns'],'five real owner/service samples at commit boundaries')
    actual=actuals(d['messages']);physical={key:{int(r[key+'_source']):float(r[field]) for r in d['physical_acquisitions']} for key,field in [('wheel','wheel_rad_s'),('drive','torque_nm'),('brake','pressure_pa')]}
    for r in d['samples']:
        now=int(r['now']);require(after<=int(r['owner_capture'])<=now and r['valid']==r['inhibited']=='1','actual current owner snapshot and independent service clock')
        for key,field,tolerance in [('wheel','wheel_rad_s',.005),('drive','torque_nm',.05),('brake','pressure_pa',500)]:
            source=int(r[key]);value=float(r[field]);require(after<=source<=now and now-source<=30000000 and (key,3,source,value) in actual,'same original Actual values/times crossed actual control TCP')
            require(source in physical[key],'same original physical producer timestamp')
            pv=physical[key][source];require(abs(pv-value)<=tolerance and (key!='wheel' or pv==value==0),'source model value matches fixed CAN quantization')
    client=d['client'];rows=d['requests'];require(len(rows)==9 and d['ready']['authorized_pid']==client['pid'] and client['pid']!=client['unauthorized_pid'],'fixed authorized principal and real unauthorized child')
    statuses=[1,1,2,3,4,0,0,10,0]
    for i,(row,status) in enumerate(zip(rows,statuses)):
        raw=bytes.fromhex(row['response']);require(len(raw)==32 and raw[:4]==b'SDR\x01' and raw[28]==status,'actual service admission verdict sequence')
        require(int(row['peer_pid'])==(client['unauthorized_pid'] if i==0 else client['pid']) and int(row['peer_uid'])==d['ready']['uid'],'kernel credential audit')
    review_raw=bytes.fromhex(rows[5]['request']);clear_raw=bytes.fromhex(rows[8]['request']);require(len(review_raw)==len(clear_raw)==76 and review_raw[:4]==clear_raw[:4]==b'SDS\x01' and review_raw[72:74]==b'\x01\x01' and clear_raw[72:74]==b'\x02\0' and struct.unpack_from('<Q',review_raw,20)[0]==3 and struct.unpack_from('<Q',clear_raw,20)[0]==4,'explicit separate local Review and Clear operations')
    require(rows[5]['request']==rows[6]['request'] and rows[5]['response']==rows[6]['response'],'exact duplicate receipt and no extra durable entries')
    require(review['evidence']['now']['ns']<clear['evidence']['now']['ns'] and any(r['code']=='20481' and r['cleared']=='1' and r['count']==r['generation']=='1' for r in d['service_records']),'explicit single incident tombstone; history count preserved')
    report.update(service_transactions=4,physical_samples=5,source_cuts=9,admission_requests=9);return report


def mutations(data):
    names=('physical-source','physical-value','freeze-ack','freeze-pending','owner-gate','collector-order','peer','status','explicit-disposition','partial-scope','tip','passed','clear-revision','history','motion','freshness','model-value')
    for name in names:
        d=copy.deepcopy(data)
        if name=='physical-source':d['samples'][0]['wheel']=d['samples'][0]['now']
        elif name=='physical-value':d['samples'][0]['torque_nm']='.1'
        elif name=='freeze-ack':d['freeze']['front'][0]['acknowledged']='0'
        elif name=='freeze-pending':d['freeze']['rear'][0]['pending']='1'
        elif name=='owner-gate':next(r for r in d['owners']['front'] if r['event']=='service-capture-stop')['value']='0'
        elif name=='collector-order':d['freeze']['central'][0]['ns']='0'
        elif name=='peer':d['client']['unauthorized_pid']=d['client']['pid']
        elif name=='status':d['requests'][0]['response']=d['requests'][5]['response']
        elif name=='explicit-disposition':d['transactions'][1]['disposition']=0
        elif name=='partial-scope':d['transactions'][1]['streams'].pop()
        elif name=='tip':d['transactions'][1]['streams'][0]['crc']^=1
        elif name=='passed':d['transactions'][2]['related']=(8001,64,9)
        elif name=='clear-revision':d['transactions'][3]['targets'][0]['revision']+=1
        elif name=='history':d['case']['rows'][0]=b'changed'
        elif name=='model-value':
            for r in d['physical_acquisitions']:r['pressure_pa']='0'
        elif name=='motion':d['result']['vehicle']['max_speed_mps']=0
        elif name=='freshness':d['samples'][0]['now']=str(int(d['samples'][0]['now'])+30000001)
        try:judge(d)
        except (ValueError,KeyError,IndexError):continue
        raise ValueError('mutation accepted: '+name)
    return len(names)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--mutations',action='store_true');a=p.parse_args();d=load(a.directory);r=judge(d)
    if a.mutations:r['mutations_rejected']=mutations(d)
    print(json.dumps(r,sort_keys=True))

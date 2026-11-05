#!/usr/bin/env python3
"""Correlate original owner tokens, TCP bytes and bounded SDK timing records.

Latency statistics describe accepted requests, not a substitute for the service
auditor's complete scenario verdict. Cancelled/failed requests remain in raw logs.
"""
import argparse
import copy
import csv
import json
import struct
from pathlib import Path
from audit_control_diagnostics import require
from audit_native_routing import SOURCES, IPS, CLIENTS, DOMAIN
from audit_someip_diagnostics import pcap


def load(root):
    bindings={};clients={r:(c,c+1) if r=='central' else (c,) for r,c in CLIENTS.items()}
    for z,role in enumerate(('front','rear')):
        bindings[0x5e01+2*z,0x101]=clients['central'];bindings[0x5e00+2*z,0x102]=clients[role]
    for i,(_,role,_) in enumerate(SOURCES):
        bindings[0x5e11+2*i,0x101]=clients[role];bindings[0x5e10+2*i,0x102]=clients['central']
    for sid,sender in [(0x5344,'central'),(0x5345,'central'),(0x5348,'central'),(0x5349,'central'),
                       (0x5346,'front'),(0x5347,'front'),(0x534a,'rear'),(0x534b,'rear')]:
        for mid in (0x10,0x20,0x40,0x50,0x60,0x70,0x80):bindings[sid,mid]=clients[sender]
    messages,_=pcap(root/'traffic.pcap',(*range(30501,30509),31610,31611,31612),tuple(IPS.values()),bindings)
    return {'wire':[m for m in messages if m['method'] in (0x20,0x80)],
            'timing':{p.name:list(csv.DictReader(p.open())) for p in root.glob('*.sdk-api.csv')},
            'owners':{p.name:list(csv.DictReader(p.open())) for p in root.glob('*.transport.csv')}}


def crc32c_table():
    table=[]
    for value in range(256):
        for _ in range(8):value=(value>>1)^(0x82f63b78 if value&1 else 0)
        table.append(value)
    return tuple(table)


CRC32C=crc32c_table()


def crc32c(raw):
    crc=0xffffffff
    for byte in raw:crc=CRC32C[(crc^byte)&255]^(crc>>8)
    return crc^0xffffffff


def judge(data):
    packets={};requests={};results={};stages={}
    identified=all('owner_epoch' in row for rows in data['timing'].values() for row in rows)
    for message in data['wire']:
        raw=message['payload'];method=message['method']
        require(len(raw)>=58 and raw[:8]==b'SDRV\x01\0\0\0','canonical owner header')
        crc=int.from_bytes(raw[-4:],'little');require(crc32c(raw[:-4])==crc,'original owner CRC32C')
        sender,receiver,domain=struct.unpack_from('<IIQ',raw,8)
        require(domain==DOMAIN,'original Host clock domain')
        epoch,token=struct.unpack_from('<IQ',raw,25)
        key=(method,crc,epoch,token,sender,receiver) if identified else (method,crc)
        require(key not in packets or packets[key]==raw,'no ambiguous original packet correlation');packets[key]=raw
        if epoch not in (2,3):continue
        if method==0x20:
            require(raw[24]==3 and sender==7 and receiver in (0,1) and message['client']==0x1312,'new Central request identity')
            identity=(epoch,token,receiver);destination=requests
        else:
            require(raw[24]==4 and sender in (0,1) and receiver==7 and len(raw)==62,'Zone result identity')
            identity=(epoch,token,sender);destination=results
        require(identity not in destination or destination[identity]==key,'one original payload per token');destination[identity]=key
    for name,rows in data['timing'].items():
        for row in rows:
            if row['event'] not in ('tx-queued','send-begin','send-return','rx-enter','rx-queued') or int(row['method']) not in (32,128):continue
            key=(int(row['method']),int(row['crc']))
            if identified:key+=tuple(int(row[k]) for k in ('owner_epoch','owner_token','owner_sender','owner_receiver'))
            events=stages.setdefault(key,{})
            require(row['event'] not in events,'unambiguous original timing stage')
            events[row['event']]={**row,'file':name}
    accepted=[r for name,rows in data['owners'].items() if name.startswith('central-2') for r in rows if r['event']=='central-result-accepted']
    zone={(int(r['epoch']),int(r['token']),peer):r for name,rows in data['owners'].items()
          for peer in ([0] if name.startswith('front-') else [1] if name.startswith('rear-') else [])
          for r in rows if r['event']=='zone-received'}
    samples=[]
    for row in accepted:
        identity=tuple(int(row[k]) for k in ('epoch','token','peer'))
        require(identity in requests and identity in results and identity in zone,'accepted token has original request/result/Zone evidence')
        request_key,result_key=requests[identity],results[identity];request,result=packets[request_key],packets[result_key]
        sent,deadline=struct.unpack_from('<QQ',request,37);source=int.from_bytes(result[37:45],'little')
        require(sent==int(row['sent']) and deadline==int(row['deadline']) and source==int(row['source']) and
                request[53]==int(row['operation'])==int.from_bytes(result[45:49],'little') and result[49]==1,'original accepted authority and result')
        received=int(zone[identity]['ns']);accepted_ns=int(row['ns'])
        require(sent<=received<=source<=accepted_ns<deadline,'accepted request/result within original exclusive deadline')
        sample={'epoch':identity[0],'token':identity[1],'peer':identity[2],'roundtrip_ns':accepted_ns-sent,'margin_ns':deadline-accepted_ns}
        for label,key,owner_time in [('request',request_key,received),('result',result_key,accepted_ns)]:
            require(key in stages and len(stages[key])==5,'complete original SDK stage chain')
            events=stages[key];times={event:int(r['ns']) for event,r in events.items()}
            require(times['tx-queued']<=times['send-begin']<=times['send-return'] and
                    times['send-begin']<=times['rx-enter']<=times['rx-queued']<=owner_time,'original queue/SDK/callback/owner order')
            require(all(int(r['bytes'])==len(packets[key]) for r in events.values()),'unchanged packet length')
            if label=='request':require(sent<=times['tx-queued'],'no request before original acceptance')
            else:require(source<=times['tx-queued'],'no result before original source')
            sample[label+'_queue_ns']=times['send-begin']-times['tx-queued']
            sample[label+'_sdk_callback_ns']=times['rx-enter']-times['send-begin']
            sample[label+'_decode_ns']=times['rx-queued']-times['rx-enter']
            sample[label+'_owner_ns']=owner_time-times['rx-queued']
        samples.append(sample)
    require(samples,'accepted request coverage')
    metrics={}
    for field in samples[0]:
        if not field.endswith('_ns'):continue
        values=sorted(s[field] for s in samples)
        metrics[field]={'min':values[0],'p50':values[len(values)//2],'p99':values[int((len(values)-1)*.99)],'max':values[-1]}
    return {'accepted_requests':len(samples),'metrics':metrics,'worst':sorted(samples,key=lambda r:r['roundtrip_ns'],reverse=True)[:5]}


def mutations(data):
    changes=[lambda d:d['wire'][0].__setitem__('payload',d['wire'][0]['payload'][:-1]+bytes([d['wire'][0]['payload'][-1]^1])),
             lambda d:[r.__setitem__('deadline',str(int(r['deadline'])+1)) for name,rows in d['owners'].items() if name.startswith('central-2') for r in rows if r['event']=='central-result-accepted'],
             lambda d:[r.__setitem__('ns','0') for rows in d['timing'].values() for r in rows if r['event']=='rx-enter'],
             lambda d:[rows.__setitem__(slice(None),[r for r in rows if r['event']!='rx-queued']) for rows in d['timing'].values()]]
    if all('owner_epoch' in r for rows in data['timing'].values() for r in rows):
        changes.append(lambda d:[r.__setitem__('owner_token',str(int(r['owner_token'])+1)) for rows in d['timing'].values() for r in rows if r['event']=='rx-enter' and int(r['method']) in (32,128)])
    for change in changes:
        changed=copy.deepcopy(data);change(changed)
        try:judge(changed)
        except ValueError:continue
        raise ValueError('latency evidence mutation accepted')
    return len(changes)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--mutations',action='store_true');a=p.parse_args()
    data=load(a.directory);report=judge(data)
    if a.mutations:report['mutations_rejected']=mutations(data)
    print(json.dumps(report,indent=2))

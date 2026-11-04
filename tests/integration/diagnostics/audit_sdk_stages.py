#!/usr/bin/env python3
"""Offline kernel/TCP/SDK stage correlation; not a service acceptance oracle."""
import argparse
import csv
import hashlib
import json
import socket
import struct
from pathlib import Path
from audit_service_response import crc32c

FIELDS=('service','method','client','session','bytes','crc')
STAGES=('tcp-receive','tcp-message','app-message','handler-queued','handler-enter','handler-exit')
IPS={'10.88.0.1':'central','10.88.0.2':'front','10.88.0.3':'rear'}


def require(ok,why):
    if not ok:raise ValueError(why)


def csv_rows(path):
    with path.open() as source:return list(csv.DictReader(source))


def clock_bounds(rows,strict=True):
    require(bool(rows),'clock samples missing')
    for r in rows:
        require(0<r['mono_before_ns']<=r['mono_after_ns'] and r['kernel_wall_ns']>0,'invalid clock bracket')
    # Conservative observed offset envelope over the entire capture, including
    # bracket width and observed drift. A hidden step between samples cannot be
    # ruled out; report this limitation instead of fabricating exact monotonic.
    low=min(r['wall_ns']-r['mono_after_ns'] for r in rows)
    high=max(r['wall_ns']-r['mono_before_ns'] for r in rows)
    if strict:require(high-low<=100000,'clock calibration uncertainty exceeds predeclared 100us observation bound')
    return low,high


def capture(root,strict_clock=True):
    meta=json.loads((root/'capture.json').read_text())
    require(meta['timestamp_source']=='SO_TIMESTAMPNS_NEW' and meta['normal_exit'] and meta['socket_drops']==0,'complete kernel capture')
    rows=[{k:int(v) for k,v in r.items()} for r in csv_rows(root/'packet-times.csv')]
    require(len(rows)==meta['rows'],'capture row count')
    low,high=clock_bounds(rows,strict_clock)
    data=(root/'traffic.pcap').read_bytes();require(data[:4]==b'\xd4\xc3\xb2\xa1','pcap format')
    position=24;streams={};active={};index=0
    while position<len(data):
        require(position+16<=len(data) and index<len(rows),'pcap record/sidecar coverage')
        sec,usec,n,original=struct.unpack_from('<IIII',data,position);position+=16
        require(n==original and position+n<=len(data),'uncut packet')
        packet=data[position:position+n];position+=n;r=rows[index];index+=1
        require(r['frame']==index and r['bytes']==n and sec*10**9+usec*1000==r['kernel_wall_ns']//1000*1000,'unaltered packet timestamp/length')
        require(packet[12:14]==b'\x08\x00','IPv4 capture')
        ip=packet[14:];ihl=(ip[0]&15)*4
        if ip[9]!=6:continue
        require(ihl>=20 and len(ip)>=ihl+20 and not(int.from_bytes(ip[6:8],'big')&0x3fff),'unfragmented TCP')
        tcp=ip[ihl:];src,dst,seq=struct.unpack_from('!HHI',tcp)
        if not ({src,dst}&set(range(30501,30509))):continue
        pair=(socket.inet_ntoa(ip[12:16]),socket.inet_ntoa(ip[16:20]),src,dst)
        require(pair[0] in IPS and pair[1] in IPS and pair[0]!=pair[1],'known peers')
        if tcp[13]&2 and not tcp[13]&16:active[pair]=seq
        header=(tcp[12]>>4)*4;length=int.from_bytes(ip[2:4],'big')
        require(header>=20 and ihl+header<=length<=len(ip),'TCP sizes')
        payload=ip[ihl+header:length]
        if not payload:continue
        require(pair in active,'SYN before data')
        stream=streams.setdefault(pair+(active[pair],),{})
        for offset,value in enumerate(payload,seq+int(bool(tcp[13]&2))):
            if offset in stream:
                require(stream[offset][0]==value,'consistent retransmission')
                stream[offset]=(value,min(stream[offset][1],r['kernel_wall_ns']))
            else:stream[offset]=(value,r['kernel_wall_ns'])
    require(index==len(rows),'no unmatched sidecar rows')
    messages=[]
    for flow,values in streams.items():
        start,end=min(values),max(values)+1
        require(len(values)==end-start,'complete TCP stream')
        payload=bytes(values[i][0] for i in range(start,end));cursor=0;prefix=0
        while cursor<len(payload):
            require(cursor+16<=len(payload),'SOME/IP header')
            service,method,length,client,session,protocol,interface,kind,code=struct.unpack_from('!HHIHHBBBB',payload,cursor)
            stop=cursor+length+8
            require(8<=length<=2056 and stop<=len(payload),'SOME/IP complete message')
            require(protocol==interface==kind==1 and code==0 and session>0,'SOME/IP binding')
            require(30501<=flow[3]<=30508 and service==0x5344+flow[3]-30501,'service bound to TCP endpoint')
            require(client in {'10.88.0.1':(0x1311,0x1312),'10.88.0.2':(0x1422,),'10.88.0.3':(0x1522,)}[flow[0]],'sender client binding')
            raw=payload[cursor+16:stop];prefix=max(prefix,max(values[i][1] for i in range(start+cursor,start+stop)))
            cursor=stop
            if raw[:8]!=b'SDRV\x01\0\0\0':
                require(method==0x10,'canonical owner header');continue
            crc=int.from_bytes(raw[-4:],'little');require(crc32c(raw[:-4])==crc,'owner CRC32C')
            key=(service,method,client,session,len(raw),crc)
            messages.append({'key':key,'flow':flow,'sha256':hashlib.sha256(raw).hexdigest(),
                             'kernel_low_ns':prefix-high,'kernel_high_ns':prefix-low})
    return messages,{'rows':len(rows),'offset_low_ns':low,'offset_high_ns':high,'uncertainty_ns':high-low,'qualified':high-low<=100000}


def stage_chain(events):
    require(all(stage in events for stage in STAGES),'complete SDK receive stages')
    times=[events[s]['ns'] for s in STAGES]
    require(times==sorted(times),'SDK stage ordering')
    require(events['tcp-receive']['tid']==events['tcp-message']['tid'],'same TCP receive thread')
    require(events['app-message']['tid']==events['handler-queued']['tid'],'same application enqueue thread')
    require(events['handler-enter']['tid']==events['handler-exit']['tid'],'same callback thread')
    result={name:events[end]['ns']-events[begin]['ns'] for name,begin,end in (
        ('tcp_parse_ns','tcp-receive','tcp-message'),('routing_ns','tcp-message','app-message'),
        ('enqueue_ns','app-message','handler-queued'),('dispatch_wait_ns','handler-queued','handler-enter'),
        ('handler_ns','handler-enter','handler-exit'))}
    for label,begin,end in [('tcp','tcp-receive','tcp-message'),('enqueue','app-message','handler-queued'),
                          ('handler','handler-enter','handler-exit')]:
        for field in ('cpu_ns','voluntary','involuntary'):
            delta=events[end][field]-events[begin][field];require(delta>=0,'thread counter monotonicity')
            result[label+'_'+field]=delta
    return result


def analyze(root):
    runtime=json.loads((root/'result.json').read_text())
    require(runtime.get('sdk_observation',{}).get('complete'),'complete observation runtime')
    captures={};calibration={}
    for role,directory in [('central',root),('front',root/'capture-front'),('rear',root/'capture-rear')]:
        # Keep SDK's monotonic observations even when wall-clock calibration
        # fails. Do not emit kernel interval metrics for that receiver, and keep
        # the overall precision verdict/CLI failure unchanged.
        packets,calibration[role]=capture(directory,strict_clock=False);table={}
        for packet in packets:
            identity=packet['flow']+packet['key']
            require(identity not in table,'unambiguous TCP message identity');table[identity]=packet
        captures[role]=table
    internal={};all_events={};partial=[]
    for path in root.glob('*.sdk-internal.csv'):
        meta=json.loads(Path(str(path)+'.json').read_text());require(meta['complete'],'complete SDK trace '+path.name)
        rows=[{k:(v if k=='stage' else int(v)) for k,v in r.items()} for r in csv_rows(path)]
        require(len(rows)==meta['rows'],'SDK row count')
        all_events[path.name]=rows
        for row in rows:
            key=tuple(row[f] for f in FIELDS);events=internal.setdefault((path.name,key),{})
            require(row['stage'] not in events,'unambiguous SDK stage '+path.name)
            events[row['stage']]=row
    indexed={}
    for (name,key),events in internal.items():indexed.setdefault((key,name.split('-')[0]),[]).append((name,events))
    api={}
    for path in root.glob('*.sdk-api.csv'):
        for r in csv_rows(path):
            if r['event'] not in ('send-begin','send-return','rx-enter','rx-queued'):continue
            key=(path.name.replace('.sdk-api.csv','.sdk-internal.csv'),int(r['method']),int(r['bytes']),int(r['crc']))
            events=api.setdefault(key,{})
            events.setdefault(r['event'],[]).append(int(r['ns']))
    ambiguous=[{'file':key[0],'method':key[1],'bytes':key[2],'crc':key[3],
                'counts':{event:len(values) for event,values in events.items()}}
               for key,events in api.items() if any(len(values)!=1 for values in events.values())]
    samples=[]
    for identity,packet in captures['central'].items():
        flow,key=packet['flow'],packet['key'];sender,receiver=IPS[flow[0]],IPS[flow[1]]
        # The two full TCP streams must preserve every original byte.
        peer=receiver if sender=='central' else sender
        require(identity in captures[peer] and captures[peer][identity]['sha256']==packet['sha256'],'same original bytes at both endpoints')
        rx=captures[receiver][identity];tx=captures[sender][identity]
        matches=indexed.get((key,receiver),[])
        if not matches:
            partial.append({'key':key,'receiver':receiver,'reason':'receiver trace unavailable (including declared SIGKILL)' });continue
        require(len(matches)==1,'unique receiver process')
        name,events=matches[0]
        if not all(s in events for s in STAGES):
            require('handler-enter' not in events and 'handler-exit' not in events,'executed callback missing internal stages')
            partial.append({'key':key,'receiver':name,'stages':list(events)});continue
        metrics=stage_chain(events)
        if calibration[receiver]['qualified']:
            metrics.update(kernel_to_io_low_ns=events['tcp-receive']['ns']-rx['kernel_high_ns'],
                           kernel_to_io_high_ns=events['tcp-receive']['ns']-rx['kernel_low_ns'])
            require(metrics['kernel_to_io_high_ns']>=0,'kernel packet before SDK read')
        api_events={event:values[0] for event,values in api.get((name,key[1],key[4],key[5]),{}).items() if len(values)==1}
        if 'rx-enter' in api_events:
            require(events['handler-enter']['ns']<=api_events['rx-enter']<=events['handler-exit']['ns'],'adapter callback inside SDK handler')
        sample={'key':key,'sender':sender,'receiver':name,'at_ns':events['handler-enter']['ns'],
                'metrics':metrics,'stages':events,'kernel_receive':rx,'kernel_send_observation':tx}
        send_matches=[(n,e) for n,e in indexed.get((key,sender),[]) if 'tcp-send' in e]
        if len(send_matches)==1:
            sn,se=send_matches[0];sample['tcp_send']=se['tcp-send']
            calls={event:values[0] for event,values in api.get((sn,key[1],key[4],key[5]),{}).items() if len(values)==1}
            if 'send-begin' in calls:
                sample['send_call']=calls
                metrics['send_to_tcp_ns']=se['tcp-send']['ns']-calls['send-begin']
                metrics['send_to_handler_ns']=events['handler-enter']['ns']-calls['send-begin']
        samples.append(sample)
    require(bool(samples),'complete receive chain coverage')
    # Preserve context for long dispatch waits: other callbacks on that process,
    # with per-thread CPU/context counters, rather than labelling wall time CPU wait.
    for s in samples:
        if s['metrics']['dispatch_wait_ns']<1000000:continue
        before=s['stages']['handler-queued']['ns'];after=s['at_ns']
        s['overlapping_handler_events']=[r for r in all_events[s['receiver']]
            if r['stage'] in ('handler-enter','handler-exit') and before-2000000<=r['ns']<=after+100000]
    faults=sorted((dict(r,file=p.name) for p in root.glob('central-2*.events.csv') for r in csv_rows(p)
                   if r['event'] in ('central-fault','central-allocation-fault','session-failed')),key=lambda r:int(r['ns']))
    at=int(faults[0]['ns']) if faults else None
    windows=[]
    for path in sorted(root.glob('central-2*.events.csv')):
        rows=csv_rows(path)
        for arm in (r for r in rows if r['event']=='normal-armed'):
            begin=int(arm['ns'])
            ends=[int(r['ns']) for r in rows if r['event'] in ('normal-stop-complete','central-fault','session-failed') and int(r['ns'])>=begin]
            for peer_path in root.glob('*-1.events.csv'):
                ends += [int(r['ns']) for r in csv_rows(peer_path) if r['event']=='service-stop-ack-omitted' and int(r['ns'])>=begin]
            require(bool(ends),'normal armed window has terminal observation')
            windows.append({'epoch':int(arm['epoch']),'begin_ns':begin,'end_ns':min(ends)})
    normal=[s for s in samples if any(w['begin_ns']<=s['at_ns']<w['end_ns'] for w in windows)]
    fields=sorted({f for s in samples for f in s['metrics']})
    worst={f:sorted((s for s in samples if f in s['metrics']),key=lambda s:s['metrics'][f],reverse=True)[:3]
           for f in ('kernel_to_io_high_ns','dispatch_wait_ns','enqueue_ns','handler_ns','send_to_tcp_ns')}
    return {'service_runtime_pass':runtime['pass'],'observation_complete':all(c['qualified'] for c in calibration.values()),'calibration':calibration,
            'complete_receive_chains':len(samples),'partial_receive_chains':len(partial),'partial':partial,
            'ambiguous_adapter_keys':ambiguous,
            'normal_windows':windows,'normal_chains':len(normal),
            'normal_maxima':{f:max(s['metrics'][f] for s in normal if f in s['metrics']) for f in fields if any(f in s['metrics'] for s in normal)},
            'normal_worst':{f:sorted((s for s in normal if f in s['metrics']),key=lambda s:s['metrics'][f],reverse=True)[:3]
                for f in ('kernel_to_io_high_ns','tcp_parse_ns','routing_ns','enqueue_ns','dispatch_wait_ns','handler_ns','send_to_tcp_ns','send_to_handler_ns')},
            'maxima':{f:max(s['metrics'][f] for s in samples if f in s['metrics']) for f in fields},
            'first_faults':faults[:4],
            'near_first_fault':sorted((s for s in samples if at and at-25000000<=s['at_ns']<=at+1000000),
                key=lambda s:s['metrics'].get('send_to_handler_ns',s['metrics'].get('kernel_to_io_high_ns',0)+s['metrics']['dispatch_wait_ns']),reverse=True)[:10],
            'worst':worst}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);a=p.parse_args()
    report=analyze(a.directory);print(json.dumps(report,indent=2))
    raise SystemExit(int(not report['observation_complete']))

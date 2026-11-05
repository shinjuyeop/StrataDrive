#!/usr/bin/env python3
"""Audit declared native service faults without converting runtime FAIL to PASS."""
import argparse
import copy
import json
from pathlib import Path
from audit_control_diagnostics import csv_rows, event, require
from audit_native_adoption import prefix


def load(root):
    home = root/'native-diagnostics'
    def rows(path):
        return csv_rows(path) if path.exists() else []
    def document(path):
        return json.loads(path.read_text()) if path.exists() else None
    return dict(plan=document(root.parent/'plan.json'), result=document(root/'result.json'),
                service=document(root/'service-result.json'), client=document(root/'service-client.json'),
                ready=document(root/'service-ready.json'), samples=rows(root/'service-samples.csv'),
                requests=rows(root/'service-requests.csv'),
                transport=rows(root/'central-2-service.transport.csv'),
                owners={role: rows(root/(('central-2-service' if role=='central' else role+'-1')+'.events.csv'))
                        for role in ('central', 'front', 'rear')},
                drain=rows(home/'front/front-1.drain-failed.csv'),
                delivery=rows(home/'central/central-2.delivery.csv'),
                merged=prefix(home/'central/merged-2'), case=prefix(home/'central/service-case'),
                sources={role: rows(home/role/(role+'-1.freeze.csv')) for role in ('front', 'rear')})


def judge(d):
    fault=d['plan']['service_fault'];result=d['result'];events=[event(raw) for raw in d['merged']['rows']]
    require(fault in ('ack-loss','actual-loss','stop-request-loss','stop-ack-loss'), 'declared fault recipe')
    require(d['plan']['isolated_ecus'] and d['plan']['diagnostic_service'], 'declared isolated native service profile')
    require(not result['pass'] and not result['sanitizer_diagnostics'] and not result['sdk_errors'] and not result['forced_cleanup'], 'failed service, clean instrumented process shutdown')
    require(result.get('central_rejoined') and result['survivor_pids_before']==result['survivor_pids_after'], 'actual Central restart and surviving remote owners')
    sessions=[e for e in events if e['kind']==6]
    require([e['epoch'] for e in sessions]==[1,2,3] and all(e['received_roles']==255 for e in sessions), 'three actual global Release completions before fault')
    boot=d['owners']['central'];stops=[e for e in boot if e['event']=='normal-stop-requested' and e['epoch']=='3']
    require(len(stops)==1,'actual Epoch3 normal stop requested')
    require(not any(e['_id'][1]==64 for e in events),'service producer cannot change original merged history')
    if fault=='actual-loss':
        require(d['ready'] and d['service'] and not d['service']['pass'],'endpoint entered but review/clear failed')
        require(d['case']['rows']==d['merged']['rows'] and len(d['case']['rows'])==d['service']['base'], 'no service transaction committed')
        require(len(d['samples'])==1 and len(d['requests'])==2,'one failed acquisition and two explicit requests')
        sample=d['samples'][0];require(int(sample['now'])-int(sample['brake'])>30000000 and sample['valid']=='0', 'original Brake source expired at service clock')
        omitted=[e for e in d['owners']['front'] if e['event']=='service-actual-omitted' and e['epoch']=='3']
        require(omitted and int(omitted[0]['ns'])<=int(sample['now']), 'actual Front feedback emitter injection before request')
        require([r['reply']['status'] for r in d['client']['requests']]==[6,11] and all(r['reply']['stage']==0 for r in d['client']['requests']), 'stale review and unapproved clear rejected')
        for row,status in zip(d['requests'],(6,11)):
            packet=bytes.fromhex(row['response']);require(len(packet)==32 and packet[:4]==b'SDR\x01' and packet[28:30]==bytes([status,0]),'original socket refusal')
        require(sum(map(len,d['sources'].values()))==9 and all(int(r['committed'])==int(r['acknowledged'])>0 and r['pending']=='0' for rows in d['sources'].values() for r in rows),'all nine sources frozen before physical loss')
    else:
        require(not d['ready'] and not d['case']['rows'] and not d['requests'],'failed precondition cannot expose service or commit')
        if fault=='ack-loss':
            omitted=[r for r in d['delivery'] if r['action']=='service-omit-ack']
            require(omitted,'actual durable replica ACK omitted')
            cut=next((r for r in d['drain'] if r['stream']=='8200'),None)
            require(cut and int(cut['committed'])>int(cut['acknowledged']) and cut['dropped']==cut['identity_error']=='0','durable unacknowledged source at drain timeout')
            require(result.get('error')=='RuntimeError: source service drain failed front','failure detected from source drain report')
        else:
            # The actual first detector depends on release phase: allocation/
            # transport can expire first, or NormalStop can observe its root's
            # original50ms age at the management release. Prove that detector;
            # never relabel the record or accept an unrelated early fault.
            codes=(0x1002,0x1105) if fault=='stop-request-loss' else (0x1102,)
            roots=[e for e in events if e['kind']==1 and e['epoch']==3 and e['code'] in codes]
            require(1<=len(roots)<=(2 if fault=='stop-request-loss' else 1) and
                    all(e['detected_ns']>=int(stops[0]['ns']) for e in roots), 'original stop detector DTC')
            if len(roots)==2:
                require({(e['code'],e['component'],e['monitor']) for e in roots}==
                        {(0x1105,2,2),(0x1002,3,3)},'distinct Stop and transport detector records')
                stop_root=next(e for e in roots if e['code']==0x1105)
                transport_root=next(e for e in roots if e['code']==0x1002)
                require(transport_root['native_reason'] in (0x20005,0x20007) and
                        transport_root['detected_ns']<=stop_root['detected_ns'] and
                        transport_root['command_expiry_ns']==min(stop_root['command_expiry_ns'],stop_root['command_source_ns']+50000001) and
                        transport_root['_id'][:2]==stop_root['_id'][:2] and
                        transport_root['related_sequence']==stop_root['event_sequence'],
                        'original transport cause precedes and relates to the same Stop observation')
            for root in roots:
                require(not root['_unmapped'],'mapped original detector')
                if root['code']==0x1105:
                    require(fault=='stop-request-loss' and root['component']==2 and root['monitor']==2 and
                            root['native_reason']==3 and root['_before']==2 and root['_after']==6,'native NormalStop RequestLost identity/state')
                    starts=[e for e in events if e['epoch']==3 and e['component']==2 and e['kind']==0 and e['_after']==2]
                    issued=[r for r in boot if r['event']=='stop-root-issued' and r['epoch']=='3']
                    require(len(starts)==len(issued)==1 and root['_command']==starts[0]['_command'],'one original unrenewed stop root')
                    request=issued[0];source=int(request['value']);expiry=int(request['deadline'])
                    require(root['command_source_ns']==source and root['command_expiry_ns']==expiry==source+60000000 and
                            int(stops[0]['ns'])<=source<=int(request['ns'])<=root['detected_ns'] and
                            root['detected_ns']>=min(expiry,source+50000001),'original StopRequest source/expiry and age violation')
                    owner=[r for r in boot if r['event']=='central-fault' and r['epoch']=='3']
                    require(len(owner)==1 and owner[0]['value']=='6' and int(owner[0]['ns'])>=root['detected_ns'],'actual coordinator Stop propagation')
                elif root['native_reason'] in (0x20005,0x20007):
                    detector='central-result-timeout' if root['native_reason']==0x20007 else 'central-result-rejected'
                    matches=[r for r in d['transport'] if r['event']==detector and int(r['token'])==root['_command']['sequence'] and int(r['epoch'])==3]
                    require(len(matches)==1,'original pending transport timeout')
                    original=matches[0]
                    require(int(original['sent'])==root['command_source_ns'] and int(original['deadline'])==root['command_expiry_ns']<=int(original['ns'])<=root['detected_ns'],'original transport token and exclusive deadline')
                    if root['native_reason']==0x20005:
                        require(fault=='stop-request-loss','late result only qualifies expired original stop authority')
                        starts=[e for e in events if e['epoch']==3 and e['component']==2 and e['kind']==0 and e['_after']==2]
                        require(len(starts)==1 and root['command_expiry_ns']==min(starts[0]['command_expiry_ns'],starts[0]['command_source_ns']+50000001),'late result bound to original unrenewed stop request')
                    if fault=='stop-ack-loss':require(original['operation']=='5','timeout belongs to actual Stop operation')
                elif fault=='stop-request-loss':require(root['native_reason']==0x10004,'actual allocator RequestLost root')
            if fault=='stop-request-loss':
                stop_roots=[e for e in roots if e['code']==0x1105]
                owner=[r for r in boot if r['event']=='central-fault' and r['epoch']=='3']
                if any(r['value']=='6' for r in owner):
                    require(len(stop_roots)==1,'actual Coordinator Stop must retain its native Stop DTC')
                if stop_roots:
                    stop_root=stop_roots[0]
                    cut=min(stop_root['command_expiry_ns'],stop_root['command_source_ns']+50000001)
                    earlier=[r for r in d['transport'] if r['event'] in ('central-result-rejected','central-result-timeout') and
                             r['epoch']=='3' and int(r['deadline'])==cut and cut<=int(r['ns'])<=stop_root['detected_ns']]
                    if earlier:
                        first=min(earlier,key=lambda r:int(r['ns']))
                        require(any(e['code']==0x1002 and e['_command']['sequence']==int(first['token']) for e in roots),
                                'earlier original transport failure must not disappear from diagnostic history')
            name='service-stop-renewal-omitted' if fault=='stop-request-loss' else 'service-stop-ack-omitted'
            owner='central' if fault=='stop-request-loss' else 'front'
            require(any(r['event']==name and r['epoch']=='3' for r in d['owners'][owner]), 'actual declared stop lane injection')
            require(not any(r['event']=='normal-stop-complete' for r in boot), 'no fabricated stop completion')
    return dict(fault=fault, expected_rejection=True, runtime_pass=False, service_commits=0)


def mutations(data):
    changes=[('false-success',lambda d:d['result'].__setitem__('pass',True)),
             ('missing-session',lambda d:d['merged']['rows'].clear()),
             ('false-clear',lambda d:d['case']['rows'].append(b'false clear'))]
    fault=data['plan']['service_fault']
    if fault=='actual-loss':
        changes += [('freshness',lambda d:d['samples'][0].__setitem__('now',d['samples'][0]['brake'])),
                    ('emitter',lambda d:d['owners']['front'].clear())]
    elif fault=='ack-loss':
        changes += [('ack',lambda d:[r.__setitem__('acknowledged',r['committed']) for r in d['drain']]),
                    ('omission',lambda d:d['delivery'].clear())]
    else:
        changes += [('injection',lambda d:d['owners']['central' if fault=='stop-request-loss' else 'front'].clear())]
    if fault=='stop-request-loss' and any(event(b)['native_reason']==0x20005 for b in data['merged']['rows']):
        changes += [('original-deadline',lambda d:[r.__setitem__('deadline',str(int(r['deadline'])+1)) for r in d['transport']]),
                    ('before-expiry',lambda d:[r.__setitem__('ns',str(max(0,int(r['deadline'])-1))) for r in d['transport']])]
    if fault=='stop-request-loss' and any(event(b)['code']==0x1105 for b in data['merged']['rows']):
        changes += [('stop-source',lambda d:[r.__setitem__('value',str(int(r['value'])+1)) for r in d['owners']['central'] if r['event']=='stop-root-issued']),
                    ('stop-expiry',lambda d:[r.__setitem__('deadline',str(int(r['deadline'])+1)) for r in d['owners']['central'] if r['event']=='stop-root-issued']),
                    ('stop-repeated',lambda d:d['owners']['central'].extend(copy.deepcopy([r for r in d['owners']['central'] if r['event']=='stop-root-issued']))),
                    ('wrong-propagation',lambda d:[r.__setitem__('value','12') for r in d['owners']['central'] if r['event']=='central-fault'])]
    epoch_roots=[event(b) for b in data['merged']['rows'] if event(b)['epoch']==3 and event(b)['kind']==1]
    if fault=='stop-request-loss' and {0x1002,0x1105}.issubset({e['code'] for e in epoch_roots}):
        def remove_root(d,code):
            d['merged']['rows']=[b for b in d['merged']['rows'] if not
                                (event(b)['epoch']==3 and event(b)['kind']==1 and event(b)['code']==code)]
        changes += [('missing-stop-root',lambda d:remove_root(d,0x1105)),
                    ('missing-transport-root',lambda d:remove_root(d,0x1002)),
                    ('duplicate-stop-root',lambda d:d['merged']['rows'].append(next(b for b in d['merged']['rows'] if
                     event(b)['epoch']==3 and event(b)['kind']==1 and event(b)['code']==0x1105)))]
    for name,mutate in changes:
        changed=copy.deepcopy(data);mutate(changed)
        try:judge(changed)
        except (ValueError,KeyError,IndexError):continue
        raise ValueError('mutation accepted: '+name)
    return len(changes)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--mutations',action='store_true');a=p.parse_args()
    data=load(a.directory);report=judge(data)
    if a.mutations:report['mutations_rejected']=mutations(data)
    print(json.dumps(report,sort_keys=True))

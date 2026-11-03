#!/usr/bin/env python3
"""Independent BMS/Power vehicle-SIL journal, input copy and physical audit."""
import argparse
import copy
import json
import struct
from pathlib import Path
from audit_control_diagnostics import csv_rows, journal, require


def load(path):
    case=path.name
    require(case in ('bms-input-loss','power-input-loss'),'named fixture')
    prefix='logical-'+case
    return dict(case=case,registry=struct.unpack_from('<I',(path/'store/manifest').read_bytes(),32)[0],
                events=journal(path/'store'),records=csv_rows(path/'records.csv'),native=csv_rows(path/'native.csv'),
                samples=csv_rows(path/'native-samples.csv'),bodies=csv_rows(path/'native-bodies.csv'),
                physical=csv_rows(path/'physical.csv'),owners=csv_rows(path/(prefix+'-events.csv')),
                runtime=json.loads((path/(prefix+'.json')).read_text()))


def judge(d):
    bms=d['case']=='bms-input-loss'; owner=5 if bms else 6; actor=10 if bms else 6; producer=32 if bms else 33
    monitor=8 if bms else 9; code=0x3101 if bms else 0x3201; reason=1 if bms else 2
    rows=d['events']; physical=d['physical']; bodies=d['bodies']; log=d['owners']
    require(d['registry']==2 and d['runtime']['passed'] and d['runtime']['physical_ok'] and d['runtime']['model_preserved'],'registry/runtime/model')
    require(all(e['_run']==5001 and e['_id'][1] in (7,30,31,32,33) and not e['_unmapped'] and
                e['_enable']['domain']==1 and e['_enable']['instance']==5001 for e in rows),'clock/producer dictionary')
    for who in {e['_id'][1] for e in rows}:
        seq=[e['event_sequence'] for e in rows if e['_id'][1]==who]
        require(seq==list(range(1,len(seq)+1)),'producer sequence')
    faults=[e for e in rows if e['kind']==1]; passed=[e for e in rows if e['kind']==5]
    require(len(faults)==len(passed)==len(d['records'])==1,'single intrinsic occurrence')
    f=faults[0]; p=passed[0]; by_id={e['_id']:e for e in rows}; proof=by_id.get(p['_proof_event'])
    require((f['code'],f['component'],f['monitor'],f['native_reason'],f['epoch'],f['_id'][1])==(code,actor,monitor,reason,1,producer) and not f['_unknown'],'native primary reason')
    require(p['code']==code and p['component']==actor and p['monitor']==monitor and p['epoch']==2 and p['_id'][1]==producer and
            p['_occurrence']==f['_occurrence'] and p['related_sequence']==f['event_sequence'],'same original occurrence')
    require(proof and proof['kind']==0 and proof['epoch']==2 and proof['_id'][1]==producer and proof['_occurrence']==f['_occurrence'] and
            proof['_proof']==p['_proof']==(1 if bms else 2) and proof['event_sequence']<p['event_sequence'] and not proof['_times'][5]['present'],'qualified metadata proof')
    sessions=[e for e in rows if e['kind']==6]
    require([e['epoch'] for e in sessions]==[1,2] and all(e['_id'][1]==7 for e in sessions),'global session authority')
    require(p['source_ns']>sessions[1]['_enable']['ns'] and p['_latch']==2,'INIT alone is not proof')
    r=d['records'][0]
    require(tuple(int(r[k]) for k in ('code','component','monitor','subject'))==(code,actor,monitor,reason) and
            all(r[k]==v for k,v in [('condition','2'),('count','1'),('generation','1'),('cleared','0')]),'history retained')
    omissions=[r for r in log if r['kind']=='native-input-unavailable']; restorations=[r for r in log if r['kind']=='native-input-restored']
    require(len(omissions)==len(restorations)==1 and int(omissions[0]['owner'])==int(restorations[0]['owner'])==owner,'actual input-copy injection')
    first=int(omissions[0]['time_ns']); restored=int(restorations[0]['time_ns'])
    require(11_000_000_000<=first<=11_000_000_000+(20_000_000 if bms else 10_000_000) and f['detected_ns']==first and
            11_200_000_000<=restored<=11_200_000_000+(20_000_000 if bms else 10_000_000),'fixed omission/restoration clocks')
    require(not any(r['kind'] in ('fault-observed','leaf-protection-selected','zone-protection-ack','owner-stopped') and int(r['time_ns'])<first for r in log),'no earlier unrelated protection')
    require(any(e['kind']==2 and e['_occurrence']==f['_occurrence'] and e['_id'][1]==producer and e['selected_ns']==first for e in rows),'primary native selection')
    require(any(r['kind']=='leaf-protection-selected' and int(r['owner'])==owner and int(r['time_ns'])==first for r in log),'original source-selected log')
    for zone in (0,1):
        require(any(r['kind']=='zone-protection-ack' and int(r['owner'])==zone and first<=int(r['time_ns'])<=first+100_000_000 for r in log),'live Zone protection ACK')
    require(any(e['kind']==0 and e['code']==0 and e['_unknown'] and e['monitor']==(9 if bms else 8) for e in rows),'other ECU protection remains propagation')
    for e,kind in ((f,1),(p,5)):
        ns=[r for r in d['native'] if int(r['kind'])==kind and int(r['producer'])==producer and int(r['event_sequence'])==e['event_sequence']]
        require(len(ns)==1,'source snapshot denominator'); n=ns[0]; observed=int(n['observed_ns'])
        require(int(n['reason'])==(reason if kind==1 else 0) and n['propagation']=='0' and int(n['model_epoch'])==e['_model']==7 and
                int(n['epoch'])==e['epoch'] and int(n['enable_ns'])==e['_enable']['ns'] and e['_after']==(int(n['detail']) if kind==1 else 0) and int(n['state'])==e['_before'],'source state/identity')
        require(observed==(e['detected_ns'] if kind==1 else e['source_ns']),'original native observation time')
        ss=[r for r in d['samples'] if int(r['kind'])==kind and int(r['producer'])==producer and int(r['event_sequence'])==e['event_sequence']]
        require(len(ss)==5 and {int(s['slot']) for s in ss}==set(range(5)),'bounded sample slots')
        if kind==1:
            if bms: require(ss[1]['present']=='0' and int(n['state'])==2 and int(n['detail'])==1,'missing electrical group before native latch')
            else: require(ss[0]['present']=='1' and ss[0]['v2']=='' and int(n['state'])==7,'missing current is not zero')
        else:
            require(n['qualified']=='1' and int(n['state'])==(2 if bms else 7),'native success state')
            for s in ss[:5 if bms else 2]:
                source,dependency=int(s['source_ns']),int(s['dependency_ns'])
                require(s['present']=='1' and int(s['model_epoch'])==(2 if not bms and int(s['slot'])==1 else 7) and
                        e['_enable']['ns']<=dependency<=source<=observed and observed-source<=int(n['source_age_ns']) and observed-dependency<=int(n['dependency_age_ns']),'fresh original proof sources')
            require(e['observed_ns']-observed<=int(n['max_gap_ns']),'current healthy body')
            if not bms:
                require(e['_command']['epoch']==int(n['root_epoch'])==2 and e['_command']['sequence']==int(n['root_sequence']) and
                        e['command_source_ns']==int(n['root_source_ns']) and e['command_expiry_ns']==int(n['root_expiry_ns']) and
                        observed<e['command_expiry_ns'] and observed-int(n['dependency_ns'])<=70_000_000,'accepted live Enable identity')
            else:
                healthy=[r for r in bodies if r['owner']=='5' and r['epoch']=='2' and int(r['body_ns'])<=observed]
                require(healthy and observed-int(healthy[0]['body_ns'])>=int(n['release_dwell_ns']) and
                        all(r['omitted']=='0' and r['fault']=='0' for r in healthy) and healthy[-1]['recovery_ready']=='1' and healthy[-1]['pending_trips']=='0','new-session BMS release dwell')
    for who,period in ((5,20_000_000),(6,10_000_000)):
        actor_rows=[r for r in bodies if int(r['owner'])==who]
        require(actor_rows and all(r['raw_present']=='1' and r['model_epoch']=='7' and int(r['dependency_ns'])<=int(r['source_ns'])<=int(r['body_ns']) for r in actor_rows),'physical source remains available')
        for a,b in zip(actor_rows,actor_rows[1:]):
            require(int(b['model_sequence'])>int(a['model_sequence']),'original input model sequence')
            if a['epoch']==b['epoch']: require(int(b['body_ns'])-int(a['body_ns'])==period,'original runnable releases')
        require(all(r['omitted']==('1' if who==owner and first<=int(r['body_ns'])<restored else '0') for r in actor_rows),'only target input copy is omitted')
    target_rows=[r for r in bodies if int(r['owner'])==owner and r['epoch']=='1' and first<=int(r['body_ns'])<21_000_000_000]
    require(target_rows and all(r['gate']=='0' and int(r['fault'])==reason for r in target_rows),'restoration alone retains native latch')
    if not bms:
        missing=[r for r in target_rows if r['omitted']=='1']
        require(missing and all(r['state']=='8' and r['contacts']=='3' for r in missing),'missing current cannot open contactors')
        ready=[r for r in bodies if r['owner']=='6' and r['epoch']=='2' and r['state']=='7']
        require(ready and p['source_ns']==int(ready[0]['body_ns']) and ready[0]['contacts']=='3' and float(ready[0]['bus_v'])>=396,'actual new HV Ready')
    require(len(physical)==2400 and all(int(r['model_epoch'])==7 and abs(float(r['balance_j']))<=1e-5 for r in physical),'physical denominator/energy')
    for a,b in zip(physical,physical[1:]):
        require(int(b['source_ns'])-int(a['source_ns'])==10_000_000 and int(b['model_sequence'])>int(a['model_sequence']) and float(b['distance_m'])>=float(a['distance_m']),'no hidden physical reset')
    response=[r for r in physical if int(r['source_ns'])>=first and r['gate']=='0' and abs(float(r['torque_nm']))<=1 and float(r['pressure_pa'])>=1_000_000]
    require(response and int(response[0]['source_ns'])-first<=230_000_000,'actual torque/brake response')
    safe=[r for r in physical if 14_000_000_000<=int(r['source_ns'])<21_000_000_000]
    require(safe and all(r['gate']=='0' and int(r['contacts'])==0 and float(r['bus_v'])<=30 and abs(float(r['speed_mps']))<=.01 for r in safe),'separate stationary/HV-off evidence')
    require(d['runtime']['replaced_links']==1,'explicit existing rejoin procedure')
    return dict(pass_=True,case=d['case'],events=len(rows),intrinsic_dtc=1,qualified_passes=1,physical_samples=len(physical),
                first_detected_ns=first,first_response_ns=int(response[0]['source_ns']),restored_ns=restored,passed_source_ns=p['source_ns'])


def mutations(data):
    names=['wrong-registry','false-primary','erased-input-loss','missing-current-as-zero','wrong-proof','INIT-as-pass','erased-history','restoration-auto-heal','physical-reset','false-HV-off']
    for name in names:
        d=copy.deepcopy(data)
        if name=='wrong-registry': d['registry']=1
        elif name=='false-primary': next(e for e in d['events'] if e['kind']==1)['_unknown']=True
        elif name=='erased-input-loss': next(r for r in d['bodies'] if r['omitted']=='1')['omitted']='0'
        elif name=='missing-current-as-zero':
            s=next(r for r in d['samples'] if r['kind']=='1' and r['slot']==('1' if d['case']=='bms-input-loss' else '0'))
            if d['case']=='bms-input-loss': s['present']='1'
            else: s['v2']='0'
        elif name=='wrong-proof': next(e for e in d['events'] if e['kind']==5)['_proof_event']=(5001,7,999)
        elif name=='INIT-as-pass': next(e for e in d['events'] if e['kind']==5)['source_ns']=next(e for e in d['events'] if e['kind']==6 and e['epoch']==2)['_enable']['ns']
        elif name=='erased-history': d['records'][0]['cleared']='1'
        elif name=='restoration-auto-heal': next(r for r in d['bodies'] if r['owner']==('5' if d['case']=='bms-input-loss' else '6') and r['epoch']=='1' and int(r['body_ns'])>11_300_000_000 and r['fault']!='0')['gate']='1'
        elif name=='physical-reset': d['physical'][2100]['model_sequence']='1'
        else: d['physical'][1400]['contacts']='3'
        try: judge(d)
        except ValueError: pass
        else: raise ValueError('accepted mutation: '+name)
    return names


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('directory',type=Path); p.add_argument('--mutations',action='store_true'); a=p.parse_args()
    data=load(a.directory); result=judge(data)
    if a.mutations: result['mutations_rejected']=mutations(data)
    print(json.dumps(result,indent=2))

#!/usr/bin/env python3
"""Independent attempt/release, native session source and physical audit."""
import argparse
import copy
import json
import struct
from pathlib import Path
from audit_control_diagnostics import csv_rows, journal, require


def load(path):
    require(path.name in ('prepare','init','release'),'named phase fixture')
    return dict(phase=path.name,registry=struct.unpack_from('<I',(path/'store/manifest').read_bytes(),32)[0],events=journal(path/'store'),
                source=csv_rows(path/'startup-source.csv'),records=csv_rows(path/'records.csv'),physical=csv_rows(path/'physical.csv'),
                owners=csv_rows(path/'logical-fault-events.csv'),runtime=json.loads((path/'logical-fault.json').read_text()))


def judge(d):
    rows=d['events']; phase=d['phase']; expected=1 if phase=='release' else 9
    require(d['registry']==3 and d['runtime']['passed'] and d['runtime']['physical_ok'] and d['runtime']['model_preserved'],'registry/runtime verdict')
    require(all(e['_run']==6001 and e['_id'][1] in {7,30,31,32,33,*range(40,48)} and not e['_unmapped'] and
                e['_times'][6]['domain']==1 and e['_times'][6]['instance']==6001 for e in rows),'run/producer/clock')
    for producer in {e['_id'][1] for e in rows}:
        seq=[e['event_sequence'] for e in rows if e['_id'][1]==producer];require(seq==list(range(1,len(seq)+1)),'source sequence')
    attempts=[e for e in rows if e['kind']==9]; releases=[e for e in rows if e['kind']==6]
    require([e['epoch'] for e in attempts]==[1,2] and all(e['_id'][1]==7 and not e['_enable']['present'] and e['_source']['present'] for e in attempts),'trusted diagnostic attempts')
    require([e['epoch'] for e in releases]==[2] and releases[0]['received_roles']==255 and releases[0]['_id'][1]==7,'only successful full release')
    require(attempts[1]['event_sequence']<releases[0]['event_sequence'] and releases[0]['_enable']['ns']>=attempts[1]['source_ns'],'separate attempt and actual enable')
    faults=[e for e in rows if e['kind']==1]; passed=[e for e in rows if e['kind']==5]
    require(len(faults)==len(passed)==len(d['records'])==expected,'native fault/proof denominator')
    wanted={(7,10,9)} if expected==1 else {(7,10,9),*((40+i,11,i+1) for i in range(8))}
    require({(e['_id'][1],e['monitor'],e['subject']) for e in faults}==wanted,'actual detector scopes')
    by_id={e['_id']:e for e in rows}
    for f in faults:
        require(f['code']==0x4101 and f['epoch']==1 and f['native_reason']==3 and not f['_unknown'],'native phase timeout')
        ps=[p for p in passed if p['_occurrence']==f['_occurrence'] and p['_id'][1]==f['_id'][1]]
        require(len(ps)==1,'one recovery per original occurrence');p=ps[0];proof=by_id.get(p['_proof_event'])
        require(p['epoch']==2 and p['related_sequence']==f['event_sequence'] and p['_latch']==2 and p['_proof']==2 and
                proof and proof['kind']==0 and proof['_proof']==2 and proof['epoch']==2 and proof['_occurrence']==f['_occurrence'] and
                proof['_id'][1]==f['_id'][1] and proof['event_sequence']<p['event_sequence'] and not proof['_times'][5]['present'],'exact post-release Control metadata proof')
        require(p['_enable']['ns']==releases[0]['_enable']['ns'] and p['observed_ns']>=releases[0]['observed_ns'],'no prerelease recovery')
        for e,kind in ((f,1),(p,5)):
            ss=[s for s in d['source'] if int(s['kind'])==kind and int(s['producer'])==e['_id'][1] and int(s['event_sequence'])==e['event_sequence']]
            require(len(ss)==1,'native source row');s=ss[0]
            require(int(s['epoch'])==e['epoch'] and int(s['requested_ns'])==attempts[e['epoch']-1]['source_ns'],'source proposal identity')
            require(int(s['enable_ns'])==(e['_enable']['ns'] if e['_enable']['present'] else 0) and int(s['state'])==e['_before'] and
                    int(s['reason'])==(3 if kind==1 else 0) and int(s['accepted_roles'])==e['received_roles'],'original state/role facts')
            if kind==1:
                deadline=3_000_000_000 if phase=='prepare' else 1_041_000_000
                require(int(s['observed_ns'])==e['detected_ns']==deadline and int(s['deadline_ns'])==e['_times'][1]['ns']==deadline and
                        int(s['previous_ns'])<deadline and int(s['observed_ns'])-int(s['previous_ns'])<=200_000,'source deadline and detection')
                require(e['_enable']['present']==(phase!='prepare'),'unknown enable stays absent before INIT proposal')
                require(e['received_roles']==239 if e['monitor']==10 else e['received_roles']==0,'missing actual Drive ACK mask')
            else:
                require(int(s['observed_ns'])==e['source_ns'] and int(s['enable_ns'])<=int(s['observed_ns'])<int(s['commit_deadline_ns']) and
                        int(s['accepted_roles'])==(255 if e['monitor']==10 else 1<<(e['subject']-1)) and int(s['state'])==(4 if e['monitor']==10 else 5),'actual successful Release source')
        record=[r for r in d['records'] if (int(r['component']),int(r['monitor']),int(r['subject']))==(f['component'],f['monitor'],f['subject'])]
        require(len(record)==1 and all(record[0][k]==v for k,v in [('code','16641'),('condition','2'),('count','1'),('generation','1'),('cleared','0')]),'history remains after recovery')
    require(any(r['kind']=='session-failed' and r['epoch']=='1' for r in d['owners']),'original session failure log')
    require(not any(r['kind'] in ('run-released','normal-authorized') and r['epoch']=='1' for r in d['owners']),'failed attempt never released authority')
    physical=d['physical'];require(len(physical)==600 and all(r['model_epoch']=='7' and abs(float(r['balance_j']))<=1e-5 for r in physical),'physical denominator/energy')
    for a,b in zip(physical,physical[1:]):
        require(int(b['source_ns'])-int(a['source_ns'])==10_000_000 and int(b['model_sequence'])>int(a['model_sequence']) and float(b['distance_m'])>=float(a['distance_m']),'no hidden plant reset')
    before=[r for r in physical if int(r['source_ns'])<4_000_000_000]
    require(before and all(r['gate']=='0' and r['contacts']=='0' and float(r['bus_v'])<=30 and abs(float(r['speed_mps']))<=.01 and abs(float(r['torque_nm']))<=.1 for r in before),'actual inhibited prerelease history')
    require(d['runtime']['replaced_links']==1 and d['runtime']['rejoin_active_ns']>3_000_000_000,'actual new rejoin')
    return dict(pass_=True,phase=phase,events=len(rows),faults=expected,qualified_passes=expected,attempts=2,releases=1,physical_samples=len(physical))


def mutations(data):
    names=['legacy-registry','attempt-claims-enable','false-epoch1-release','false-timeout','wrong-source-mask','wrong-proof','early-pass','erased-history','early-gate','physical-reset']
    for name in names:
        d=copy.deepcopy(data)
        if name=='legacy-registry':d['registry']=2
        elif name=='attempt-claims-enable':next(e for e in d['events'] if e['kind']==9)['_enable']['present']=True
        elif name=='false-epoch1-release':next(e for e in d['events'] if e['kind']==6)['epoch']=1
        elif name=='false-timeout':next(e for e in d['events'] if e['kind']==1)['detected_ns']+=1
        elif name=='wrong-source-mask':d['source'][0]['accepted_roles']='255'
        elif name=='wrong-proof':next(e for e in d['events'] if e['kind']==5)['_proof_event']=(6001,7,999)
        elif name=='early-pass':next(e for e in d['events'] if e['kind']==5)['epoch']=1
        elif name=='erased-history':d['records'][0]['cleared']='1'
        elif name=='early-gate':d['physical'][100]['gate']='1'
        else:d['physical'][400]['model_sequence']='1'
        try:judge(d)
        except ValueError:pass
        else:raise ValueError('accepted mutation: '+name)
    return names


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--mutations',action='store_true');a=p.parse_args();d=load(a.directory);r=judge(d)
    if a.mutations:r['mutations_rejected']=mutations(d)
    print(json.dumps(r,indent=2))

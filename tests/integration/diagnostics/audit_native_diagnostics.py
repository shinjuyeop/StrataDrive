#!/usr/bin/env python3
"""Independent registry-2 Gateway native/journal/physical correlation audit."""
import argparse
import copy
import json
import struct
from pathlib import Path
from audit_control_diagnostics import csv_rows, journal, require


def load(path):
    loss=path.name=='central-pause'
    prefix='logical-fault' if loss else 'logical-normal'
    manifest=(path/'store'/'manifest').read_bytes()
    return dict(registry=struct.unpack_from('<I',manifest,32)[0],events=journal(path/'store'),
                records=csv_rows(path/'records.csv'),native=csv_rows(path/'native.csv'),
                physical=csv_rows(path/'physical.csv'),owners=csv_rows(path/(prefix+'-events.csv')),
                runtime=json.loads((path/(prefix+'.json')).read_text()),loss=loss)


def judge(d):
    rows=d['events']; physical=d['physical']; faults=[e for e in rows if e['kind']==1]
    require(d['registry']==2 and d['runtime']['passed'] and d['runtime']['model_preserved'],'registry/runtime/model verdict')
    require(all(e['_run']==4001 and e['_id'][1] in (7,30,31,32,33) and not e['_unmapped'] and
                e['_enable']['domain']==1 and e['_enable']['instance']==4001 for e in rows),'producer/run/clock dictionary')
    for producer in {e['_id'][1] for e in rows}:
        seq=[e['event_sequence'] for e in rows if e['_id'][1]==producer]
        require(seq==list(range(1,len(seq)+1)),'source sequence')
    require(all(int(p['model_epoch'])==7 and abs(float(p['balance_j']))<=1e-5 for p in physical),'physical model/balance')
    for a,b in zip(physical,physical[1:]):
        require(int(b['source_ns'])-int(a['source_ns'])==10_000_000 and int(b['model_sequence'])>int(a['model_sequence']) and
                float(b['distance_m'])>=float(a['distance_m']),'physical continuity')
    if not d['loss']:
        require(not faults and not d['records'] and len(physical)==9200,'normal false DTC/denominator')
        return dict(pass_=True,events=len(rows),faults=0,physical_samples=len(physical))
    require(len(faults)==len(d['records'])==2 and len(physical)==2400,'fault/sample denominator')
    require({(e['component'],e['monitor'],e['code']) for e in faults}=={(7,6,0x2001),(8,6,0x2001)},'original Gateway causes')
    require({tuple(int(r[k]) for k in ('code','component','monitor','subject')) for r in d['records']}==
            {(e['code'],e['component'],e['monitor'],e['subject']) for e in faults},'record projection')
    require(all(r['condition']=='2' and r['count']=='1' and r['generation']=='1' and r['cleared']=='0' for r in d['records']),'Passed retains history')
    sessions=[e for e in rows if e['kind']==6]
    require([e['epoch'] for e in sessions]==[1,2] and all(e['_id'][1]==7 for e in sessions),'global INIT authority')
    by_id={e['_id']:e for e in rows}; passes=[e for e in rows if e['kind']==5]
    require(len(passes)==2,'qualified pass denominator')
    for f in faults:
        require(f['epoch']==1 and f['_id'][1]=={7:30,8:31}[f['component']],'source owner')
        p=[e for e in passes if e['_occurrence']==f['_occurrence'] and e['related_sequence']==f['event_sequence'] and e['_id'][1]==f['_id'][1]]
        require(len(p)==1 and p[0]['epoch']==2,'new epoch same occurrence')
        p=p[0]; proof=by_id.get(p['_proof_event'])
        require(proof and proof['kind']==0 and proof['_proof']==p['_proof']==1 and proof['_id'][1]==f['_id'][1] and
                proof['_occurrence']==f['_occurrence'] and proof['epoch']==2 and proof['event_sequence']<p['event_sequence'] and
                not proof['_times'][5]['present'],'metadata Input proof')
        for e,kind in ((f,1),(p,5)):
            ns=[n for n in d['native'] if int(n['kind'])==kind and int(n['component'])==e['component'] and int(n['monitor'])==6]
            require(len(ns)==1,'native observation denominator'); n=ns[0]; command=e['_command']
            require(n['propagation']=='0' and int(n['epoch'])==e['epoch'] and int(n['enable_ns'])==e['_enable']['ns'] and
                    int(n['root_epoch'])==command['epoch'] and int(n['root_sequence'])==command['sequence'] and
                    int(n['root_source_ns'])==command['source']['ns'] and int(n['root_expiry_ns'])==command['expiry']['ns'] and
                    int(n['valid_until_ns'])==command['expiry']['ns'],'original identity/context')
            now=int(n['observed_ns'])
            if kind==1:
                require(now==e['detected_ns'] and f['_times'][1]['ns']==command['expiry']['ns'] and
                        0<=now-command['expiry']['ns']<=200_000,'native expiry/detection')
                require(any(a['kind']=='zone-protection-ack' and int(a['owner'])==f['component']-7 and int(a['time_ns'])>=now for a in d['owners']),'original ACK log')
                require(any(a['kind']==3 and a['_occurrence']==f['_occurrence'] and a['_id'][1]==f['_id'][1] and a['acknowledged_ns']>=now for a in rows),'source ACK event')
            else:
                require(int(n['reason'])==0 and int(n['writes'])==(2 if e['component']==7 else 1) and now==e['source_ns'] and
                        now>=e['_enable']['ns'] and now<command['expiry']['ns'] and 0<=now-int(n['dependency_ns'])<=70_000_000,'actual complete dispatch')
    first=min(e['detected_ns'] for e in faults)
    response=[p for p in physical if int(p['source_ns'])>=first and p['gate']=='0' and abs(float(p['torque_nm']))<=1 and float(p['pressure_pa'])>=1_000_000]
    require(response and int(response[0]['source_ns'])-first<=230_000_000,'original physical response')
    require(all(p['gate']=='0' for p in physical if first+230_000_000<=int(p['source_ns'])<21_000_000_000),'resumption alone stays protected')
    require(d['runtime']['replaced_links']==1,'explicit joined link replacement')
    return dict(pass_=True,events=len(rows),faults=2,qualified_passes=2,physical_samples=len(physical),
                first_detected_ns=first,first_response_ns=int(response[0]['source_ns']))


def mutations(data):
    names=['registry','expiry','propagation-as-root','wrong-proof','early-pass','partial-send','history-erased','physical-reset']
    for name in names:
        d=copy.deepcopy(data)
        if name=='registry': d['registry']=1
        elif name=='expiry': next(n for n in d['native'] if n['kind']=='1')['root_expiry_ns']='1'
        elif name=='propagation-as-root': next(n for n in d['native'] if n['kind']=='1')['propagation']='1'
        elif name=='wrong-proof': next(e for e in d['events'] if e['kind']==5)['_proof_event']=(4001,7,999)
        elif name=='early-pass': next(e for e in d['events'] if e['kind']==5)['epoch']=1
        elif name=='partial-send': next(n for n in d['native'] if n['kind']=='5' and n['component']=='7')['writes']='1'
        elif name=='history-erased': d['records'][0]['cleared']='1'
        else: d['physical'][2100]['model_sequence']='1'
        try: judge(d)
        except ValueError: pass
        else: raise ValueError('accepted mutation: '+name)
    return names


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('directory',type=Path); p.add_argument('--mutations',action='store_true'); args=p.parse_args()
    d=load(args.directory); result=judge(d)
    if args.mutations: result['mutations_rejected']=mutations(d)
    print(json.dumps(result,indent=2))

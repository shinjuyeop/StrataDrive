#!/usr/bin/env python3
"""Independent canonical journal/native-source audit of the local M9 cohort."""
import argparse
import copy
import json
from pathlib import Path
from audit_control_diagnostics import csv_rows, journal, require


def load(path):
    loss=(path/'native-authority.csv').exists()
    return dict(events=journal(path/'store'),records=csv_rows(path/'records.csv'),physical=csv_rows(path/'physical.csv'),
                owners=csv_rows(path/('logical-fault-events.csv' if loss else 'logical-normal-events.csv')),
                runtime=json.loads((path/('logical-fault.json' if loss else 'logical-normal.json')).read_text()),
                native=csv_rows(path/'native-authority.csv') if loss else [],
                zones=csv_rows(path/'native-zone.csv') if loss else [],loss=loss)


def judge(data):
    rows,physical=data['events'],data['physical']
    require(data['runtime']['passed'] and data['runtime']['model_preserved'], 'runtime/model verdict')
    require(all(e['_run']==3001 and not e['_unmapped'] and e['_enable']['domain']==1 and
                e['_enable']['instance']==3001 for e in rows), 'run/clock/unmapped')
    require({e['_id'][1] for e in rows}<={7,20,21,22,23,24}, 'producer dictionary')
    for producer in {e['_id'][1] for e in rows}:
        seq=[e['event_sequence'] for e in rows if e['_id'][1]==producer]
        require(seq==list(range(1,len(seq)+1)), 'owner sequence')
    require(all(int(p['model_epoch'])==7 and abs(float(p['balance_j']))<=1e-5 for p in physical), 'original physical identity/balance')
    for a,b in zip(physical,physical[1:]):
        require(int(b['model_sequence'])>int(a['model_sequence']) and int(b['source_ns'])-int(a['source_ns'])==10_000_000 and
                float(b['distance_m'])>=float(a['distance_m']), 'model continuity')
    faults=[e for e in rows if e['kind']==1]
    if not data['loss']:
        require(not faults and not data['records'] and len(physical)==9200, 'normal false DTC')
        return dict(pass_=True,faults=0,physical_samples=len(physical),events=len(rows))
    require(len(faults)==len(data['records'])==5 and len(physical)==2400, 'fault/sample denominator')
    require({tuple(int(r[k]) for k in ('code','component','monitor','subject')) for r in data['records']}==
            {(e['code'],e['component'],e['monitor'],e['subject']) for e in faults}, 'journal/record projection keys')
    sessions=[e for e in rows if e['kind']==6]
    require([e['epoch'] for e in sessions]==[1,2] and all(e['_id'][1]==7 for e in sessions), 'global INIT authority')
    expired=[e for e in faults if e['code']==0x2001]
    deadlines=[e for e in faults if e['code']==0x4002]
    require({e['component'] for e in expired}=={9,5,4} and {e['component'] for e in deadlines}=={7,8}, 'local fault classification')
    pass_rows=[e for e in rows if e['kind']==5]
    require(len(pass_rows)==5, 'one qualified pass per original monitor')
    by_id={e['_id']:e for e in rows}
    for f in faults:
        require(f['epoch']==1 and f['_id'][1]!=7, 'original detector producer')
        require(f['_id'][1]=={7:20,8:21,9:22,5:23,4:24}[f['component']], 'owner actor/producer binding')
        passed=[p for p in pass_rows if p['_occurrence']==f['_occurrence'] and p['related_sequence']==f['event_sequence'] and p['_id'][1]==f['_id'][1]]
        require(len(passed)==1 and passed[0]['epoch']==2 and passed[0]['_latch']==2, 'same occurrence across trusted INIT')
        p=passed[0]; proof=by_id.get(p['_proof_event'])
        require(proof and proof['_id'][1]==f['_id'][1] and proof['epoch']==2 and proof['_occurrence']==f['_occurrence'] and
                proof['event_sequence']<p['event_sequence'] and proof['_proof']==p['_proof'], 'exact qualified proof')
        if f['code']==0x2001:
            require(f['monitor']==5 and f['native_reason']==1 and p['_proof']==1 and proof['kind']==0 and not proof['_times'][5]['present'], 'command proof is not physical Actual')
            require(11_000_000_000<=f['detected_ns']<11_200_000_000 and
                    0<=f['detected_ns']-f['command_expiry_ns']<=200_000, 'independent exclusive command expiry')
            for e,kind in [(f,1),(p,5)]:
                native=[n for n in data['native'] if int(n['kind'])==kind and int(n['component'])==e['component']]
                require(len(native)==1, 'native authority observation')
                n=native[0]; command=e['_command']
                require(int(n['epoch'])==e['epoch'] and int(n['enable_ns'])==e['_enable']['ns'] and
                        int(n['parent_epoch'])==command['epoch'] and int(n['parent_sequence'])==command['sequence'] and
                        int(n['parent_source_ns'])==command['source']['ns'] and int(n['command_expiry_ns'])==command['expiry']['ns'], 'original parent/child clocks')
                if kind==1:
                    require(n['independent']=='1' and int(n['observed_ns'])==e['detected_ns'] and
                            int(n['envelope_deadline_ns'])<=int(n['command_expiry_ns']), 'original exclusive authority')
                    owner={9:2,5:3,4:4}[f['component']]
                    require(any(o['kind']=='command-expired' and int(o['owner'])==owner and int(o['time_ns'])==f['detected_ns'] and
                                int(o['deadline_ns'])==f['command_expiry_ns'] for o in data['owners']), 'original owner detector log')
                    require(any(e['kind']==2 and e['_occurrence']==f['_occurrence'] and e['_id'][1]==f['_id'][1] and
                                e['selected_ns']==f['detected_ns'] for e in rows), 'source-selected protection')
                else:
                    now=int(n['observed_ns'])
                    require(now==p['observed_ns'] and now>=sessions[1]['_enable']['ns'] and now<int(n['command_expiry_ns']) and
                            0<=now-int(n['oldest_input_ns'])<=70_000_000 and now>=int(n['sent_ns']), 'successful native body/authority')
        else:
            require(f['monitor']==4 and f['native_reason']==2 and f['detected_ns']==11_200_000_000 and p['_proof']==2, 'Zone resume deadline monitor')
            require(proof['kind']==0 and not proof['_times'][5]['present'] and proof['_after']==(3 if f['component']==7 else 28), 'fresh complete Zone inputs/control proof')
            for e,kind in [(f,1),(p,5)]:
                native=[n for n in data['zones'] if int(n['kind'])==kind and int(n['component'])==e['component']]
                require(len(native)==1 and int(native[0]['epoch'])==e['epoch'] and int(native[0]['enable_ns'])==e['_enable']['ns'] and
                        int(native[0]['observed_ns'])==e['observed_ns'] and int(native[0]['fault'])==(2 if kind==1 else 0), 'native Zone snapshot')
                if kind==1:
                    require(e['_times'][1]['ns']==int(native[0]['violation_ns']) and
                            e['_times'][1]['ns']<e['detected_ns'], 'native deadline violation/detection separation')
    require(all(r['condition']=='2' and r['count']=='1' and r['generation']=='1' and r['cleared']=='0' for r in data['records']), 'Passed retains DTC history')
    paused=[o for o in data['owners'] if o['kind']=='owner-stopped' and int(o['time_ns'])==11_000_000_000]
    require({int(o['owner']) for o in paused}=={0,1,7}, 'predeclared stopped cohort')
    require(not any(o['kind'] in ('fault-observed','zone-protection-ack') and int(o['owner']) in (0,1,7) and
                    11_000_000_000<=int(o['time_ns'])<11_200_000_000 for o in data['owners']), 'stopped owner cannot observe/ACK')
    first=min(e['detected_ns'] for e in expired)
    responses=[p for p in physical if int(p['source_ns'])>=first and abs(float(p['torque_nm']))<=1 and float(p['pressure_pa'])>=1_000_000 and p['gate']=='0']
    require(responses and int(responses[0]['source_ns'])-first<=230_000_000, 'physical torque/brake response')
    require(all(p['gate']=='0' for p in physical if first+230_000_000<=int(p['source_ns'])<21_000_000_000), 'resumption alone cannot heal')
    require(data['runtime']['replaced_links']==1, 'explicit failed-link replacement')
    return dict(pass_=True,faults=5,command_loss=3,zone_deadline=2,qualified_passes=5,events=len(rows),physical_samples=len(physical),
                first_detected_ns=first,first_physical_response_ns=int(responses[0]['source_ns']))


def mutations(data):
    names=['wrong-expiry','unqualified-reference','early-pass','false-native-independent','history-erased','physical-reset','stopped-ack']
    for name in names:
        d=copy.deepcopy(data); f=next(e for e in d['events'] if e['kind']==1 and e['code']==0x2001)
        if name=='wrong-expiry': f['command_expiry_ns']+=1_000_000
        elif name=='unqualified-reference': next(e for e in d['events'] if e['kind']==5)['_proof_event']=(3001,7,999)
        elif name=='early-pass': next(e for e in d['events'] if e['kind']==5)['epoch']=1
        elif name=='false-native-independent': d['native'][0]['independent']='0'
        elif name=='history-erased': d['records'][0]['cleared']='1'
        elif name=='physical-reset': d['physical'][2100]['model_sequence']='1'
        else: d['owners'].append(dict(kind='zone-protection-ack',owner='0',time_ns='11050000000'))
        try: judge(d)
        except ValueError: pass
        else: raise ValueError('accepted mutation: '+name)
    return names


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('directory',type=Path); parser.add_argument('--mutations',action='store_true')
    args=parser.parse_args(); data=load(args.directory); result=judge(data)
    if args.mutations: result['mutations_rejected']=mutations(data)
    print(json.dumps(result,indent=2))

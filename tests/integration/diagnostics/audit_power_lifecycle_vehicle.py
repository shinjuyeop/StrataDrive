#!/usr/bin/env python3
"""Audit retained Power lifecycle detector, physical response and durable recovery."""
import argparse
import copy
import json
from pathlib import Path
from audit_control_diagnostics import csv_rows, journal, require


def load(path):
    return dict(recipe=json.loads((path/'recipe.json').read_text()), events=journal(path/'store'),
                **{name: csv_rows(path/(name+'.csv')) for name in ('native', 'samples', 'records', 'physical', 'injections', 'owner-events')})


def judge(d):
    r=d['recipe']; reason=r['reason']; recovery=r['recovery']; events=d['events']; physical=d['physical']
    require(reason in (1, 3, 7, 9, 10) and r['startup']==(reason in (1, 7)), 'fixed recipe')
    require(r['physical_ok'] and r['diagnostics_complete'] and r['duration_ns']==(24 if recovery else 15)*10**9, 'execution bounds')
    require(all(e['_run']==9601 and e['_enable']['domain']==1 and e['_enable']['instance']==9601 and not e['_unmapped'] for e in events), 'source dictionary')
    require(not any(e['kind'] in (7, 8) for e in events), 'recording completeness')
    for who in {e['_id'][1] for e in events}:
        seq=[e['event_sequence'] for e in events if e['_id'][1]==who]
        require(seq==list(range(1,len(seq)+1)), 'producer continuity')
    sessions=[e for e in events if e['kind']==6]; faults=[e for e in events if e['kind']==1]; passes=[e for e in events if e['kind']==5]
    require([e['epoch'] for e in sessions]==([1,2] if recovery else [1]) and all(e['_id'][1]==7 for e in sessions), 'global Release')
    require(len(faults)==len(d['records'])==(2 if reason==3 else 1), 'actual roots')
    require(len(passes)==(len(faults) if recovery else 0), 'no implicit recovery')
    by_id={e['_id']:e for e in events}
    if reason==3:
        require(not d['native'] and not any(e['monitor']==9 and e['kind'] in (1,5) for e in events), 'preempted local watchdog has no false DTC')
        drops=[x for x in d['owner-events'] if x['event']=='dropped' and x['owner']=='6']
        require(len(drops)==3 and all(11_000_000_000<=int(x['ns'])<11_200_000_000 for x in drops), 'actual Power packet drops')
        require({f['_id'][1] for f in faults}=={30,31}, 'both actual gateway roots')
    else:
        require(d['injections'] and int(d['injections'][0]['ns'])==r['injected_ns'] and
                int(d['injections'][-1]['ns'])==r['restored_ns'] and d['injections'][-1]['fault']=='0', 'restore transition')
        require(r['restored_ns']=={1:1_200_000_000,7:4_000_000_000,9:12_500_000_000,10:13_500_000_000}[reason], 'declared restoration')
    for f in faults:
        require(f['epoch']==1 and not f['_unknown'], 'intrinsic initial occurrence')
        if reason==3:
            require((f['code'],f['monitor'],f['native_reason'])==(0x2001,6,2) and
                    0<=f['detected_ns']-f['command_expiry_ns']<=1_000_000, 'original command expiry detector')
        else:
            require((f['code'],f['component'],f['monitor'],f['_id'][1],f['native_reason'])==(0x3201,6,9,33,reason), 'actual native reason')
            n=next(x for x in d['native'] if int(x['event_sequence'])==f['event_sequence'])
            require(int(n['observed_ns'])==f['detected_ns'] and n['reason']==str(reason) and n['epoch']=='1' and
                    n['model_epoch']=='7' and n['propagation']=='0' and int(n['state'])==f['_before'], 'native snapshot')
            require([int(n['timing'+str(i)]) for i in range(10)]==[1_000_000,30_000_000,50_000_000,70_000_000,500_000_000,100_000_000,2_000_000_000,300_000_000,1_000_000_000,20_000_000], 'original timing configuration')
            if reason in (7,9,10):
                slot={7:6,9:7,10:8}[reason]
                require(f['detected_ns']-int(n['phase_origin_ns'])==int(n['timing'+str(slot)]), 'phase timeout origin')
            raw=[s for s in d['samples'] if int(s['event_sequence'])==f['event_sequence']]
            require(len(raw)==5 and raw[0]['present']=='1' and raw[0]['epoch']=='7' and
                    int(n['enable_ns'])<=int(raw[0]['dependency_ns'])<=int(raw[0]['source_ns'])<=f['detected_ns'] and
                    f['detected_ns']-int(raw[0]['source_ns'])<=int(n['timing2']), 'original acquisition')
            if reason==1: require(int(n['detail'])&1, 'energized startup contact')
            else: require(float(raw[0]['v2' if reason==9 else 'v1'])=={7:0,9:20,10:100}[reason], 'raw injected sample')
        rec=[x for x in d['records'] if int(x['component'])==f['component'] and int(x['monitor'])==f['monitor']]
        require(len(rec)==1 and all(rec[0][k]==v for k,v in [('condition','2' if recovery else '1'),('count','1'),('generation','1'),('cleared','0')]), 'retained history')
        response=[p for p in physical if int(p['source_ns'])>=f['detected_ns'] and p['gate']=='0' and abs(float(p['torque_nm']))<=1 and float(p['pressure_pa'])>=1_000_000]
        require(response and int(response[0]['source_ns'])-f['detected_ns']<=230_000_000, 'physical protection response')
        if recovery:
            p=next(x for x in passes if x['component']==f['component'] and x['monitor']==f['monitor'])
            proof=by_id.get(p['_proof_event'])
            require(p['epoch']==2 and p['_occurrence']==f['_occurrence'] and p['_id'][1]==f['_id'][1] and
                    p['related_sequence']==f['event_sequence'] and p['_latch']==2 and proof and proof['kind']==0 and
                    proof['_occurrence']==f['_occurrence'] and proof['event_sequence']<p['event_sequence'] and
                    p['source_ns']>sessions[1]['_enable']['ns'], 'new native recovery proof')
            if reason!=3:
                n=next(x for x in d['native'] if int(x['event_sequence'])==p['event_sequence'])
                require(n['qualified']=='1' and n['epoch']=='2' and n['reason']=='0' and n['state']=='7' and int(n['observed_ns'])==p['source_ns'], 'actual Power Ready')
    require(len(physical)==(2400 if recovery else 1500) and all(p['model_epoch']=='7' and abs(float(p['balance_j']))<=1e-5 for p in physical), 'physical denominator and conservation')
    for a,b in zip(physical,physical[1:]):
        require(int(b['source_ns'])-int(a['source_ns'])==10_000_000 and int(b['model_sequence'])>int(a['model_sequence']) and float(b['distance_m'])>=float(a['distance_m']), 'single model continuity')
    held=[p for p in physical if 14_000_000_000<=int(p['elapsed_ns'])<20_000_000_000]
    require(held and all(p['gate']=='0' and p['contacts']=='0' and float(p['bus_v'])<=30 and abs(float(p['speed_mps']))<=.01 and abs(float(p['torque_nm']))<=1 and float(p['pressure_pa'])>=1_000_000 for p in held), 'stationary HV-off')
    return dict(passed=True, roots=len(faults), qualified_passes=len(passes), physical_samples=len(physical))


def mutations(data):
    names=['false-reason','erased-history','model-reset','false-hold','no-response']
    if data['recipe']['reason']==3:names+=['no-drop']
    else:names+=['restamped','wrong-timeout']
    if data['recipe']['recovery']:names+=['INIT-as-pass','wrong-proof']
    for name in names:
        d=copy.deepcopy(data);f=next(e for e in d['events'] if e['kind']==1)
        if name=='false-reason':f['native_reason']=99
        elif name=='erased-history':d['records'][0]['count']='0'
        elif name=='model-reset':d['physical'][100]['model_sequence']='1'
        elif name=='false-hold':d['physical'][1400]['contacts']='3'
        elif name=='no-response':
            for p in d['physical']:
                if f['detected_ns']<=int(p['source_ns'])<=f['detected_ns']+230_000_000:p['pressure_pa']='0'
        elif name=='no-drop':d['owner-events']=[x for x in d['owner-events'] if x['event']!='dropped']
        elif name=='restamped':d['samples'][0]['source_ns']=str(f['detected_ns']+1)
        elif name=='wrong-timeout':d['native'][0]['timing6']='3000000000'
        elif name=='INIT-as-pass':next(e for e in d['events'] if e['kind']==5)['source_ns']=next(e for e in d['events'] if e['kind']==6 and e['epoch']==2)['_enable']['ns']
        else:next(e for e in d['events'] if e['kind']==5)['_proof_event']=(9601,7,999)
        try:judge(d)
        except (ValueError,StopIteration):continue
        raise ValueError('accepted mutation: '+name)
    return names


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--mutations',action='store_true');a=p.parse_args()
    data=load(a.directory);result=judge(data)
    if a.mutations:result['mutations_rejected']=mutations(data)
    print(json.dumps(result,indent=2))

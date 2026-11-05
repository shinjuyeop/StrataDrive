#!/usr/bin/env python3
"""Independently join Clock fault, explicit revalidation, continuous native samples and DTC proof."""
import argparse
import copy
import json
from pathlib import Path
from audit_control_diagnostics import csv_rows, journal, require


def load(path):
    return dict(recipe=json.loads((path/'recipe.json').read_text()),events=journal(path/'store'),
                **{n:csv_rows(path/(n+'.csv')) for n in ('samples','physical','records','original')})


def judge(d):
    r=d['recipe'];events=d['events'];samples=d['samples'];physical=d['physical'];trust=r['trust']
    require(r['physical_ok'] and r['revalidated']==trust and r['injection_ns']==11_000_000_000 and r['rollback_ns']==2_000_000 and
            r['checked_ns']==20_000_000_000 and r['revision']==1, 'declared clock intervention')
    require(not any(e['kind'] in (7,8) or e['_unmapped'] for e in events), 'recording completeness')
    for who in {e['_id'][1] for e in events}:
        require([e['event_sequence'] for e in events if e['_id'][1]==who]==list(range(1,1+sum(e['_id'][1]==who for e in events))), 'source continuity')
    require(all(e['_run']==9701 for e in events), 'run identity')
    faults=[e for e in events if e['kind']==1 and e['code']==0x4001];passes=[e for e in events if e['kind']==5 and e['code']==0x4001]
    require(len(faults)==1 and len(passes)==int(trust), 'no implicit Clock recovery')
    f=faults[0];require(f['epoch']==1 and f['monitor']==11 and f['component']==10 and f['subject']==6 and not f['_times'][2]['trusted'], 'original clock scope and untrusted detection')
    require(len(d['original'])==1,'native original denominator');o=d['original'][0]
    require(int(o['reason'])==1 and int(o['observed_ns'])==f['detected_ns']==r['injection_ns']-r['rollback_ns'] and
            int(o['previous_ns'])>int(o['observed_ns']), 'actual native rollback detector')
    sessions=[e for e in events if e['kind']==6]
    require([e['epoch'] for e in sessions]==[1,2] and all(e['received_roles']==255 for e in sessions), 'actual full Release')
    require(len(d['records'])==1 and d['records'][0]['count']=='1' and d['records'][0]['cleared']=='0' and
            d['records'][0]['condition']==('2' if trust else '0'), 'history and no automatic clear')
    if trust:
        p=passes[0];proof=next((e for e in events if e['_id']==p['_proof_event']),None)
        require(proof and proof['kind']==0 and proof['_proof']==p['_proof']==2 and p['_occurrence']==proof['_occurrence']==f['_occurrence'] and
                p['_id'][1]==proof['_id'][1]==f['_id'][1] and p['related_sequence']==f['event_sequence'] and
                proof['event_sequence']<p['event_sequence'] and p['epoch']==2 and p['_before']==r['revision'], 'retained occurrence and linked proof')
        begin=proof['_times'][1]['ns'];end=p['source_ns']
        require(p['measured']==end-begin>=100_000_000 and begin>=sessions[1]['_enable']['ns'], 'continuous recovery duration')
        window=[s for s in samples if begin<=int(s['observed_ns'])<=p['observed_ns']]
        require(window and int(window[-1]['source_ns'])==end and int(window[-1]['observed_ns'])==p['observed_ns'], 'original sampled proof endpoint')
        previous=begin
        for s in window:
            now,source=int(s['observed_ns']),int(s['source_ns'])
            require(s['epoch']=='2' and s['release_mask']=='255' and s['gate']==s['healthy']=='1' and
                    int(s['requested_ns'])>=r['checked_ns'] and int(s['enable_ns'])==sessions[1]['_enable']['ns'] and
                    previous<=source<=now and now-source<=30_000_000 and source-previous<=30_000_000, 'trusted fresh unbroken native observation')
            previous=source
    require(len(physical)==2400 and all(p['model_epoch']=='7' for p in physical), 'single physical model denominator')
    for a,b in zip(physical,physical[1:]):require(int(b['source_ns'])-int(a['source_ns'])==10_000_000 and int(b['sequence'])>int(a['sequence']), 'physical continuity')
    response=[p for p in physical if int(p['source_ns'])>=r['injection_ns'] and p['gate']=='0' and abs(float(p['torque_nm']))<=1 and float(p['pressure_pa'])>=1_000_000]
    require(response and int(response[0]['source_ns'])-r['injection_ns']<=230_000_000, 'physical protection from trusted injection clock')
    held=[p for p in physical if 14_000_000_000<=int(p['elapsed_ns'])<20_000_000_000]
    require(held and all(p['gate']=='0' and p['contacts']=='0' and float(p['bus_v'])<=30 and abs(float(p['speed_mps']))<=.01 for p in held), 'stationary HV-off before new INIT')
    return dict(passed=True,roots=1,qualified_passes=len(passes),samples=len(samples),physical_samples=len(physical))


def mutations(data):
    names=['trusted-fault','erased-history','physical-reset','no-rollback','false-hold']
    if data['recipe']['trust']:names+=['no-revalidation','wrong-proof','short-window','wrong-release','stale-source','unhealthy']
    for name in names:
        d=copy.deepcopy(data)
        if name=='trusted-fault':next(e for e in d['events'] if e['kind']==1 and e['code']==0x4001)['_times'][2]['trusted']=True
        elif name=='erased-history':d['records'][0]['count']='0'
        elif name=='physical-reset':d['physical'][100]['sequence']='1'
        elif name=='no-rollback':d['original'][0]['previous_ns']=d['original'][0]['observed_ns']
        elif name=='false-hold':d['physical'][1400]['contacts']='3'
        elif name=='no-revalidation':d['recipe']['revalidated']=False
        else:
            p=next(e for e in d['events'] if e['kind']==5 and e['code']==0x4001)
            if name=='wrong-proof':p['_proof_event']=(9701,7,999)
            elif name=='short-window':p['measured']=99_000_000
            else:
                row=next(s for s in d['samples'] if int(s['observed_ns'])==p['observed_ns'])
                row[{'wrong-release':'release_mask','stale-source':'source_ns','unhealthy':'healthy'}[name]]='0'
        try:judge(d)
        except (ValueError,StopIteration):continue
        raise ValueError('accepted mutation: '+name)
    return names


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--mutations',action='store_true');a=p.parse_args()
    data=load(a.directory);result=judge(data)
    if a.mutations:result['mutations_rejected']=mutations(data)
    print(json.dumps(result,indent=2))

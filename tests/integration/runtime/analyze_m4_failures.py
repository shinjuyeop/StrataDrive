#!/usr/bin/env python3
"""Audit original M4 cohort without executing/relabeling any workload."""
import argparse
import csv
import hashlib
import json
import statistics
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cohort',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();root=args.cohort;out=args.output;out.mkdir(parents=True,exist_ok=False)
    metadata=json.loads((root/'metadata.json').read_text());trials=json.loads((root/'cohort.json').read_text())
    fingerprints={};rows=[];windows=[];controls=[]
    def read(path):
        fingerprints[str(path.relative_to(root))]=hashlib.sha256(path.read_bytes()).hexdigest()
        return json.loads(path.read_text())
    for trial in trials:
        if trial['verdict']!='FAIL':continue
        folder=root/trial['raw'];command=read(folder/'command.json')
        prefix=folder/'result'/('wall-normal' if trial['case']=='normal' else 'wall-fault')
        result=read(prefix.with_suffix('.json'))
        for suffix in ('-execution.csv','-events.csv'):
            p=Path(str(prefix)+suffix);fingerprints[str(p.relative_to(root))]=hashlib.sha256(p.read_bytes()).hexdigest()
        jobs=[{k:int(v) for k,v in r.items()} for r in csv.DictReader(open(str(prefix)+'-execution.csv'))]
        events=list(csv.DictReader(open(str(prefix)+'-events.csv')))
        priorities=[18,18,10,10,10,9,10,11,19,20]
        setup=len(result['threads'])==10 and result['startup_ok']
        for t in result['threads']:
            cpu=0 if t['owner']<2 or t['owner']>=8 else 1
            setup=setup and t['setup_error']==0 and t['affinity']==[cpu] and t['cpu']==cpu and t['policy']==int(trial['policy']=='fifo') and t['priority']==(priorities[t['owner']] if trial['policy']=='fifo' else 0)
        load=read(folder/'load.json') if trial['loaded'] else None
        control=not load or (load['policy']==0 and load['affinity']==[1] and load['cpu_ns']>=100000000)
        assert setup and control and len(jobs)==12110
        counts=0
        for owner in range(10):
            owned=[j for j in jobs if j['owner']==owner]
            assert len(owned)==1211
            first=owned[0]['release_ns']
            for i,j in enumerate(owned):
                assert j['slot']==i and j['release_ns']==first+i*2000000 and j['deadline_ns']==j['release_ns']+4000000
                assert bool(j['start_ns'])==bool(j['end_ns'])
                assert not j['start_ns'] or j['release_ns']<=j['start_ns']<=j['end_ns']
                assert not j['detected_ns'] or j['detected_ns']>=j['deadline_ns']
            missed=[j for j in owned if not j['end_ns'] or j['end_ns']>j['deadline_ns']];counts+=len(missed)
            if not missed:continue
            j=missed[0];before=[v for v in owned if v['end_ns'] and v['slot']<j['slot']];after=[v for v in owned if v['end_ns'] and v['slot']>j['slot']]
            phase=statistics.median((v['start_ns']-v['release_ns'])/1e6 for v in before[-5:]) if before else 0
            observed=[v for v in owned if v['end_ns']]
            detect=next((e for e in events if e['kind']=='deadline-detected' and int(e['code'])==owner),None)
            rows.append(dict(run=trial['raw'],policy=trial['policy'],loaded=trial['loaded'],owner=owner,misses=len(missed),late_body=sum(v['end_ns']>v['deadline_ns'] for v in observed),first_slot=j['slot'],release_ns=j['release_ns'],deadline_ns=j['deadline_ns'],detected_ns=j['detected_ns'],prior5_median_phase_ms=phase,max_completed_guard_gap_ms=max((b['start_ns']-a['start_ns'])/1e6 for a,b in zip(observed,observed[1:])),max_actual_poll_gap_ms=result['timing'][owner]['max_poll_gap_ms'],max_all_body_ms=result['timing'][owner]['max_body_us']/1000,setup_control=setup,load_control=control))
            if owner==9:
                windows.extend(dict(run=trial['raw'],**v) for v in owned if j['slot']-5<=v['slot']<=j['slot']+5)
                assert before and after and before[-1]['end_ns']<after[0]['start_ns']<j['deadline_ns']
                assert detect and int(detect['time_ns'])<int(next(e['time_ns'] for e in events if e['kind']=='owner-stopped'))
        assert counts==result['deadline_misses']
        controls.append(dict(run=trial['raw'],setup_control=setup,load_control=control,command=command,load=load,original_verdict=trial['verdict'],reason=result['reason']))
    for name,values in (('misses.csv',rows),('fifo-window.csv',windows)):
        with (out/name).open('w') as f:
            w=csv.DictWriter(f,list(values[0]),lineterminator='\n');w.writeheader();w.writerows(values)
    report=dict(original_metadata=metadata,scope='post-run audit, no replacement run or changed verdict',failed_runs=len(controls),controls=controls,raw_sha256=fingerprints,
                findings={'code':'private periodic origins differ from common guard release; newest-only admission exposes phase crossing; hot audit/trace vectors allocate after startup',
                          'configuration':'all seven requested CPU/policy/priority and load controls match; no evidence of setup fallback',
                          'environment':'OTHER six failures correlated across CPU1 owners under OTHER busy load; skipped opportunities, no completed body deadline violations',
                          'unconfirmed':'original FIFO extra wake delay cause; no requested wake timestamps or kernel timer/wakeup/switch trace in original run; no proof allocation caused that miss'})
    (out/'analysis.json').write_text(json.dumps(report,indent=2)+'\n');print('audited',len(controls),'original FAIL runs without rerunning')


if __name__=='__main__':main()

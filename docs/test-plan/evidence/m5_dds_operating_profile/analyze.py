#!/usr/bin/env python3
"""Offline audit of preserved attempts; does not rewrite any raw verdict."""
import collections,csv,json,math
from pathlib import Path
import sys
root=Path(sys.argv[1]);out=Path(__file__).resolve().parent
rows=[];packets=[];warnings=[];threads=[];qos=[]
for cohort in ('pre-fix','cohort-v1','readiness-v2'):
 for trial in json.loads((root/cohort/'results.json').read_text()):
  name=trial.get('id','normal/partial');folder=root/cohort/name
  detail=trial['result'];profile=trial.get('profile','normal');case=trial.get('case','partial')
  san='NOT APPLICABLE' if profile=='normal' else 'FAIL' if trial.get('tsan_warnings',0) or trial.get('sanitizer_clean') is False else 'INCOMPLETE (expected peer SIGKILL)' if case=='peer-kill' else 'PASS' if trial['exit']==0 else 'INCOMPLETE (process failure)'
  if 'sanitizer_verdict' in trial:san=trial['sanitizer_verdict']
  record=dict(cohort=cohort,id=name,profile=profile,case=case,config=trial.get('config','D'),exit=trial['exit'],raw_verdict=trial.get('verdict',trial.get('legacy_verdict')),sanitizer_verdict=san,functional=detail.get('functional'),tsan_warnings=trial.get('tsan_warnings',0),negative_control_pass=trial.get('negative_control_pass'))
  rtt=[];late=0;rej=lost=0;whc=0
  for p in folder.glob('*.csv'):
   if p.name.endswith(('.objects.csv','.proxy.csv','.alloc.csv','.threads.csv','-qos.csv','-status.csv')):continue
   for event in csv.DictReader(p.open()):
    event={**event,'cohort':cohort,'trial':name,'role':p.name.split('-')[0]};packets.append(event)
    if event['event']!='send':
     event['age_ns']=int(event['time_ns'])-int(event['source_ns'])
     if event['role']=='central':rtt.append(event['age_ns']/1e6)
     if int(event['time_ns'])>=int(event['deadline_ns']):late+=1
     if event['accepted']=='1':assert int(event['time_ns'])<min(int(event['deadline_ns']),int(event['inner_expiry_ns']))
  for p in folder.glob('*.objects.csv'):
   for obj in csv.DictReader(p.open()):whc=max(whc,int(obj['unacked_bytes']))
  for p in folder.glob('*.reader-status.csv'):
   for s in csv.DictReader(p.open()):rej+=int(s['rejected_total']);lost+=int(s['lost_total'])
  for p in folder.glob('*.threads.csv'):
   for t in csv.DictReader(p.open()):threads.append(dict(cohort=cohort,trial=name,file=p.name,**t))
  for p in folder.glob('*-qos.csv'):
   for q in csv.DictReader(p.open()):qos.append(dict(cohort=cohort,trial=name,file=p.name,**q))
  for p in folder.glob('*.stderr'):
   for line in p.read_text().splitlines():
    if line.startswith('SUMMARY: ThreadSanitizer:'):warnings.append(dict(cohort=cohort,trial=name,file=p.name,summary=line))
  rtt.sort();record.update(reader_rejected=rej,reader_lost=lost,expired_events=late,result_samples=len(rtt),rtt_max_ms=max(rtt,default=None),rtt_p95_ms=rtt[math.ceil(.95*len(rtt))-1] if rtt else None,max_observed_unacked_bytes=whc)
  rows.append(record)
for name,data in [('results',rows),('packets',packets),('threads',threads),('qos',qos)]:
 keys=list(dict.fromkeys(k for r in data for k in r))
 with (out/(name+'.csv')).open('w') as f:w=csv.DictWriter(f,fieldnames=keys,lineterminator="\n");w.writeheader();w.writerows(data)
(out/'analysis.json').write_text(json.dumps({'attempts':len(rows),'cohorts':{c:dict(collections.Counter(r['raw_verdict'] for r in rows if r['cohort']==c)) for c in ('pre-fix','cohort-v1','readiness-v2')},'warnings':warnings},indent=2)+'\n')
for config in 'ABCD':
 group=[r for r in rows if r['cohort']=='cohort-v1' and r['id'].startswith('normal-'+config+'-')]
 print(config,[(r['raw_verdict'],r['rtt_max_ms'],r['rtt_p95_ms'],r['reader_rejected'],r['expired_events']) for r in group])
print('attempts',len(rows),'warnings',len(warnings),'readiness',[(r['id'],r['raw_verdict']) for r in rows if r['cohort']=='readiness-v2'])

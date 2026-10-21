#!/usr/bin/env python3
"""Recompute cohort/raw exits and deadline timelines from preserved tar members."""
import argparse,csv,io,json,tarfile
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--archives',nargs='+',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 data={}
 for archive in a.archives:
  with tarfile.open(archive) as tar:
   for m in tar:
    if m.isfile() and (m.name.endswith(('.json','.events.csv')) or m.name.endswith(('plant-events.csv','leaf-events.csv'))):
     data[m.name]=tar.extractfile(m).read()
 cohorts=[];timeline=[]
 for name,raw in sorted(data.items()):
  if not name.endswith('/plan.json'):continue
  base=name.rsplit('/',1)[0]
  try:plan=json.loads(raw);runs=json.loads(data[base+'/results.json'])
  except (KeyError,ValueError):continue
  if not isinstance(runs,list) or not all('case' in r and 'exit' in r for r in runs):continue
  cohort={'cohort':base,'selected_final_cohort':('someip-native-qualified-' in base or 'someip-native-qualified48/' in base),'intrusive':base.endswith('tsan-gdb'),'acceptance_excluded_reason':('GDB diagnostic only' if base.endswith('tsan-gdb') else 'old full-queue oracle did not assert overflow' if base.endswith('overflow-before') else None),'profile':plan.get('profile'),'native_watch':plan.get('native_watch',False),'fifo':plan.get('fifo',False),'loaded':plan.get('loaded',False),'binary_sha256':plan.get('binary_sha256'),'cases':[]}
  for r in runs:
   prefix=base+'/'+r['case']+'-'+str(r.get('repeat',1));result=json.loads(data.get(prefix+'/result.json',b'{}'))
   row=dict(r,raw_result_present=bool(result),observed_pass=result.get('pass'),native=result.get('native'),error=result.get('error'),sdk_errors=result.get('sdk_errors'),sanitizer=result.get('sanitizer_diagnostics'),processes=result.get('processes',[]))
   # Exit is immutable; intrusive GDB and stageA's old weak oracle are excluded.
   cohort['cases'].append(row)
   for fname,content in data.items():
    if fname.startswith(prefix+'/') and fname.endswith('.native.watch.json'):
     info=json.loads(content);timeline.append({'cohort':base,'case':r['case'],'process':fname.rsplit('/',1)[-1],'event':'native-first-fault','ns':info.get('fault_ns',0),'original_deadline':info.get('fault_deadline',0),'epoch':info.get('fault_epoch',0)})
   for role in ('central-1','front-1','central-2','front-2'):
    key=prefix+'/'+role+'.events.csv'
    if key not in data:continue
    keep={'native-injection','injection','transport-overflow','overflow-extra-send','local-protection','native-watch-protection','central-protection','leaf-protection-selected','normal-armed','all-eight-released','epoch-issued','remote-protection-selected'}
    for e in csv.DictReader(io.StringIO(data[key].decode())):
     if e['event'] in keep:timeline.append({'cohort':base,'case':r['case'],'process':role,'event':e['event'],'ns':int(e['ns']),'original_deadline':int(e['deadline']),'epoch':int(e['epoch'])})
   for fname,content in data.items():
    if not fname.startswith(prefix+'/') or not fname.endswith('leaf-events.csv'):continue
    for e in csv.DictReader(io.StringIO(content.decode())):
     if e['event']!='valid-input':timeline.append({'cohort':base,'case':r['case'],'process':fname.rsplit('/',1)[-1],'event':e['event'],'ns':int(e['ns']),'original_deadline':int(e['deadline']),'epoch':int(e['epoch'])})
  cohort['pass']=sum(r['exit']==0 for r in runs);cohort['fail']=sum(r['exit']!=0 for r in runs);cohorts.append(cohort)
 a.output.mkdir(exist_ok=True,parents=True)
 (a.output/'results-summary.json').write_text(json.dumps(cohorts,indent=2)+'\n')
 with (a.output/'timeline.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=['cohort','case','process','event','ns','original_deadline','epoch']);w.writeheader();w.writerows(timeline)
 print(json.dumps({'cohorts':len(cohorts),'runtime_requests':sum(len(c['cases']) for c in cohorts),'raw_pass':sum(c['pass'] for c in cohorts),'raw_fail':sum(c['fail'] for c in cohorts)}))

if __name__=='__main__':main()

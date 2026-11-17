"""Preserve each later missing-slot cluster without attributing unobserved causes."""
import argparse,gzip,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--bundle',type=Path,required=True);a=p.parse_args()
base=json.loads((a.bundle/'native-gap-analysis.json').read_text());missing=base['missing'];groups=[]
for row in sorted(missing,key=lambda r:r['release_ns']):
 if not groups or row['release_ns']>max(r['detected_ns'] for r in groups[-1])+50_000_000:groups.append([])
 groups[-1].append(row)
result=[]
for rows in groups:
 lo=min(r['release_ns'] for r in rows);hi=max(r['detected_ns'] for r in rows);samples={}
 for name,radius in [('host-native.jsonl.gz',100_000_000),('host-clock.jsonl.gz',100_000_000),('host-profile.jsonl.gz',1_000_000_000)]:
  values=[]
  with gzip.open(a.run/name,'rt') as stream:
   for line in stream:
    row=json.loads(line)
    if row['wall_ns']>hi+radius:break
    if row['wall_ns']>=lo-radius:values.append(row)
  samples[name]=values
 result.append(dict(missing=rows,first_release_after_initial_s=(lo-base['initial_ns'])/1e9,last_detection_after_initial_s=(hi-base['initial_ns'])/1e9,after_first_fault=lo>base['first_fault_ns'],samples=samples))
assert sum(len(g['missing']) for g in result)==18 and all(g['after_first_fault'] for g in result)
output=dict(status='RECORDED_UNRESOLVED_LATER_NATIVE_GAPS',groups=result,interpretation='Two later clusters: one owner-9 release and 17 owner-0..8 releases. Coarse host samples cannot establish the cause of millisecond gaps. Preserve zero-missed-slot requirement independently of GC/input-expiry diagnosis.')
(a.bundle/'native-gap-context.json').write_text(json.dumps(output,indent=2)+'\n')
print([(len(g['missing']),g['first_release_after_initial_s']) for g in result])

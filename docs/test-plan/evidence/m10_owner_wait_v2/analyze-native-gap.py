"""Preserve the later missing slots separately from the first HV expiry."""
import argparse
import csv
import gzip
import json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--bundle',type=Path,required=True);a=p.parse_args()
read=lambda p:json.loads(p.read_text())
native=read(a.run/'capture/native.json');initial=native['initial'];last=0
with (a.run/'capture/native.csv').open() as stream:
    for row in csv.DictReader(stream):last=int(row['now'])
missing=[]
with (a.run/'capture/native-wall.csv').open() as stream:
    for row in csv.DictReader(stream):
        if not int(row['end_ns']) and int(row['deadline_ns'])<=last:missing.append({k:int(v) for k,v in row.items()})
assert len(missing)==18 and {r['owner'] for r in missing}==set(range(9))
lo=min(r['release_ns'] for r in missing);hi=max(r['detected_ns'] for r in missing)
samples={}
for name,radius in [('host-native.jsonl.gz',100_000_000),('host-clock.jsonl.gz',100_000_000),('host-profile.jsonl.gz',1_000_000_000)]:
    values=[]
    with gzip.open(a.run/name,'rt') as stream:
        for line in stream:
            row=json.loads(line)
            if row['wall_ns']>hi+radius:break
            if row['wall_ns']>=lo-radius:values.append(row)
    samples[name]=values
irq=samples['host-native.jsonl.gz'];begin,end=irq[0],irq[-1]
interrupt_deltas={k:dict(label=v['label'],delta=[n-o for n,o in zip(v['counts'],begin['interrupts'][k]['counts'])])
    for k,v in end['interrupts'].items() if k in begin['interrupts'] and v['counts']!=begin['interrupts'][k]['counts']}
result=dict(status='RECORDED_UNRESOLVED_LATER_NATIVE_GAP',missing=missing,
    first_deadline_after_initial_s=(min(r['deadline_ns'] for r in missing)-initial)/1e9,
    final_deadline_after_initial_s=(max(r['deadline_ns'] for r in missing)-initial)/1e9,
    after_original_hv_fault=True,window_begin_ns=lo,window_end_ns=hi,
    samples=samples,interrupt_deltas=interrupt_deltas,
    interpretation='Two consecutive release slots for owner IDs0..8 were absent after protection had already latched. The50ms IRQ/clock and0.5s process samples do not establish the cause of the millisecond gap. Retain as a separate unresolved observation; a GC improvement cannot waive native timing checks.')
(a.bundle/'native-gap-analysis.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['status','first_deadline_after_initial_s','final_deadline_after_initial_s']}))

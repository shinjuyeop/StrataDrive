"""Reproduce selected original receipt fields around the first GC expiry."""
import argparse
import gzip
import json
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('--run',type=Path,required=True)
p.add_argument('--bundle',type=Path,required=True)
a=p.parse_args()
analysis=json.loads((a.bundle/'first-fault-analysis.json').read_text())
frame=int(analysis['original_first_fault']['held_hv']['sequence'])
selected=[]
with gzip.open(a.run/'capture/trace.jsonl.gz','rt') as stream:
    for line in stream:
        record=json.loads(line);r=record['receipt']
        if frame<=int(r['frame'])<=frame+2:
            authority=r['original_actual']['admitted_actual']
            selected.append(dict(frame=int(r['frame']),normal=authority['normal'],
                state_path=record.get('state_path',r.get('state_path')),
                acquired_begin_ns=r['physics_acquisition_begin_ns'],
                acquired_end_ns=r['physics_acquisition_end_ns'],authority=authority))
        if int(r['frame'])>frame+2:break
assert len(selected)==3
result=dict(scope='original selected fields; no changed timestamps or verdicts',frames=selected)
target=a.bundle/'post-gc-frames.json'
if target.exists():
    assert json.loads(target.read_text())==result,'original selected fields must reproduce exactly'
else:target.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(status='PASS_ORIGINAL_FIELDS',frames=[r['frame'] for r in selected])))

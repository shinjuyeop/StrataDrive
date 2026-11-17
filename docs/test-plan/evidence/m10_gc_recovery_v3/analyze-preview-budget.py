"""Measure original staging cost before the first fault; no acceptance change."""
import argparse
import gzip
import json
from pathlib import Path
import statistics

p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--bundle',type=Path,required=True);a=p.parse_args()
fault=json.loads((a.run/'capture/native-drive-fault.json').read_text())['observed_ns']
rows=[]
with gzip.open(a.run/'capture/trace.jsonl.gz','rt') as stream:
    for line in stream:
        record=json.loads(line);r=record['receipt'];path=record['state_path']
        admitted=int(path['admitted']['wall_ns']);applied=int(r['wall_applied_ns'])
        if applied>=fault:break
        actual=r['original_actual']['admitted_actual']
        if not actual['normal']:continue
        checked=int(actual['command_checked_through_ns'])-5_000_000
        assert admitted<=checked<=applied
        rows.append(dict(frame=int(r['frame']),admitted_to_check_ns=checked-admitted,
                         check_to_applied_ns=applied-checked,admitted_to_applied_ns=applied-admitted))
def quant(key):
    values=sorted(r[key] for r in rows)
    return dict(count=len(values),median_ns=statistics.median(values),p95_ns=statistics.quantiles(values,n=100,method='inclusive')[94],
        p99_ns=statistics.quantiles(values,n=100,method='inclusive')[98],max_ns=values[-1],
        above_250us=sum(v>250_000 for v in values),above_500us=sum(v>500_000 for v in values),above_1ms=sum(v>1_000_000 for v in values))
result=dict(scope='original normal applied frames before first Drive fault; observed costs, not a future execution bound',
    first_fault_ns=fault,metrics={k:quant(k) for k in ('admitted_to_check_ns','check_to_applied_ns','admitted_to_applied_ns')},
    worst_check_to_applied=sorted(rows,key=lambda r:r['check_to_applied_ns'],reverse=True)[:10])
(a.bundle/'preview-budget-analysis.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))

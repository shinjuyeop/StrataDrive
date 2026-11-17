"""Join original GC delegates, HV expiry and native deadlines; post-run only."""
import argparse
import csv
import json
from pathlib import Path
import statistics

p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True)
p.add_argument('--bundle',type=Path,required=True);a=p.parse_args()
read=lambda p:json.loads(p.read_text())
native=read(a.run/'capture/native.json');fault=read(a.run/'capture/native-drive-fault.json')
gc=read(a.bundle/'owner-gc.json');path=read(a.bundle/'path-analysis.json')
assert gc['status']=='PASS_GC_OBSERVATION_ONLY' and not gc['serial']
assert read(a.bundle/'replay.json')['exact'] and read(a.bundle/'drive-fault-replay.json')['equal']
first=fault['observed_ns'] if fault else None
last=None
with (a.run/'capture/native.csv').open() as stream:
    for row in csv.DictReader(stream):last=int(row['now'])
counts={n:dict(eligible=0,missing=0,late=0) for n in ('all','before_first_fault','at_or_after_first_fault')}
missing=[];late=[]
with (a.run/'capture/native-wall.csv').open() as stream:
    for original in csv.DictReader(stream):
        row={k:int(v) for k,v in original.items()}
        if row['deadline_ns']>last:continue
        phase='before_first_fault' if first is None or row['deadline_ns']<first else 'at_or_after_first_fault'
        for label in ('all',phase):
            counts[label]['eligible']+=1
            counts[label]['missing']+=not row['end_ns']
            counts[label]['late']+=row['end_ns']>row['deadline_ns']
        if not row['end_ns']:missing.append(row)
        if row['end_ns']>row['deadline_ns']:late.append(row)
gap=dict(scope='original completed deadline grid; phase split by deadline, no acceptance change',
    initial_ns=native['initial'],last_native_ns=last,first_fault_ns=first,counts=counts,missing=missing,late=late)
(a.bundle/'native-gap-analysis.json').write_text(json.dumps(gap,indent=2)+'\n')
if fault:
    assert fault['fault']==5 and fault['hv_dependency_age_ns']==30_000_000
    hv=fault['held_hv'];cycles=gc['cycles']
    containing=[c for c in cycles if c['begin']['wall_ns']<=first<c['end']['wall_ns']]
    preceding=max((c for c in cycles if c['end']['wall_ns']<first),key=lambda c:c['end']['wall_ns'])
    assert not containing and preceding['completed_frame']+1==hv['sequence']
    dependency_age=first-hv['dependency_ns']
    assert dependency_age>fault['hv_dependency_age_ns']
    report=dict(scope='direct original GC delegates and byte-equal first-fault replay; HV expiry after first parallel GC',
        original_first_fault=fault,first_fault_after_initial_s=(first-native['initial'])/1e9,
        inherited_dependency_age_ns=hv['source_ns']-hv['dependency_ns'],
        held_duration_ns=first-hv['source_ns'],dependency_age_at_fault_ns=dependency_age,
        containing_gc=None,preceding_gc=preceding,periodic_pauses=cycles,
        fault_after_gc_end_ns=first-preceding['end']['wall_ns'],
        held_source_after_gc_end_ns=hv['source_ns']-preceding['end']['wall_ns'],
        all_parallel_collections_below_hv_age=all(c['delta']['wall_ns']<30_000_000 for c in cycles),
        gc_cpu_fraction=[c['delta']['cpu_ns']/c['delta']['wall_ns'] for c in cycles],
        native_deadline_counts=counts,physical_accepted=False)
    (a.bundle/'first-fault-analysis.json').write_text(json.dumps(report,indent=2)+'\n')
renderer=read(a.run/'capture/paired/renderer/result.json')
def quant(values):
    return dict(count=len(values),median=statistics.median(values),
        p95=statistics.quantiles(values,n=100,method='inclusive')[94] if len(values)>1 else values[0],
        maximum=max(values)) if values else None
phases={}
for label in ('before_first_fault','at_or_after_first_fault'):
    rows=[r for r in renderer['inference'] if native['initial']<=r['end_ns']<=path['physical_end_ns'] and
          (first is None or r['end_ns']<first)==(label=='before_first_fault')]
    phases[label]=dict(result_completion_phase=True,scene_result_ms=quant([(r['end_ns']-r['original_acquisition_ns'])/1e6 for r in rows]),
        over_100ms=sum(r['end_ns']-r['original_acquisition_ns']>100_000_000 for r in rows))
(a.bundle/'latency-phases.json').write_text(json.dumps(dict(scope='split by original result completion; protected hold is not normal driving',phases=phases),indent=2)+'\n')
print(json.dumps(dict(native=counts,first_fault_after_initial_s=(first-native['initial'])/1e9 if first else None)))

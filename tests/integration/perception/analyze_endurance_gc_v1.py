"""Join original GC delegates, HV expiry and native deadlines; post-run only."""
import argparse
import csv
import json
from pathlib import Path
import statistics
from audit_owner_gc_v1 import validate,declared_policy,declared_owner_cpus

p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True)
p.add_argument('--bundle',type=Path,required=True);a=p.parse_args()
read=lambda p:json.loads(p.read_text())
native=read(a.run/'capture/native.json');fault=read(a.run/'capture/native-drive-fault.json')
original_gc_audit=read(a.bundle/'owner-gc.json');path=read(a.bundle/'path-analysis.json')
server=read(a.run/'server.json');profile=read(a.run/'capture/owner-gc.json')
serial=declared_policy(server)
gc=dict(cycles=validate(profile,serial,declared_owner_cpus(server)))
# Completed delegate pairs remain diagnostic evidence after an early physical
# stop. The original full-horizon audit failure is preserved, never promoted.
assert not serial
replay_path=a.bundle/'replay.json'
exact_replay=(replay_path.exists() and read(replay_path).get('exact') is True
              and read(a.bundle/'drive-fault-replay.json').get('equal') is True)
if not exact_replay:
    assert read(a.bundle/'disposition.json')['finite_diagnostic_pass'] is False
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
    assert fault['hv_dependency_age_ns']==native['hv_dependency_ns'] in (30_000_000,50_000_000)
    hv=fault['held_hv'];cycles=gc['cycles']
    containing=[c for c in cycles if c['begin']['wall_ns']<=first<c['end']['wall_ns']]
    preceding=max((c for c in cycles if c['end']['wall_ns']<first),key=lambda c:c['end']['wall_ns'],default=None)
    dependency_age=first-hv['dependency_ns']
    if fault['fault']==5:assert dependency_age>fault['hv_dependency_age_ns']
    report=dict(scope='direct original GC delegates and original Drive fault; dependency ages are diagnostic unless fault code is HV expiry',
        exact_replay=exact_replay,
        original_first_fault=fault,first_fault_after_initial_s=(first-native['initial'])/1e9,
        inherited_dependency_age_ns=hv['source_ns']-hv['dependency_ns'],
        held_duration_ns=first-hv['source_ns'],dependency_age_at_fault_ns=dependency_age,
        containing_gc=containing,preceding_gc=preceding,periodic_pauses=cycles,
        fault_after_gc_end_ns=first-preceding['end']['wall_ns'] if preceding else None,
        held_source_after_gc_end_ns=hv['source_ns']-preceding['end']['wall_ns'] if preceding else None,
        all_parallel_collections_below_hv_age=all(c['delta']['wall_ns']<fault['hv_dependency_age_ns'] for c in cycles),
        gc_cpu_fraction=[c['delta']['cpu_ns']/c['delta']['wall_ns'] for c in cycles],
        native_deadline_counts=counts,physical_accepted=False)
    (a.bundle/'first-fault-analysis.json').write_text(json.dumps(report,indent=2)+'\n')
profile=read(a.run/'capture/owner-gc.json')
(a.bundle/'gc-analysis.json').write_text(json.dumps(dict(scope='completed original delegates; partial horizon is not acceptance',original_gc_audit=original_gc_audit,cycles=gc['cycles'],incremental_purge=profile['incremental_purge'],integrity=read(a.bundle/'admission-window.json'),first_fault_ns=first),indent=2)+'\n')
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

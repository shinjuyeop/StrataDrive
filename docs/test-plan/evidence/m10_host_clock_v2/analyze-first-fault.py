"""Join the immutable first Drive fault to original HV/owner and native records."""
import argparse
import csv
import gzip
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/integration/perception'))
from audit_state_path_v1 import hv_origin

p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True)
p.add_argument('--bundle',type=Path,required=True);a=p.parse_args()
def read(path):return json.loads(path.read_text())
def rows(name):
    with (a.run/'capture'/name).open() as stream:
        return [{k:int(v) for k,v in r.items()} for r in csv.DictReader(stream)]
fault=read(a.run/'capture/native-drive-fault.json')
meta=read(a.run/'capture/native.json');native=rows('native.csv');paths=rows('native-state-path.csv')
observed=fault['observed_ns'];held=fault['held_hv'];call=next(r for r in native if r['now']==observed)
path=next(r for r in paths if r['service_begin_ns']==observed)
assert fault['fault']==5 and fault['hv_dependency_age_ns']==30_000_000
selected=[];origin=None;incoming=None
with gzip.open(a.run/'capture/trace.jsonl.gz','rt') as stream:
    for line in stream:
        record=json.loads(line);receipt=record['receipt'];at=int(receipt['physics_acquisition_begin_ns'])
        if at>observed+200_000_000:break
        derived=hv_origin(receipt)
        if derived['source_ns']==held['source_ns']:
            assert derived['dependency_ns']==held['dependency_ns'];origin=derived
        if derived['source_ns']==call['hv_source']:
            assert derived['dependency_ns']==call['hv_dependency'];incoming=derived
        if abs(at-observed)<=40_000_000:selected.append(record)
assert origin is not None and incoming is not None
assert held['sequence']==origin['source_frame'] and path['frame']==incoming['source_frame']
analysis=read(a.bundle/'path-analysis.json')
owner={r['frame']:r for r in analysis['owner_window']}
assert origin['source_frame'] in owner and incoming['source_frame'] in owner
eligible=[r for r in rows('native-wall.csv') if r['deadline_ns']<=native[-1]['now']]
before=[r for r in eligible if r['deadline_ns']<=observed]
def slot_summary(values):return dict(eligible=len(values),missing=sum(not r['end_ns'] for r in values),late=sum(r['end_ns']>r['deadline_ns'] for r in values))
host=read(a.bundle/'host-clock-audit.json');clock=[]
with gzip.open(a.run/'host-clock.jsonl.gz','rt') as stream:
    for line in stream:
        sample=json.loads(line)
        if abs(sample['wall_ns']-observed)<=100_000_000:clock.append(sample)
result=dict(status='PASS_ORIGINAL_FAILURE_EXPLAINED',scope='post-run timestamp decomposition; not causal kernel tracing or changed acceptance',
    original_first_fault=fault,first_fault_after_initial_ms=(observed-meta['initial'])/1e6,
    first_protection_after_initial_ms=(next(r['now'] for r in native if r['protection'])-meta['initial'])/1e6,
    held_origin=origin,incoming_origin=incoming,
    held_dependency_age_ms=(observed-held['dependency_ns'])/1e6,
    held_dependency_at_acquisition_ms=(held['source_ns']-held['dependency_ns'])/1e6,
    held_source_age_ms=(observed-held['source_ns'])/1e6,
    incoming_dependency_age_ms=(observed-incoming['dependency_ns'])/1e6,
    held_owner=owner[origin['source_frame']],incoming_owner=owner[incoming['source_frame']],
    source_receipts=selected,native_call=call,native_path=path,
    native_slots_before_fault=slot_summary(before),native_slots_all=slot_summary(eligible),
    monitor=read(a.bundle/'monitor-timing.json')['wake_delay_ns'],clock_window=clock,
    qualified_thermal_delta=host['thermal_delta'],all_cores_low_samples=len(host['all_cores_at_most_850mhz_wall_ns']),
    maximum_cpu_temperature_millicelsius=host['maximum_cpu_temperature_millicelsius'],
    exact_original_replay=read(a.bundle/'replay.json')['exact'],exact_first_fault_replay=read(a.bundle/'drive-fault-replay.json')['equal'],
    interpretation='Held HV dependency expires before incoming replacement. Physical tick wall minus CPU and the next complete-to-admitted gap consume freshness, despite no observed thermal counter increase or all-core low-clock sample. These records do not distinguish task wait, scheduler delay, physics-worker wait, RPC or gate eligibility.',
    next_diagnostic='Bounded owner pump reason/wait and thread scheduling observations; retain original HV30ms and source clocks. Do not change freshness checks or treat cap70 as accepted.')
assert result['exact_original_replay'] and result['exact_first_fault_replay']
(a.bundle/'first-fault-analysis.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['first_fault_after_initial_ms','held_dependency_age_ms',
    'held_dependency_at_acquisition_ms','held_source_age_ms','incoming_dependency_age_ms','native_slots_before_fault','native_slots_all']}))

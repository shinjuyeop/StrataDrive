"""Join original HV expiry to the directly observed outside-pump pause."""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/integration/perception'))
from audit_state_path_v1 import hv_origin
from audit_owner_wait_v1 import stamp,delta,validate
p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--bundle',type=Path,required=True);a=p.parse_args()
read=lambda p:json.loads(p.read_text())
fault=read(a.run/'capture/native-drive-fault.json');native=read(a.run/'capture/native.json')
observed=fault['observed_ns'];held=fault['held_hv'];call=None;first_protection=None;last=0
with (a.run/'capture/native.csv').open() as stream:
    for row in csv.DictReader(stream):
        now=int(row['now']);last=now
        if now==observed:call={k:int(v) for k,v in row.items()}
        if first_protection is None and int(row['protection']):first_protection=now
assert call is not None and fault['fault']==5
wait=read(a.bundle/'owner-wait.json');selected_frames={r['frame'] for r in wait['worst_outside'][:5]}
window=[];selected=[];origin=None
with gzip.open(a.run/'capture/trace.jsonl.gz','rt') as stream:
    for line in stream:
        record=json.loads(line);receipt=record['receipt'];end=int(receipt['physics_acquisition_end_ns'])
        if abs(end-observed)<=60_000_000:window.append(record)
        if int(receipt['frame']) in selected_frames:
            checked=validate(record['state_path']);outside=record['state_path']['owner_wait']['outside']
            begin,finish=stamp(outside['longest_begin']),stamp(outside['longest_end'])
            selected.append(dict(frame=int(receipt['frame']),ticket=int(receipt['ticket']),
                normal=receipt['original_actual']['native']['normal'],begin=begin,end=finish,delta=delta(begin,finish),
                contains_first_fault=begin['wall_ns']<=observed<=finish['wall_ns'],
                max_rpc_ns=int(record['state_path']['max_rpc_ns']),owner_spans=checked['spans'],original=record))
        if int(receipt['physics_acquisition_begin_ns'])==held['source_ns']:
            origin=hv_origin(receipt)
assert origin and origin['dependency_ns']==held['dependency_ns'] and origin['source_frame']==held['sequence']
pause=next(r for r in selected if r['contains_first_fault'])
assert pause['frame']==held['sequence']+1
periodic=[r for r in selected if (r['frame']-pause['frame'])%12220==0]
assert len(periodic)==4 and [b['frame']-a['frame'] for a,b in zip(periodic,periodic[1:])]==[12220]*3
slots={k:dict(eligible=0,missing=0,late=0) for k in ['before_fault','all']}
with (a.run/'capture/native-wall.csv').open() as stream:
    for row in csv.DictReader(stream):
        deadline,end=int(row['deadline_ns']),int(row['end_ns'])
        for key,limit in [('before_fault',observed),('all',last)]:
            if deadline<=limit:
                slots[key]['eligible']+=1;slots[key]['missing']+=not end;slots[key]['late']+=end>deadline
engine=Path('/d/shin/stratadrive-tools/UnrealEngine_4.26/Engine')
config=engine/'Config/BaseEngine.ini';text=config.read_text()
assert 'gc.TimeBetweenPurgingPendingKillObjects=61.1' in text and 'gc.AllowParallelGC=True' in text
gc_defaults=dict(path=str(config),sha256=hashlib.sha256(config.read_bytes()).hexdigest(),period_seconds=61.1,parallel=True,
    scope='configured engine defaults; V2 did not record direct runtime GC delegate brackets')
clock=read(a.bundle/'host-clock-audit.json')
result=dict(status='PASS_ORIGINAL_FAILURE_LOCALIZED',original_first_fault=fault,
    fault_after_start_s=(observed-native['initial'])/1e9,
    first_protection_after_start_s=(first_protection-native['initial'])/1e9,
    dependency_age_ms=(observed-held['dependency_ns'])/1e6,
    inherited_dependency_ms=(held['source_ns']-held['dependency_ns'])/1e6,
    held_source_age_ms=(observed-held['source_ns'])/1e6,
    held_origin=origin,original_native_call=call,pause=pause,periodic_pauses=periodic,
    other_large_outside_pauses=[r for r in selected if r not in periodic],original_window=window,
    native_slots=slots,configured_gc_defaults=gc_defaults,
    thermal_counter_increase=any(clock['thermal_delta'].values()),all_core_low_samples=len(clock['all_cores_at_most_850mhz_wall_ns']),
    exact_replay=read(a.bundle/'replay.json')['exact'],exact_first_fault=read(a.bundle/'drive-fault-replay.json')['equal'],
    interpretation='Expiry occurred inside a22.427ms pause after the preceding receipt completed and before the next pump. That pause used3.703ms thread CPU with3 voluntary and0 involuntary switches. Four large pauses recur every12220 physical frames, exactly61.1s of model time, matching configured GC defaults. Strong GC correlation, not a direct GC-tagged causal proof.',
    next_candidate='Record direct GC delegate brackets and test owner-only serial GC; retain61.1s collection period, original HV30ms, source stamps and check order. Keep every original FAIL.')
assert result['exact_replay'] and result['exact_first_fault']
(a.bundle/'first-fault-analysis.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['status','fault_after_start_s','dependency_age_ms','native_slots','thermal_counter_increase']}))

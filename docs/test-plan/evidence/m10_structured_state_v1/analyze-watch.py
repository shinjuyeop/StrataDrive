"""Post-run watchdog fault window and original conversion-check observations."""
import argparse
import csv
import gzip
import json
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True)
p.add_argument('--output',type=Path,required=True);a=p.parse_args()
read=lambda name:json.loads((a.run/name).read_text())
def csv_rows(name):
    with (a.run/name).open() as stream:
        return [{k:int(v) for k,v in row.items()} for row in csv.DictReader(stream)]

meta=read('capture/native.json');initial=meta['initial']
native=csv_rows('capture/native.csv');first=next(r for r in native if r['protection'])
fault=first['now'];stop=native[-1]['now']
watch=csv_rows('capture/native-wall.csv')
eligible=[r for r in watch if r['deadline_ns']<=stop]
violations=[r for r in eligible if not r['end_ns'] or r['end_ns']>r['deadline_ns']]
window=[dict(r,release_after_initial_ms=(r['release_ns']-initial)/1e6,
    start_after_initial_ms=(r['start_ns']-initial)/1e6 if r['start_ns'] else None,
    wake_delay_ns=r['start_ns']-r['release_ns'] if r['start_ns'] else None)
    for r in watch if r['owner']==9 and abs(r['release_ns']-fault)<16_000_000]
calls=[dict(r,wake_delay_ns=r['read_begin_ns']-r['wake_ns'],
    wall_ns=r['proof_publish_ns']-r['read_begin_ns'],cpu_ns=r['cpu_end_ns']-r['cpu_begin_ns'])
    for r in csv_rows('capture/native-state-path.csv') if abs(r['wake_ns']-fault)<16_000_000]
events=read('capture/events.json');check=next(e for e in events if e['op']=='structured_json_check')
start=next(e for e in events if e['op']=='wall_start')
describes=[e['response'] for e in events if e['op']=='describe' and 'structured_direct_requests' in e['response']]
clocks=[]
with gzip.open(a.run/'host-clock.jsonl.gz','rt') as stream:
    for line in stream:
        r=json.loads(line)
        if initial-100_000_000<=r['wall_ns']<=fault+150_000_000:clocks.append(r)
result=dict(scope='post-run original observations; incomplete physical case, no performance acceptance',
    first_fault=meta['first_fault'],initial_ns=initial,first_protection_ns=fault,
    native_owner=meta['owner'],native_io=meta['io'],monitor_policy_in_live_case='not recorded',
    eligible_slots=len(eligible),violations=violations,monitor_window=window,native_call_window=calls,
    check_before_wall_start=check['wall_ns']<start['wall_ns'],structured_json_check=check['response'],
    last_describe_counts={k:describes[-1][k] for k in ('wall_frames','structured_state','structured_direct_requests','structured_text_fallback_requests')},
    near_initial_clocks=clocks)
a.output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('monitor_window','native_call_window','near_initial_clocks')}))

"""Post-run native/IRQ correlation; not a kernel scheduling causal trace."""
import argparse
import csv
import gzip
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/integration/perception'))
from audit_state_path_v1 import quant
p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
def read(name):return json.loads((a.run/name).read_text())
def rows(name):
    with (a.run/name).open() as f:return [{k:int(v) for k,v in r.items()} for r in csv.DictReader(f)]
def compressed(name):
    with gzip.open(a.run/name,'rt') as f:return [json.loads(line) for line in f]
monitor=rows('capture/native-monitor.csv');native=rows('capture/native-state-path.csv')
meta=read('capture/native.json');host=compressed('host-native.jsonl.gz');clocks=compressed('host-clock.jsonl.gz')
watch=rows('capture/native-wall.csv');control=rows('capture/native.csv')
first_fault=next((r['now'] for r in control if r['protection']),None)
stop=control[-1]['now'];eligible=[r for r in watch if r['deadline_ns']<=stop]
anchors=sorted(monitor,key=lambda r:r['wake_ns']-r['release_ns'],reverse=True)[:12]
if first_fault:
    nearby=[r for r in monitor if abs(r['wake_ns']-first_fault)<20_000_000]
    anchors+=nearby
anchors={r['release_ns']:r for r in anchors}
windows=[]
for r in anchors.values():
    before=[s for s in host if s['end_ns']<=r['release_ns']]
    after=[s for s in host if s['wall_ns']>=r['wake_ns']]
    item=dict(monitor=r,release_after_initial_ms=(r['release_ns']-meta['initial'])/1e6,
        wake_delay_ns=r['wake_ns']-r['release_ns'],native_calls=[n for n in native if abs(n['wake_ns']-r['wake_ns'])<=5_000_000])
    if before and after:
        x,y=before[-1],after[0];changes={}
        for key,old in x['interrupts'].items():
            new=y['interrupts'].get(key)
            if new and new['label']==old['label']:
                delta=[n-o for o,n in zip(old['counts'],new['counts'])]
                if any(delta):changes[key]=dict(label=old['label'],counts_cpu1_cpu9=delta)
        old_threads={t['pid']:t for t in x['kernel_threads']};threads=[]
        for new in y['kernel_threads']:
            old=old_threads.get(new['pid'])
            if old and old['start_ticks']==new['start_ticks']:
                threads.append(dict(pid=new['pid'],comm=new['comm'],runtime_delta_ns=new['schedstat'][0]-old['schedstat'][0],
                    dispatch_delta=new['schedstat'][2]-old['schedstat'][2],policy=new['scheduling_policy'],rt_priority=new['rt_priority']))
        item['bracket']=dict(before_wall_ns=x['wall_ns'],before_end_ns=x['end_ns'],after_wall_ns=y['wall_ns'],after_end_ns=y['end_ns'],
            interrupt_deltas=changes,kernel_thread_deltas=threads)
        item['clocks']=[s for s in clocks if x['wall_ns']<=s['wall_ns']<=y['end_ns']]
    windows.append(item)
summary=dict(scope='post-run sequential50ms correlation; cannot establish exact preemption/timer/firmware cause',
    interrupt_limit='V1 single pread retained only the first17 IRQ rows; NVIDIA/local-timer and later rows are absent. Zero recorded deltas cannot rule out IRQ activity. See interrupt-read-correction.json.',
    initial_ns=meta['initial'],first_fault=meta['first_fault'],first_protection_ns=first_fault,
    monitor_thread=read('capture/native-monitor.json')['thread'],native_thread=meta['owner'],
    eligible_slots=len(eligible),missing=[r for r in eligible if not r['end_ns']],late=[r for r in eligible if r['end_ns']>r['deadline_ns']],
    by_wake_cpu={str(cpu):quant(r['wake_ns']-r['release_ns'] for r in monitor if r['wake_cpu']==cpu) for cpu in (1,9)},
    host_observer=read('host-native-summary.json'),windows=sorted(windows,key=lambda r:r['monitor']['release_ns']))
a.output.write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='windows'}))

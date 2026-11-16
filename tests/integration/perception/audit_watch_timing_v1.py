"""Join diagnostic monitor records to unchanged original execution-watch slots."""
import argparse
import csv
import json
from pathlib import Path
from audit_state_path_v1 import quant


def validate(meta, rows, watch, initial, horizon):
    first=initial+1_000_000
    if meta['first_release_ns']!=first or meta['last_release_ns']!=first+horizon:
        raise ValueError('original watch origin and horizon')
    if meta['overflow'] or meta['count']!=len(rows) or meta['capacity']!=horizon//2_000_000+1:
        raise ValueError('complete bounded monitor trace')
    thread=meta['thread']
    if thread['policy']!=1 or thread['priority']!=18 or thread['allowed_cpus']!=[1,9] or thread['tid']<=0:
        raise ValueError('declared monitor thread identity')
    completed={r['release_ns']:r for r in watch if r['owner']==9 and r['end_ns']}
    if len(completed)!=len(rows) or not rows:
        raise ValueError('one record for every original completed monitor slot')
    previous=None
    for r in rows:
        slot=completed.get(r['release_ns'])
        if not slot or slot['start_ns']!=r['wake_ns'] or slot['end_ns']!=r['job_end_ns']:
            raise ValueError('original monitor start/end identity')
        if not (r['sleep_begin_ns']<=r['wake_ns']<=r['job_end_ns']<=r['poll_end_ns']<=r['grid_now_ns']):
            raise ValueError('ordered monitor observation')
        if r['wake_ns']<r['release_ns'] or r['next_release_ns']!=first+((r['grid_now_ns']-first)//2_000_000+1)*2_000_000:
            raise ValueError('original absolute wake and no catch-up grid')
        if any(r[k] not in thread['allowed_cpus'] for k in ('sleep_cpu','wake_cpu','end_cpu')):
            raise ValueError('actual observed monitor CPU')
        if r['begin_error'] or r['end_error']:
            raise ValueError('monitor sampling error')
        for suffix in ('cpu_ns','voluntary','involuntary','minor_faults'):
            if r['begin_'+suffix]>r['end_'+suffix] or (previous and r['begin_'+suffix]<previous['end_'+suffix]):
                raise ValueError('monotonic thread counters')
        if previous and (r['release_ns']!=previous['next_release_ns'] or r['sleep_begin_ns']<previous['grid_now_ns']):
            raise ValueError('original consecutive requested wakes')
        previous=r
    return dict(status='PASS_MONITOR_DIAGNOSTIC_INTEGRITY',scope='diagnostic consistency only; original physical and timing verdicts remain required',
        records=len(rows),thread=thread,native_perception_accepted=False,
        wake_delay_ns=quant(r['wake_ns']-r['release_ns'] for r in rows),
        watch_body_ns=quant(r['job_end_ns']-r['wake_ns'] for r in rows),
        thread_cpu_ns=quant(r['end_cpu_ns']-r['begin_cpu_ns'] for r in rows),
        after_body_to_next_grid_ns=quant(r['grid_now_ns']-r['job_end_ns'] for r in rows),
        sleep_migrations=sum(r['sleep_cpu']!=r['wake_cpu'] for r in rows),
        body_migrations=sum(r['wake_cpu']!=r['end_cpu'] for r in rows),
        body_involuntary_switches=sum(r['end_involuntary']-r['begin_involuntary'] for r in rows),
        body_minor_faults=sum(r['end_minor_faults']-r['begin_minor_faults'] for r in rows),
        wakes_over_500us=[r for r in rows if r['wake_ns']-r['release_ns']>500_000])


def audit(run):
    def read(name):return json.loads((run/'capture'/name).read_text())
    def csv_read(name):
        with (run/'capture'/name).open() as stream:
            return [{k:int(v) for k,v in r.items()} for r in csv.DictReader(stream)]
    native=read('native.json')
    return validate(read('native-monitor.json'),csv_read('native-monitor.csv'),csv_read('native-wall.csv'),
                    native['initial'],native['diagnostic_horizon_ns'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    try:result=audit(a.run)
    except Exception as error:result=dict(status='FAIL',error=str(error))
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='wakes_over_500us'}))
    raise SystemExit(0 if result['status']=='PASS_MONITOR_DIAGNOSTIC_INTEGRITY' else 1)

"""Verify the declared host cap and summarize qualified per-core observations."""
import argparse
import csv
import gzip
import json
from pathlib import Path

CAP='/sys/devices/system/cpu/intel_pstate/max_perf_pct'
MIN='/sys/devices/system/cpu/intel_pstate/min_perf_pct'
TURBO='/sys/devices/system/cpu/intel_pstate/no_turbo'


def validate(samples, initial, end, expected_cpus=range(16)):
    if end<=initial or len(samples)<2:raise ValueError('bounded physical interval and observations')
    if any(b['wall_ns']<=a['wall_ns'] for a,b in zip(samples,samples[1:])):raise ValueError('monotonic observations')
    if samples[0]['end_ns']>initial or samples[-1]['wall_ns']<end:raise ValueError('physical span not bracketed')
    before=[s for s in samples if s['end_ns']<=initial][-1]
    after=[s for s in samples if s['wall_ns']>=end][0]
    rows=[s for s in samples if before['wall_ns']<=s['wall_ns']<=after['wall_ns']]
    names=[f'/sys/devices/system/cpu/cpu{cpu}/thermal_throttle/{counter}'
           for cpu in expected_cpus for counter in ('core_throttle_count','package_throttle_count')]
    frequencies=[f'/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_cur_freq' for cpu in expected_cpus]
    for row in rows:
        if row['end_ns']<row['wall_ns'] or row.get('errors'):raise ValueError('host counter read errors')
        values=row['values']
        if (values.get(CAP),values.get(MIN),values.get(TURBO))!=(70,16,0):raise ValueError('declared boost lease not continuously observed')
        if any(name not in values for name in names+frequencies):raise ValueError('missing per-CPU counter')
    for a,b in zip(rows,rows[1:]):
        if any(b['values'][name]<a['values'][name] for name in names):raise ValueError('thermal counter regression')
    gaps=[b['wall_ns']-a['wall_ns'] for a,b in zip(rows,rows[1:])]
    if max(gaps)>200_000_000:raise ValueError('observation gap exceeds200ms; cap coverage unavailable')
    return dict(status='PASS_HOST_OBSERVATION_ONLY',scope='50ms sequential sysfs correlation; not causal attribution or continuous hardware tracing',
        samples=len(rows),maximum_observation_gap_ns=max(gaps),
        thermal_delta={name:after['values'][name]-before['values'][name] for name in names},
        all_cores_at_most_850mhz_wall_ns=[r['wall_ns'] for r in rows if all(r['values'][n]<=850000 for n in frequencies)],
        maximum_cpu_temperature_millicelsius=max(v for r in rows for k,v in r['values'].items() if '/temp' in k and k.endswith('_input')))


def audit(run):
    initial=json.loads((run/'capture/native.json').read_text())['initial']
    with (run/'capture/native.csv').open() as f:end=int(list(csv.DictReader(f))[-1]['now'])
    with gzip.open(run/'host-clock.jsonl.gz','rt') as f:samples=[json.loads(line) for line in f]
    return validate(samples,initial,end)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:result=audit(a.run)
    except Exception as error:result=dict(status='FAIL',error=str(error))
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    raise SystemExit(0 if result['status']=='PASS_HOST_OBSERVATION_ONLY' else 1)

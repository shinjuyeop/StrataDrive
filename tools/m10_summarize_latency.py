"""Reproducible diagnostic latency and optimistic wall availability.

This is descriptive, not an acceptance gate. It deliberately labels the interval
union as an upper bound: original source/state age and complete-scene admission
can only reduce it. No new timestamp, grace period, or control input is created.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics

LIFETIME_NS = 100_000_000


def distribution(values):
    values = sorted(values)
    if not values:
        return dict(count=0)
    return dict(count=len(values), median_ms=statistics.median(values)/1e6,
                p95_ms=values[math.ceil(.95*len(values))-1]/1e6,
                max_ms=values[-1]/1e6)


def coverage(rows, start, stop):
    if not 0 < start < stop:
        raise ValueError('explicit original wall observation window')
    intervals = []
    for row in rows:
        if 'error' in row:
            continue
        acquired, callback, completed = (row[k] for k in
            ('original_acquisition_ns', 'callback_ns', 'end_ns'))
        if not all(type(x) is int for x in (acquired,callback,completed)) or not 0 < acquired <= callback <= completed:
            raise ValueError('original scene/callback/completion order')
        begin = max(start, completed)
        end = min(stop, acquired+LIFETIME_NS, callback+LIFETIME_NS)
        if begin < end:
            intervals.append((begin,end))
    merged = []
    for begin,end in sorted(intervals):
        if merged and begin <= merged[-1][1]:
            merged[-1][1] = max(end,merged[-1][1])
        else:
            merged.append([begin,end])
    previous=start;gaps=[]
    for begin,end in merged:
        gaps.append(begin-previous)
        previous=end
    gaps.append(stop-previous)
    available=sum(end-begin for begin,end in merged)
    return dict(scope='upper bound ignoring original source/state/fidelity gates',
        start_ns=start,stop_ns=stop,available_ns=available,duration_ns=stop-start,
        fraction=available/(stop-start),valid_intervals=len(intervals),merged_intervals=len(merged),
        maximum_unavailable_gap_ms=max(gaps)/1e6,
        control_acceptance_proven=False)


def summarize(run, output):
    if output.exists():
        raise ValueError('preserve existing diagnostic result')
    paths = dict(renderer=run/'capture/paired/renderer/result.json',
                 native=run/'capture/native.json')
    reports = {k:json.loads(p.read_text()) for k,p in paths.items()}
    renderer,native = reports['renderer'],reports['native']
    seconds = renderer['endurance_seconds']
    if seconds not in (30,300):
        raise ValueError('declared endurance duration')
    rows=renderer['inference']; good=[r for r in rows if 'error' not in r]
    start=native['initial'];stop=start+seconds*1_000_000_000
    values = dict(
        scene_to_result=[r['end_ns']-r['original_acquisition_ns'] for r in good],
        scene_to_callback=[r['callback_ns']-r['original_acquisition_ns'] for r in good],
        callback_to_result=[r['end_ns']-r['callback_ns'] for r in good],
        worker_queue=[r['begin_ns']-r['callback_ns'] for r in good],
        preprocess=[r['preprocess_ns'] for r in good],
        inference=[r['inference_ns'] for r in good],
        worker_cpu=[r['thread_cpu_ns'] for r in good],
        completion_spacing=[b['end_ns']-a['end_ns'] for a,b in zip(good,good[1:])])
    if any(v<0 for group in values.values() for v in group):
        raise ValueError('nonnegative measured durations and ordered completions')
    result=dict(schema='m10-diagnostic-latency-summary-v1',
        raw=len(renderer['raw']),inferences=len(rows),successful_inferences=len(good),
        statistics={k:distribution(v) for k,v in values.items()},
        results_scene_age_ge_100ms=sum(v>=LIFETIME_NS for v in values['scene_to_result']),
        errors=renderer['errors']+renderer['cleanup_errors']+[r['error'] for r in rows if 'error' in r],
        native_first_fault=native['first_fault'],
        optimistic_wall_coverage=coverage(rows,start,stop),
        actual_control_admissions=sum(r['accepted_for_control'] is True for r in rows),
        raw_rate_per_second=len(renderer['raw'])/seconds,
        percentile_method='nearest rank; ceil(.95*n)-1 in sorted samples',
        inputs={k:dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for k,p in paths.items()},
        summarizer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('raw','inferences','statistics','results_scene_age_ge_100ms','optimistic_wall_coverage','actual_control_admissions')}))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();summarize(a.run.resolve(),a.output.resolve())

"""Post-run diagnosis only; never changes frozen acceptance or source clocks."""
import argparse
import csv
import gzip
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'tests/integration/perception'))
from audit_state_path_v1 import join, hv_origin, hv_join, quant as quant_ns

p = argparse.ArgumentParser()
p.add_argument('--run', type=Path, required=True)
p.add_argument('--bundle', type=Path, required=True)
a = p.parse_args()
read = lambda path: json.loads(path.read_text())
native = read(a.run/'capture/native.json')
with (a.run/'capture/native-state-path.csv').open() as stream:
    paths = {int(r['frame']): {k: int(v) for k, v in r.items()}
             for r in csv.DictReader(stream) if int(r['frame'])}
rows = []
origins = {}
previous = None
with gzip.open(a.run/'capture/trace.jsonl.gz', 'rt') as stream:
    for line in stream:
        record = json.loads(line)
        receipt = record['receipt']
        path = record.get('state_path', receipt.get('state_path'))
        row = join(receipt, paths[int(receipt['frame'])], path)
        origins[int(receipt['work_end_ns'])] = hv_origin(receipt)
        row['end_ns'] = int(receipt['physics_acquisition_end_ns'])
        row['apply_ns'] = int(receipt['wall_applied_ns'])
        row['apply_to_acquisition_end_ns'] = row['end_ns']-row['apply_ns']
        row['preceding_source_end_gap_ns'] = row['end_ns']-previous['end_ns'] if previous else None
        row['preceding_complete_to_admitted_ns'] = (
            int(path['admitted']['wall_ns'])-previous['complete_ns'] if previous else None)
        row['complete_ns'] = int(path['complete']['wall_ns'])
        rows.append(row)
        previous = row
start = native['initial']
end = rows[-1]['end_ns']
with (a.run/'capture/native.csv').open() as stream:
    native_rows = [{k: int(v) for k, v in r.items()} for r in csv.DictReader(stream)]
fault = next((r['now'] for r in native_rows if r['protection']), None)
for sample in native_rows:
    hv_join(sample, origins)
worst = max(rows[1:], key=lambda r: r['preceding_source_end_gap_ns'])
anchor = fault or worst['end_ns']
reason = 'first native protection' if fault else 'largest original acquisition-end gap'

def quant(values):
    values = list(values)
    return dict(count=len(values), median=statistics.median(values),
                p95=statistics.quantiles(values, n=100, method='inclusive')[94] if len(values)>1 else values[0],
                maximum=max(values)) if values else None

def clock_row(row):
    values = row['values']
    freq = [v for k, v in values.items() if k.endswith('/scaling_cur_freq')]
    return dict(offset_ms=(row['wall_ns']-anchor)/1e6,
                bracket_ms=(row['end_ns']-row['wall_ns'])/1e6,
                min_mhz=min(freq)/1000 if freq else None,
                max_mhz=max(freq)/1000 if freq else None,
                low_cores=sum(v<=850_000 for v in freq),
                hottest_c=max((v/1000 for k, v in values.items() if '/temp' in k), default=None),
                thermal={k.rsplit('/', 1)[-1]: v for k, v in values.items() if 'thermal_throttle' in k},
                errors=row['errors'])

with gzip.open(a.run/'host-clock.jsonl.gz', 'rt') as stream:
    clocks = [json.loads(line) for line in stream]
physical = [r for r in clocks if start<=r['wall_ns']<=end]
clock_summary = read(a.run/'host-clock-summary.json')
clock_stats = dict(samples=len(physical),
    sample_interval_ms=quant((b['wall_ns']-a['wall_ns'])/1e6 for a, b in zip(physical, physical[1:])),
    sample_cost_ms=quant((r['end_ns']-r['wall_ns'])/1e6 for r in physical),
    hottest_c=max((clock_row(r)['hottest_c'] for r in physical), default=None),
    all_cpus_at_most_850mhz=sum(clock_row(r)['low_cores']==16 for r in physical),
    observer_average_cores=clock_summary['monitor_cpu_seconds']/clock_summary['wall_seconds'],
    read_error_samples=clock_summary['read_error_samples'],
    unavailable=clock_summary['unavailable'])
if physical:
    clock_stats['thermal_delta'] = {k.rsplit('/', 1)[-1]: v-physical[0]['values'].get(k, v)
        for k, v in physical[-1]['values'].items() if 'thermal_throttle' in k}
episodes = []
for index, sample in enumerate(physical):
    if clock_row(sample)['low_cores']!=16:
        continue
    if not episodes or index!=episodes[-1][-1]+1:
        episodes.append([])
    episodes[-1].append(index)
renderer = read(a.run/'capture/paired/renderer/result.json')
low_clock_episodes = []
for indices in episodes:
    lo = physical[max(0, indices[0]-1)]['wall_ns']
    hi = physical[min(len(physical)-1, indices[-1]+1)]['end_ns']
    selected = [r for r in rows if lo<=r['end_ns']<=hi]
    first = physical[max(0, indices[0]-1)]['values']
    last = physical[min(len(physical)-1, indices[-1]+1)]['values']
    low_clock_episodes.append(dict(first_sample_after_initial_s=(physical[indices[0]]['wall_ns']-start)/1e9,
        last_sample_after_initial_s=(physical[indices[-1]]['wall_ns']-start)/1e9,
        samples=len(indices), bracket_begin_ns=lo, bracket_end_ns=hi,
        thermal_delta={k.rsplit('/', 1)[-1]: v-first.get(k, v) for k, v in last.items() if 'thermal_throttle' in k},
        owner_intervals=len(selected),
        source_gap_ns=quant_ns(r['preceding_source_end_gap_ns'] for r in selected if r['preceding_source_end_gap_ns'] is not None),
        apply_to_acquisition_end_ns=quant_ns(r['apply_to_acquisition_end_ns'] for r in selected),
        physics_wall_ns=quant_ns(r['owner_spans']['before_tick_to_after_tick']['wall_ns'] for r in selected),
        physics_cpu_ns=quant_ns(r['owner_spans']['before_tick_to_after_tick']['cpu_ns'] for r in selected),
        result_latency_ms=quant((r['end_ns']-r['original_acquisition_ns'])/1e6
            for r in renderer['inference'] if lo<=r['end_ns']<=hi),
        clock_window=[clock_row(r) for r in physical if lo<=r['wall_ns']<=hi]))
report = dict(scope='post-run diagnostic correlation, not a change to frozen acceptance; wall minus thread CPU cannot distinguish scheduling, blocking or parallel physics work',
    initial_ns=start, physical_end_ns=end, physical_seconds=(end-start)/1e9,
    anchor_ns=anchor, anchor_reason=reason, first_protection_ns=fault,
    source_end_gap_ns=quant(r['preceding_source_end_gap_ns'] for r in rows[1:]),
    largest_source_gaps=sorted(rows[1:], key=lambda r: r['preceding_source_end_gap_ns'], reverse=True)[:12],
    owner_window=[r for r in rows if abs(r['end_ns']-anchor)<=100_000_000],
    fast_clock=clock_stats,
    low_clock_episodes=low_clock_episodes,
    clock_window=[clock_row(r) for r in clocks if abs(r['wall_ns']-anchor)<=2_000_000_000])
report['hv_original_identity_calls_checked'] = len(native_rows)
normal = [r for r in rows if r['normal']]
report['normal_owner_spans'] = {span: {metric: quant_ns(r['owner_spans'][span][metric] for r in normal)
    for metric in ('wall_ns', 'cpu_ns', 'wall_minus_cpu_ns')} for span in rows[0]['owner_spans']}
report['normal_handoff'] = {key: quant_ns(r[key] for r in normal) for key in (
    'acquisition_to_publication_ns', 'publication_to_native_upper_ns', 'acquisition_to_native_ns',
    'native_service_ns', 'native_cpu_ns', 'max_pump_gap_ns', 'max_rpc_ns')}
(a.bundle/'path-analysis.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({k: v for k, v in report.items() if k not in ('largest_source_gaps', 'owner_window', 'clock_window')}, indent=2))

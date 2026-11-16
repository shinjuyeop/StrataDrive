"""Post-run first-fault measurements; does not alter the frozen verdict."""
import argparse
import csv
import gzip
import json
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--run', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
read = lambda path: json.loads(path.read_text())
meta = read(a.run/'capture/native.json')
with (a.run/'capture/native.csv').open() as stream:
    native = list(csv.DictReader(stream))
first = next(row for row in native if int(row['protection']))
fault = int(first['now'])
stop = int(native[-1]['now'])
del native
with (a.run/'capture/native-wall.csv').open() as stream:
    jobs = [{k: int(v) for k, v in row.items()} for row in csv.DictReader(stream)]
complete = [row for row in jobs if row['deadline_ns'] <= stop]
before = [row for row in complete if row['deadline_ns'] <= fault]
def slots(rows):
    return dict(eligible=len(rows), missing=sum(not r['end_ns'] for r in rows),
                late=sum(r['end_ns'] > r['deadline_ns'] for r in rows),
                max_body_ns=max(r['end_ns']-r['start_ns'] for r in rows if r['end_ns']))
window = []
previous = None
with gzip.open(a.run/'capture/trace.jsonl.gz', 'rt') as stream:
    for line in stream:
        receipt = json.loads(line)['receipt']
        end = int(receipt['physics_acquisition_end_ns'])
        if end > fault+100_000_000:
            break
        if end > fault-100_000_000:
            item = {k: int(receipt[k]) for k in ('ticket', 'wall_applied_ns',
                    'physics_acquisition_begin_ns', 'physics_acquisition_end_ns')}
            item.update(elapsed_ms=(end-meta['initial'])/1e6,
                source_end_gap_ms=(end-previous)/1e6 if previous else None,
                apply_to_source_ms=(end-item['wall_applied_ns'])/1e6,
                acquire_ms=(end-item['physics_acquisition_begin_ns'])/1e6,
                native_observed_ns=int(receipt['original_actual']['native']['observed_ns']),
                normal=receipt['original_actual']['native']['normal'])
            window.append(item)
        previous = end
thermal = []
clocks = []
with gzip.open(a.run/'host-profile.jsonl.gz', 'rt') as stream:
    for line in stream:
        row = json.loads(line)
        if abs(row['wall_ns']-fault) <= 2_000_000_000:
            clocks.append(dict(offset_ms=(row['wall_ns']-fault)/1e6,
                scaling_cur_freq_khz={k: v for k, v in row['host'].items() if 'scaling_cur_freq' in k}))
        if abs(row['wall_ns']-fault) <= 1_000_000_000:
            thermal.append(dict(offset_ms=(row['wall_ns']-fault)/1e6,
                max_cpu_c=max(v/1000 for k, v in row['host'].items() if '/temp' in k),
                counters={k.rsplit('/', 1)[-1]: v for k, v in row['host'].items() if 'throttle' in k}))
server = read(a.run/'server.json')
renderer = read(a.run/'capture/paired/renderer/result.json')
late_inference = [dict(begin_wall_ns=x['begin_ns'], end_wall_ns=x['end_ns'],
    original_acquisition_ns=x['original_acquisition_ns'],
    result_after_fault_ms=(x['end_ns']-fault)/1e6,
    source_to_result_ms=(x['end_ns']-x['original_acquisition_ns'])/1e6,
    compute_ms=(x['end_ns']-x['begin_ns'])/1e6) for x in renderer['inference']
    if x['end_ns']-x['original_acquisition_ns'] > 100_000_000]
result = dict(scope='post-run descriptive measurements, not a replacement acceptance audit',
    first_fault=meta['first_fault'], first_protection_wall_ns=fault,
    fault_after_initial_ms=(fault-meta['initial'])/1e6, native_at_first_fault=first,
    ages_at_fault_ms={k: (fault-int(first[k]))/1e6 for k in ('wheel_source', 'hv_source', 'hv_dependency')},
    hv_dependency_limit_ms=meta['hv_dependency_ns']/1e6,
    native_slots_all=slots(complete), native_slots_before_fault=slots(before),
    source_window=window, nearby_thermal_samples=thermal, nearby_frequency_samples=clocks,
    resource_minima={k: min(row[k] for row in server['resources']) for k in ('available_ram_bytes', 'spool_free_bytes')},
    late_inferences=late_inference,
    inference='The source/HV dependency chain exceeded its unchanged age limit. All logical CPUs reported about800MHz in the first two post-fault500ms samples, without a sampled thermal counter rise. These samples cannot establish exact ordering or identify the power, thermal, scheduler or IO cause.')
a.output.write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps({k: v for k, v in result.items() if k not in ('source_window', 'nearby_thermal_samples', 'nearby_frequency_samples')}))

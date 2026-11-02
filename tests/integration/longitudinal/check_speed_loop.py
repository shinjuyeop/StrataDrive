#!/usr/bin/env python3
"""Independent full-path M8 verdict. Preserve every run and reject missing data."""
import argparse
import csv
import datetime
import hashlib
import json
import math
from pathlib import Path
import platform
import subprocess

ROOT = Path(__file__).resolve().parents[3]
NS = 1_000_000_000


def reference(t):
    if t < 20: return (30 / 3.6) * t / 20
    if t < 35: return 30 / 3.6
    if t < 43: return 30 / 3.6 - (10 / 3.6) * (t - 35) / 8
    if t < 58: return 20 / 3.6
    if t < 72: return (20 / 3.6) * (72 - t) / 14
    return 0.


def read_rows(path):
    with path.open() as stream:
        return [{k: float(v) if any(c in v.lower() for c in '.enai') else int(v)
                 for k, v in row.items()} for row in csv.DictReader(stream)]


def judge(directory):
    config = json.loads((directory / 'config.json').read_text())
    runtime = json.loads((directory / 'runtime.json').read_text())
    control = read_rows(directory / 'control.csv')
    physical = read_rows(directory / 'physical.csv')
    mode = config['mode']
    summary = json.loads((directory / f"logical-{'normal' if mode == 'nominal' else mode}.json").read_text())
    errors = []
    def require(ok, reason):
        if not ok: errors.append(reason)
    require(runtime['passed'] and summary['passed'], 'runtime: ' + runtime['reason'])
    require(bool(control) and bool(physical), 'empty trace')
    if not control or not physical: return {'pass': False, 'errors': errors}
    origin = runtime['speed_origin_ns']
    require(origin == control[0]['now_ns'], 'origin')
    require(all(math.isfinite(v) for row in control + physical for v in row.values()), 'nonfinite')
    for i, row in enumerate(control):
        require(row['profile_ns'] == i * 20_000_000 and row['now_ns'] == origin + row['profile_ns'], f'control grid {i}')
        require(row['sequence'] == i and row['epoch'] == 1, f'control identity {i}')
        require(abs(row['target_mps'] - reference(row['profile_ns']/NS)) < 1e-12, f'reference {i}')
        require(0 <= row['now_ns'] - row['speed_source_ns'] <= 30_000_000, f'source age {i}')
        require(row['request_expiry_ns'] == row['speed_source_ns'] + 30_000_001, f'expiry {i}')
        require(-5 <= row['acceleration_mps2'] <= 2, f'acceleration {i}')
        previous = control[i-1]['acceleration_mps2'] if i else 0
        require(abs(row['acceleration_mps2'] - previous) <= .040000000001, f'slew {i}')
        if i: require(row['speed_source_ns'] > control[i-1]['speed_source_ns'], f'acquisition {i}')
    require(all(row['model_epoch'] == 7 and row['speed_mps'] >= 0 and abs(row['balance_j']) <= 1e-5 for row in physical), 'physical invariants')
    require(all(b['now_ns']-a['now_ns'] == 10_000_000 and b['model_sequence'] > a['model_sequence'] and b['distance_m'] >= a['distance_m']
                for a, b in zip(physical, physical[1:])), 'physical grid/continuity')
    require(physical[-1]['now_ns'] == NS + config['duration_ns'] - 9_000_000, 'physical duration')
    metrics = {}
    if mode == 'nominal':
        require(len(control) == 4350 and runtime['speed_fault'] == 0, 'control coverage/fault')
        for name, rows, period in [('feedback', control, .02), ('physical', physical, .01)]:
            series = [((r['now_ns']-origin)/NS, r['speed_mps']) for r in rows]
            windows = []
            for begin, end, target in [(25, 35, 30/3.6), (48, 58, 20/3.6), (77, 87, 0)]:
                values = [abs(v-target)*3.6 for t, v in series if begin <= t < end]
                maximum = max(values, default=math.inf)
                require(len(values) == round((end-begin)/period) and maximum <= 1, f'{name} plateau {begin}')
                windows.append({'begin_s': begin, 'end_s': end, 'samples': len(values), 'max_error_kph': maximum if values else None})
            ratios = [max(0, v-reference(t))/reference(t) for t, v in series if 0 < t < 87 and reference(t) > 0]
            overspeed = max(ratios, default=math.inf)
            require(overspeed <= .1, f'{name} overspeed')
            metrics[name] = {'plateaus': windows, 'max_positive_overspeed_ratio': overspeed if ratios else None}
        final = physical[-1]
        require(final['speed_mps'] <= .001 and abs(final['torque_nm']) <= .1 and final['pressure_pa'] >= 100000 and final['bus_v'] <= 30 and final['contacts'] == 0, 'physical shutdown')
        require(summary['first_fault_ns'] == 0, 'unexpected protection')
        # New allocation commands must reuse at least one controller root.
        pairs = [(a, b) for a, b in zip(physical, physical[1:]) if a['command_source_ns'] and b['now_ns'] < origin + 87*NS]
        require(any(a['command_source_ns'] != b['command_source_ns'] and a['command_root_sequence'] == b['command_root_sequence'] for a, b in pairs), 'missing independent 10ms renewal')
    else:
        injection = NS + config['injection_ns']
        require(config['injection_ns'] <= summary['first_fault_ns'] <= config['injection_ns']+100_000_000, 'fault detection')
        require(summary['first_fault_ns'] <= summary['all_protected_ns'] <= config['injection_ns']+100_000_000, 'protection selection')
        selection = NS + summary['all_protected_ns']
        after = [r for r in physical if r['now_ns'] >= selection+230_000_000]
        require(bool(after) and all(abs(r['torque_nm']) <= 1 and r['pressure_pa'] >= 1_000_000 and not r['run_gate'] for r in after), 'physical protection response/latch')
        require(control[-1]['now_ns'] <= selection and all(not r['run_gate'] for r in physical if r['now_ns'] >= selection), 'normal resumed')
        require(any(r['speed_mps'] > 5 and r['run_gate'] for r in physical if injection-NS <= r['now_ns'] < injection), 'fault was not injected while driving')
        metrics = {'detection_ms': (NS+summary['first_fault_ns']-injection)/1e6,
                   'selection_ms': (selection-injection)/1e6, 'post_response_samples': len(after)}
    return {'pass': not errors, 'errors': errors, 'control_samples': len(control), 'physical_samples': len(physical), 'metrics': metrics}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runner', type=Path)
    parser.add_argument('--output-root', type=Path)
    parser.add_argument('--check', type=Path)
    args = parser.parse_args()
    if args.check:
        result = judge(args.check)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0 if result['pass'] else 1
    if not args.runner or not args.output_root: parser.error('runner and output-root required')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = args.output_root / stamp
    output.mkdir(parents=True, exist_ok=False)
    sources = [p for base in ('central', 'simulation', 'interfaces', 'zone', 'vecu', 'cmake')
               for p in (ROOT/base).rglob('*') if p.is_file() and p.suffix in ('.cpp', '.hpp', '.cmake')]
    sources += [ROOT/'CMakeLists.txt', ROOT/'docs/test-plan/speed-loop-protocol.md', Path(__file__), Path(__file__).with_name('speed_loop_run.cpp')]
    manifest = {'python': platform.python_version(), 'clock': 'logical', 'binary_sha256': hashlib.sha256(args.runner.read_bytes()).hexdigest(),
                'sources': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(sources)}}
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    results = {}
    for mode in ('nominal', 'feedback-loss', 'command-loss'):
        argv = [str(args.runner.resolve()), mode, str(output/mode)]
        returncode = -1
        try:
            with (output/(mode+'.log')).open('w') as log:
                run = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT, timeout=120)
            returncode = run.returncode
            result = judge(output/mode)
        except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
            result = {'pass': False, 'errors': [repr(exc)]}
        (output/mode).mkdir(exist_ok=True)
        result.update(argv=argv, returncode=returncode)
        result['pass'] = result['pass'] and returncode == 0
        results[mode] = result
        (output/mode/'verdict.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    (output/'result.json').write_text(json.dumps(results, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'output': str(output), 'results': results}, indent=2, allow_nan=False))
    return 0 if all(r['pass'] for r in results.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())

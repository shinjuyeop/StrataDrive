#!/usr/bin/env python3
"""Verify retained startup correction and failed live trial; never launch CARLA."""
import argparse
import copy
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tarfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def timeline(run):
    capture = run / 'capture'
    read = lambda name: json.loads((capture / name).read_text())
    startup = read('native-startup.json')
    jobs = [{k: int(v) for k, v in row.items()} for row in csv.DictReader((capture / 'native.csv').open())]
    assert len(startup) == 5 and [r['leaf'] for r in startup] == list(range(5))
    enable = startup[0]['enable_ns']
    for i, row in enumerate(startup):
        period = 20_000_000 if i == 3 else 10_000_000
        first = next(j for j in jobs if j['now'] >= enable + period)
        assert row['epoch'] == 42 and row['enable_ns'] == enable
        assert enable <= row['initialized_ns'] <= first['now']
        assert row['first_due_ns'] == row['first_body_ns'] == row['first_wait_ns'] == first['now']
        assert row['first_body_fault'] == 0 and row['first_wait_mask'] == 6
        for phase in ('first_due', 'first_body'):
            assert row[phase + '_source_ns'] == first['now']
            assert row[phase + '_power_dependency_ns'] == row[phase + '_battery_dependency_ns'] == first['hv_dependency'] < enable
        pending = [j for j in jobs if j['now'] >= first['now'] and j['hv_dependency'] < enable]
        assert row['wait_calls'] == len(pending) and row['last_wait_ns'] == pending[-1]['now']
    fault = next(j['now'] for j in jobs if j['protection'])
    assert fault == next(j['now'] for j in jobs if j['now'] > enable + 30_000_000)
    assert all(not j['armed'] and j['hv_dependency'] < enable for j in jobs)
    assert all(j['protection'] == (fault if j['now'] >= fault else 0) for j in jobs)
    events = read('events.json')
    status = [e for e in events if e['op'] == 'wall_status']
    gap = max(int(e['response']['max_pump_gap_ns']) for e in status)
    first_gap = next(e for e in status if int(e['response']['max_pump_gap_ns']) == gap)
    assert gap > 30_000_000 and first_gap['wall_ns'] > fault
    assert all(not e['response']['wall_wait'] for e in status if e['wall_ns'] < fault)
    assert first_gap['response']['wall_wait'] == 'native_protection_authority'
    sensor = read('sensors.json')
    assert len(sensor['state']) == 2 and all(s['begin_wall_ns'] < enable for s in sensor['state'])
    assert len(sensor['model_calls']) == 1 and sensor['model_calls'][0]['begin_wall_ns'] > fault
    native = [json.loads(line) for line in (capture / 'native-perception.jsonl').read_text().splitlines()]
    assert all(not r['perception']['initialized'] and not r['perception']['available'] and not r['perception']['accepted_results'] for r in native)
    assert not sensor['errors'] and not sensor['cleanup_errors'] and sensor['closed']
    assert sensor['camera_cleanup'] == 'destroyed after ownership release'
    result = read('result.json')
    assert result['status'] == 'FAIL' and result['completed_physics'] == 2 and result['native_exit'] == 0
    assert all(result['pause'].values()) and result['close']['ok'] and not result['close']['locked']
    assert not result.get('cleanup_error') and not result.get('camera_cleanup_error')
    watch = list(csv.DictReader((capture / 'native-wall.csv').open()))
    assert all(int(r['detected_ns']) == 0 for r in watch)
    initial = read('native.json')['initial']
    return dict(startup_correction='PASS', driving_acceptance=False, live_shadow_delivery='NOT_DEMONSTRATED',
                native_calls=len(jobs), enable_after_initial_ns=enable-initial,
                init_delivery_delay_ns=[r['initialized_ns']-enable for r in startup],
                first_body_after_enable_ns=[r['first_body_ns']-enable for r in startup],
                first_body_fault=[r['first_body_fault'] for r in startup],
                protection_after_enable_ns=fault-enable, protection_after_initial_ns=fault-initial,
                max_server_pump_gap_ns=gap, max_rpc_window_at_gap_ns=int(first_gap['response']['max_rpc_window_ns']),
                first_live_inference_after_protection_ns=sensor['model_calls'][0]['begin_wall_ns']-fault,
                actual_packets_by_role=[sum(r['actual'][i] is not None for r in native) for i in range(3)],
                wall_watch_jobs=len(watch), wall_watch_detected=0, camera_cleanup=sensor['camera_cleanup'],
                attribution='server pump gap observed; underlying renderer/driver/scheduling cause not established')


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--work', type=Path, required=True); args = parser.parse_args()
    bundle = Path(__file__).resolve().parent; work = args.work.resolve(); work.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((bundle / 'evidence-manifest.json').read_text())
    for name, item in manifest['files'].items():
        path = bundle / name
        assert path.stat().st_size == item['bytes'] and sha(path) == item['sha256'], name
    frozen = json.loads((bundle / 'sources.json').read_text())
    assert sha(bundle / 'sources.tar.gz') == frozen['archive_sha256']
    source = work / 'source'; source.mkdir()
    with tarfile.open(bundle / 'sources.tar.gz', 'r:gz') as tar:
        members = tar.getmembers(); assert len(members) == len(frozen['files']) and {m.name for m in members} == set(frozen['files'])
        for member in members:
            name = Path(member.name); assert member.isfile() and not name.is_absolute() and '..' not in name.parts
            data = tar.extractfile(member).read(); item = frozen['files'][member.name]
            assert len(data) == item['bytes'] and hashlib.sha256(data).hexdigest() == item['sha256']
            dest = source / name; dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(data)
    run = work / 'startup-fixed-01'; shutil.copytree(bundle / 'startup-fixed-01', run)
    server = json.loads((run / 'server.json').read_text())
    assert server['freeze_sha256'] == sha(bundle / 'sources.json')
    assert server['original_ini_sha256'] == server['restored_ini_sha256'] and server['server_exit'] == 130
    raw = json.loads((bundle / 'raw-manifest.json').read_text()); archive = bundle / raw['archive']
    assert archive.stat().st_size == raw['bytes'] and sha(archive) == raw['sha256'], 'hydrate original raw with Git LFS'
    with tarfile.open(archive) as tar:
        members = tar.getmembers(); assert len(members) == len(raw['members']) and {m.name for m in members} == set(raw['members'])
        for member in members:
            assert member.isfile() and Path(member.name).name == member.name
            data = tar.extractfile(member).read(); item = raw['members'][member.name]
            assert len(data) == item['bytes'] and hashlib.sha256(data).hexdigest() == item['sha256']
            (run / 'capture' / member.name).write_bytes(data)
    sys.path[:0] = [str(source), str(source / 'tests/integration/perception')]
    spec = importlib.util.spec_from_file_location('frozen_audit', source / 'tests/integration/perception/audit_control_shadow_v1.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    expected = json.loads((bundle / 'startup-fixed-01/audit.json').read_text())
    assert module.audit(run) == expected
    result = timeline(run); assert result == json.loads((bundle / 'timeline.json').read_text())
    assert json.loads((bundle / 'live-replay/replay.json').read_text())['startup'] == json.loads((run / 'capture/native-startup.json').read_text())
    rejected = []
    def reject(name, path, bad, check):
        original = path.read_bytes(); path.write_bytes(bad)
        try:
            try: check(run)
            except (ValueError, KeyError, AssertionError, StopIteration): rejected.append(name)
            else: raise AssertionError('mutation accepted: ' + name)
        finally: path.write_bytes(original)
    path = run / 'capture/native-startup.json'; rows = json.loads(path.read_text())
    for field in ('enable_ns', 'first_body_ns', 'first_body_fault', 'first_wait_mask', 'first_due_power_dependency_ns', 'wait_calls'):
        bad = copy.deepcopy(rows); bad[0][field] += 1
        reject('startup-' + field, path, json.dumps(bad).encode(), timeline)
    path = run / 'capture/sensors.json'; sensor = json.loads(path.read_text())
    for name, offset in (('reserved', 28), ('clock', 32), ('version', 8)):
        bad = copy.deepcopy(sensor); data = bytearray.fromhex(bad['ipc'][0]['packet_hex']); data[offset] ^= 1; bad['ipc'][0]['packet_hex'] = data.hex()
        reject('wire-' + name, path, json.dumps(bad).encode(), module.audit)
    bad = copy.deepcopy(sensor); bad['raw'] = []
    reject('omitted-raw', path, json.dumps(bad).encode(), module.audit)
    bad = copy.deepcopy(sensor); bad['camera_cleanup'] = 'not verified'
    reject('cleanup-claim', path, json.dumps(bad).encode(), timeline)
    path = run / 'capture/native-perception.jsonl'; rows = [json.loads(x) for x in path.read_text().splitlines()]
    bad = copy.deepcopy(rows); row = next(r for r in bad if r['actual'][0]); packet = bytearray.fromhex(row['actual'][0]); packet[-1] ^= 1; row['actual'][0] = packet.hex()
    reject('original-actual-crc', path, ''.join(json.dumps(r)+'\n' for r in bad).encode(), module.audit)
    path = run / 'capture' / next(iter(raw['members'])); bad = bytearray(path.read_bytes()); bad[-1] ^= 1
    reject('raw-content-hash', path, bytes(bad), module.audit)
    assert module.audit(run) == expected and timeline(run) == result
    validation = dict(status='PASS', exact_live_audit=True, exact_startup_timeline=True, rejected_mutations=rejected, driving_acceptance=False)
    (work / 'validation.json').write_text(json.dumps(validation, indent=2)+'\n'); print(json.dumps(validation, indent=2))


if __name__ == '__main__':
    main()

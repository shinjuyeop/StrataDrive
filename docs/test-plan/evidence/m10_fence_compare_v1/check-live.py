#!/usr/bin/env python3
"""Reproduce this diagnostic pair using the prospective frozen readers."""
import argparse
import copy
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--work', type=Path, required=True)
    a = p.parse_args()
    bundle = Path(__file__).resolve().parent
    work = a.work.resolve()
    work.mkdir(parents=True, exist_ok=False)
    seal = json.loads((bundle / 'evidence-manifest.json').read_text())
    for name, item in seal['files'].items():
        path = bundle / name
        assert path.stat().st_size == item['bytes'] and sha(path) == item['sha256'], name
    source, frozen = module('source_check', bundle / 'check-evidence.py').extract(bundle, work)
    sys.path[:0] = [str(source), str(source / 'tests/integration/perception')]
    timing = module('frozen_fence', source / 'tests/integration/perception/audit_fence_compare_v1.py')
    shadow = module('frozen_shadow', source / 'tests/integration/perception/audit_control_shadow_v1.py')
    runs = [work / name for name in ('camera-absent-01', 'camera-2k-01')]
    build = json.loads((bundle / 'build-02/manifest.json').read_text())
    assert len(build['installed']) == 4
    for item in build['installed'].values():
        assert frozen['external'][item['path']] == item['instrumented_sha256']
    for run in runs:
        shutil.copytree(bundle / run.name, run)
        server = json.loads((run / 'server.json').read_text())
        assert server['freeze_sha256'] == sha(bundle / 'sources.json')
        assert server['server_timing_build_sha256'] == sha(bundle / 'build-02/manifest.json')
        assert server['server_exit'] == 130 and not server.get('forced_stop')
        assert server['original_ini_sha256'] == server['restored_ini_sha256']
        assert timing.audit(run) == json.loads((run / 'fence-audit.json').read_text())
        assert shadow.audit(run) == json.loads((run / 'audit.json').read_text())
        replay = bundle / ('replay-' + run.name)
        assert list(csv.DictReader((replay / 'replay.csv').open())) == list(csv.DictReader((run / 'capture/native.csv').open()))
        assert json.loads((replay / 'replay.json').read_text())['startup'] == json.loads((run / 'capture/native-startup.json').read_text())
        sensor = json.loads((run / 'capture/sensors.json').read_text())
        assert not sensor['camera'] and not sensor['raw'] and not sensor['model_calls']
    expected = json.loads((bundle / 'comparison.json').read_text())
    assert timing.compare(*runs) == expected
    assert module('derive', bundle / 'derive.py').derive(work, timing) == json.loads((bundle / 'timeline.json').read_text())
    prior = bundle.parent / 'm10_server_timing_v1/future-exclusion.json'
    exclusion = json.loads((bundle / 'future-exclusion.json').read_text())
    assert exclusion['prior_sha256'] == sha(prior)
    assert exclusion['rgb_sha256'] == json.loads(prior.read_text())['rgb_sha256']
    assert exclusion['prior_count'] == exclusion['count'] == 8978
    assert exclusion['new_raw_packets'] == 0 and exclusion['holdout_access'] is False
    assert json.loads((bundle / 'raw-manifest.json').read_text())['archives'] == []
    restored = json.loads((bundle / 'restoration.json').read_text())
    for name, item in build['installed'].items():
        assert restored[name]['path'] == item['path']
        assert restored[name]['sha256'] == item['original_sha256'] and restored[name]['restored']
    rejected = []

    def reject(name, path, bad, check):
        original = path.read_bytes()
        path.write_bytes(bad)
        try:
            try:
                check()
            except (ValueError, KeyError, AssertionError):
                rejected.append(name)
            else:
                raise AssertionError('mutation accepted: ' + name)
        finally:
            path.write_bytes(original)

    camera = runs[1]
    path = camera / 'server.log'
    lines = path.read_text().splitlines()
    end = timing.reader.END
    prefix = timing.reader.PREFIX
    summaries = [i for i, line in enumerate(lines) if line.startswith(end)]
    index = next(i for i, line in enumerate(lines) if line.startswith(prefix)
                 and json.loads(line[len(prefix):])['cpu_begin'] > 0)
    audit_camera = lambda: timing.audit(camera)
    for i in summaries:
        component = json.loads(lines[i][len(end):])['component']
        reject('missing-end-' + component, path,
               '\n'.join(line for j, line in enumerate(lines) if i != j).encode(), audit_camera)
    for field, value in (('overflow', 1), ('rows', 0)):
        bad = lines.copy()
        row = json.loads(bad[summaries[0]][len(end):])
        row[field] = value
        bad[summaries[0]] = end + json.dumps(row)
        reject('journal-' + field, path, '\n'.join(bad).encode(), audit_camera)
    bad = lines.copy()
    bad.insert(index, bad[index])
    reject('duplicate-row', path, '\n'.join(bad).encode(), audit_camera)
    for field, value in (('end', 0), ('cpu_end', 0), ('stage', 'unknown'), ('begin', True)):
        bad = lines.copy()
        row = json.loads(bad[index][len(prefix):])
        row[field] = value
        bad[index] = prefix + json.dumps(row)
        reject('timing-' + field, path, '\n'.join(bad).encode(), audit_camera)
    path = camera / 'capture/result.json'
    bad = json.loads(path.read_text())
    bad['rendering_enabled'] = False
    reject('renderer-disabled', path, json.dumps(bad).encode(), audit_camera)
    path = camera / 'capture/sensors.json'
    sensor = json.loads(path.read_text())
    bad = copy.deepcopy(sensor)
    bad['preparation_calls'].pop()
    reject('preparation-count', path, json.dumps(bad).encode(), audit_camera)
    bad = copy.deepcopy(sensor)
    bad['sensor_attributes']['image_size_x'] = '1280'
    reject('camera-resolution', path, json.dumps(bad).encode(), audit_camera)
    path = runs[0] / 'capture/sensors.json'
    bad = json.loads(path.read_text())
    bad['camera_condition'] = '2k'
    reject('condition-mismatch', path, json.dumps(bad).encode(), lambda: timing.audit(runs[0]))
    path = camera / 'server.json'
    server = json.loads(path.read_text())
    for field, value in (('freeze_sha256', 'wrong'), ('server_timing_build_sha256', 'wrong'),
                         ('attempts', 2), ('started_utc', '2000-01-01T00:00:00+00:00'),
                         ('argv', server['argv'] + ['-changed']),
                         ('client_argv', server['client_argv'] + ['--changed'])):
        bad = copy.deepcopy(server)
        bad[field] = value
        reject('pair-' + field, path, json.dumps(bad).encode(), lambda: timing.compare(*runs))
    assert timing.compare(*runs) == expected
    result = dict(status='PASS', exact_pair_audit=True, exact_shadow_audits=2,
                  exact_retained_replays=2, exact_timeline=True, rejected_mutations=rejected,
                  scope='retained diagnostic integrity; both driving attempts remain FAIL',
                  driving_acceptance=False)
    (work / 'validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

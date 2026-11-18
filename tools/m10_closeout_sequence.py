#!/usr/bin/env python3
"""Summarize a finished M10 sequence and retain byte-checked evidence.

Reuse the retained parameterized analyzers; do not rescore original verdicts.
This runs after all physical work and archive reproduction, never alongside UE.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ANALYZERS = ROOT/'docs/test-plan/evidence/m10_gc_recovery_v3'
CASES = ('normal-30s-01', 'normal-30s-02', 'normal-300s-01')
REPRODUCTIONS = ('state-path', 'structured-state', 'monitor-timing', 'host-clock',
                  'owner-wait', 'workspace', 'owner-gc', 'admission-window')


def read(path):
    return json.loads(path.read_text())


def identity(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return dict(bytes=path.stat().st_size, sha256=h.hexdigest())


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def stopped():
    if any(n.startswith(('UE4Editor','CarlaUE4-Linux')) for n in subprocess.check_output(['ps', '-eo', 'comm='], text=True).splitlines()):
        raise RuntimeError('finish engine execution before analysis or archive I/O')


def main(a):
    series, work = a.series.resolve(), a.work.resolve()
    stopped()
    sequence = read(series/'sequence-disposition.json')
    assert sequence['runtime_restoration']['status'] == 'PASS'
    owner = read(work/'experiment-owner.json')
    proc = Path('/proc')/str(owner['pid'])/'stat'
    assert not proc.exists() or int(proc.read_text().rsplit(')', 1)[1].split()[19]) != owner['start_ticks']
    events = [json.loads(line) for line in (work/'power-lease.jsonl').read_text().splitlines()]
    assert [r['event'] for r in events] == ['OWNER', 'APPLIED', 'RESTORED']
    assert events[1]['maximum_percent'] == 70 and events[-1]['maximum_percent'] == 100
    policy = {n: Path('/sys/devices/system/cpu/intel_pstate', n).read_text().strip()
              for n in ('min_perf_pct', 'max_perf_pct', 'no_turbo')}
    assert policy == dict(min_perf_pct='16', max_perf_pct='100', no_turbo='0')
    files = read(series/'pre-install.json')['files']
    for item in files.values():
        item['checked_sha256'] = identity(Path(item['path']))['sha256']
        assert item['checked_sha256'] == item['sha256']
    if not (series/'power-lease.jsonl').exists():
        shutil.copy2(work/'power-lease.jsonl', series/'power-lease.jsonl')
    assert (series/'power-lease.jsonl').read_bytes() == (work/'power-lease.jsonl').read_bytes()
    commands, cases = [], {}

    def call(script, argv, log):
        stopped()
        command = [sys.executable, str(script), *map(str, argv)]
        with log.open('x') as stream:
            result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
        commands.append(dict(argv=command, script=identity(script), exit=result.returncode))
        result.check_returncode()

    for name in CASES:
        bundle = series/name
        if not (bundle/'disposition.json').exists():
            continue
        run = work/name/'archive-check/run'
        disposition = read(bundle/'disposition.json')
        assert read(bundle/'archive-validation.json')['status'] == 'PASS'
        if not (run/'capture/native.json').exists():
            server = read(run/'server.json')
            assert not disposition['finite_diagnostic_pass'] and server['status'] == 'FAIL'
            assert not read(bundle/'raw-manifest.json')['archives']
            assert all(read(bundle/(stem+'-reproduction.json'))['status'] == 'PASS' for stem in REPRODUCTIONS)
            manifest = read(bundle/'run-manifest.json')
            assert manifest['bytes'] < 2*1024*1024, 'bounded setup failure only'
            target = bundle/'readiness-failure.tar.gz'
            if not target.exists():
                shutil.copy2(bundle/manifest['archive'], target)
            assert identity(target) == {k: manifest[k] for k in ('bytes', 'sha256')}
            cases[name] = dict(disposition=disposition, native_started=False, raw_images=0,
                server_error=server['error'], retained_setup=identity(target))
            continue
        replay_path=bundle/'replay.json'
        exact_replay=(replay_path.exists() and read(replay_path).get('exact') is True
                      and read(bundle/'drive-fault-replay.json').get('equal') is True)
        if not exact_replay:
            # A rejected receipt cannot be promoted to exact replay. Retain the
            # original converter failure while still closing out raw evidence.
            assert not disposition['finite_diagnostic_pass'] and disposition['replay']!=0
            assert disposition['drive_fault_replay'] is False
            sys.path.insert(0,str(ROOT/'tests/integration/carla'))
            from evidence_io import json_rows
            expired=[int(r['receipt']['frame']) for r in json_rows(run/'capture/trace.jsonl')
                     if r['receipt']['wall_authority_expired_during_physics']]
            log=(bundle/'replay.log').read_text()
            assert expired and 'wall_authority_expired_during_physics' in log and 'AssertionError' in log
            if not (bundle/'replay-rejection.json').exists():
                write(bundle/'replay-rejection.json',dict(status='FAIL_ORIGINAL_REPLAY_RETAINED',
                    expired_receipt_frames=expired,exact_replay=False,original_log=identity(bundle/'replay.log')))
        assert all(read(bundle/(stem+'-reproduction.json'))['status'] == 'PASS' for stem in REPRODUCTIONS)
        steps = [
            ('analyze.py', ['--run', run, '--case', name, '--output', bundle/'analysis.json'], 'analysis.json'),
            ('analyze-state-path.py', ['--run', run, '--bundle', bundle], 'path-analysis.json'),
            (ROOT/'tests/integration/perception/analyze_endurance_gc_v1.py', ['--run', run, '--bundle', bundle], 'gc-analysis.json'),
            ('package-review.py', ['--run', run, '--bundle', bundle], 'retained-metadata.json'),
            ('package-bounded-review.py', ['--bundle', bundle], 'bounded-review.json'),
        ]
        for script, argv, target in steps:
            if not (bundle/target).exists():
                script=Path(script)
                call(ANALYZERS/script, argv, bundle/(script.name+'.log'))
        analysis, path = read(bundle/'analysis.json'), read(bundle/'path-analysis.json')
        server = read(run/'server.json')
        assert events[1]['wall_ns'] < path['initial_ns'] < path['physical_end_ns'] < events[-1]['wall_ns']
        assert all(v['end_wall_ns'] < events[-1]['wall_ns'] for v in server['shutdown'].values())
        if disposition['finite_diagnostic_pass']:
            assert read(bundle/'audit.json')['status'] == 'PASS_DIAGNOSTIC_CASE_ONLY'
            assert analysis['protection_intervals'] == 0
        cases[name] = dict(disposition=disposition, analysis=analysis,
            exact_replay=exact_replay,
            fast_clock=path['fast_clock'], gc=read(bundle/'owner-gc.json'),
            native_deadlines=read(bundle/'native-gap-analysis.json')['counts'])
        if a.compact and not (bundle/'compaction-validation.json').exists():
            sys.path.insert(0, str(ROOT/'tests/integration/perception'))
            from compact_endurance_archive_v1 import compact
            write(bundle/'compaction-validation.json', compact(bundle, run))
        print(name+' analyzed; original verdict retained', flush=True)
    write(series/'restoration-confirmation.json', dict(status='PASS',
        checked_utc=datetime.now(timezone.utc).isoformat(), files=files, policy=policy,
        lease_restoration_reason=events[-1]['reason'],
        all_measured_work_and_server_shutdown_before_restoration=True))
    write(series/'final-validation.json', dict(status='PASS_EVIDENCE_AND_RESTORATION_ONLY',
        cases=cases, original_verdicts_preserved=True,
        all_declared_finite_cases_pass=len(cases) == len(sequence['cases']) and bool(cases) and all(
            c['disposition']['finite_diagnostic_pass'] for c in cases.values()),
        continuous_driving_accepted=False, native_perception_accepted=False, milestone_closed=False))
    write(series/'closeout-inputs.json', dict(tool=identity(Path(__file__)), commands=commands,
        compact=a.compact, note='Existing completed derivations are reused without changing original verdicts.'))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--series', type=Path, required=True)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--compact', action='store_true')
    main(p.parse_args())

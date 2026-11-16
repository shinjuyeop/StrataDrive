"""Run the single declared 300s diagnostic case, restore, audit and seal it."""
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
SERIES = Path(__file__).resolve().parent
SCRIPTS = ROOT / 'tests/integration/perception'
PYTHON = ROOT / 'build/m10-perception/cuda-venv/bin/python'
WORK = ROOT / 'build/m10-host-endurance-v1'
RUN = Path('/tmp/stratadrive-m10-host-endurance-v1/normal-300s-01')
BUNDLE = SERIES / 'normal-300s-01'
ENGINE = Path('/d/shin/stratadrive-tools/UnrealEngine_4.26')
CARLA = Path('/d/shin/stratadrive-tools/m7-source/carla-0.9.16')
sys.path.insert(0, str(SCRIPTS))
from endurance_profile_v1 import limits
from profile_host_v1 import host


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def call(argv, log):
    with log.open('w') as output:
        return subprocess.run(list(map(str, argv)), stdout=output,
                              stderr=subprocess.STDOUT).returncode


def restore():
    commands = [
        ['python3', ROOT/'tools/carla/m7_nodrive/build_dxc_lifetime.py',
         '--engine', ENGINE, '--output', ROOT/'build/m10-dxc-lifetime-v1', '--restore'],
        ['python3', ROOT/'tools/carla/m7_nodrive/build_endurance.py',
         '--engine', ENGINE, '--source', CARLA, '--output',
         ROOT/'build/m10-remediation/server-build-01', '--restore'],
    ]
    codes = [call(argv, WORK/f'restore-{i}.log') for i, argv in enumerate(commands)]
    original = json.loads((SERIES/'pre-install.json').read_text())
    files = {name: dict(item, restored_sha256=sha(item['path']))
             for name, item in original['files'].items()}
    ok = all(item['restored_sha256'] == item['sha256'] for item in files.values())
    write(SERIES/'restoration.json', dict(status='PASS' if ok and codes == [0, 0] else 'FAIL',
          commands_exit=codes, files=files, checked_utc=datetime.now(timezone.utc).isoformat()))
    assert ok and codes == [0, 0], 'runtime restoration failed; inspect original records'


def live():
    BUNDLE.mkdir(exist_ok=False)
    assert not RUN.exists(), 'single attempt must not overwrite an earlier run'
    base = json.loads((ROOT/'docs/test-plan/evidence/m10_host_profile_v5/h-repeat2/case.json').read_text())
    argv = base['argv'][:]
    for flag, value in [('--freeze', SERIES/'sources.json'), ('--output', RUN),
                        ('--endurance-seconds', '300')]:
        argv[argv.index(flag)+1] = str(value)
    case = dict(base, declared_utc=datetime.now(timezone.utc).isoformat(),
                seconds=300, requested_intervals=60000, run=str(RUN),
                freeze_sha256=sha(SERIES/'sources.json'),
                protocol='docs/test-plan/perception-host-endurance-v1-protocol.md',
                comparison_case='normal-300s-01', argv=argv)
    write(BUNDLE/'case.json', case)
    samples = []
    until = time.monotonic()+180
    while True:
        values = host()
        temperature = max(v/1000 for k, v in values.items() if '/temp' in k)
        samples.append(dict(wall_ns=time.monotonic_ns(), max_cpu_c=temperature))
        if temperature <= 70 or time.monotonic() >= until:
            break
        time.sleep(2)
    required = limits(300)['stored_bytes']+4*1024**3
    free = {p: shutil.disk_usage(p).free for p in ('/tmp', '/d')}
    mem = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    available = int(mem['MemAvailable'].split()[0])*1024
    qualified = temperature <= 70 and min(free.values()) >= required and available >= 4*1024**3
    write(BUNDLE/'preflight.json', dict(status='PASS' if qualified else 'NOT_RUN',
          cpu_samples=samples, free_bytes=free, required_free_bytes=required,
          available_ram_bytes=available, minimum_available_ram_bytes=4*1024**3))
    assert qualified, 'prospective preflight not satisfied; do not start'
    print('START normal-300s-01', flush=True)
    with (WORK/'runner.log').open('w') as log, (WORK/'monitor.log').open('w') as out:
        runner = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        monitor = subprocess.Popen(['taskset', '-c', '0,8', str(PYTHON),
            str(SCRIPTS/'profile_host_v1.py'), '--pid', str(runner.pid), '--seconds', '1100',
            '--output', str(WORK/'profile.jsonl')], stdout=out, stderr=subprocess.STDOUT)
        code = runner.wait()
        monitor_code = monitor.wait(timeout=10)
    write(BUNDLE/'live-exit.json', dict(runner=code, monitor=monitor_code))
    print('SERVER EXIT', code, 'MONITOR', monitor_code, flush=True)
    assert monitor_code == 0
    with (WORK/'profile.jsonl').open('rb') as source, gzip.open(RUN/'host-profile.jsonl.gz', 'wb') as out:
        shutil.copyfileobj(source, out)
    shutil.copy2(WORK/'profile.summary.json', RUN/'host-profile-summary.json')
    return code


def audit_and_seal(code):
    def script(name, args, log):
        return call([PYTHON, SCRIPTS/name, *args], BUNDLE/log)
    audit = script('audit_paired_v1.py', [RUN, '--output', BUNDLE/'audit.json'], 'audit.log')
    shadow = script('audit_control_shadow_v1.py', [RUN, '--output', BUNDLE/'shadow-integrity.json'], 'shadow-integrity.log')
    replay = WORK/'replay'
    replay_code = script('replay_wall_startup_v1.py', ['--capture', RUN/'capture',
        '--binary', ROOT/'build/m10-endurance-v3/native/tests/integration/carla/m7_1g/m7_wall_startup_replay',
        '--scenario', ROOT/'tests/integration/carla/scenarios/m10_endurance_hold_v1.txt',
        '--output', replay, '--require-exact'], 'replay.log')
    if (replay/'validation.json').exists():
        shutil.copy2(replay/'validation.json', BUNDLE/'replay.json')
    print('AUDITS', audit, shadow, replay_code, flush=True)
    assert script('seal_endurance_v1.py', ['--run', RUN, '--bundle', BUNDLE,
        '--prior', ROOT/'docs/test-plan/evidence/m10_host_profile_v5/h-repeat2/future-exclusion.json'], 'seal.log') == 0
    print('SEALED; starting independent archive audit', flush=True)
    assert script('check_endurance_archive_v1.py', ['--series', SERIES, '--bundle', BUNDLE,
        '--work', WORK/'archive-check'], 'archive-check.log') == 0
    shutil.copy2(WORK/'archive-check/validation.json', BUNDLE/'archive-validation.json')
    assert RUN.parent == Path('/tmp/stratadrive-m10-host-endurance-v1')
    shutil.rmtree(RUN)
    write(BUNDLE/'disposition.json', dict(runner=code, physical_audit=audit, shadow_audit=shadow,
          replay=replay_code, archive='PASS', finite_300s_diagnostic_pass=all(
          value == 0 for value in (code, audit, shadow, replay_code)),
          native_perception_accepted=False, milestone_closed=False))
    print('ARCHIVE VERIFIED; redundant NVMe spool removed', flush=True)


if __name__ == '__main__':
    try:
        exit_code = live()
    finally:
        restore()
    audit_and_seal(exit_code)

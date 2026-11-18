"""Run the declared 30s diagnostic case, restore, audit and seal it."""
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
WORK = ROOT / 'build/m10-hv50-cache-v1' / sys.argv[1]
NAME = sys.argv[1]
assert NAME in ('normal-30s-01','normal-30s-02','normal-300s-01')
SECONDS=300 if '300s' in NAME else 30
RUN = Path('/tmp/stratadrive-m10-hv50-cache-v1') / NAME
BUNDLE = SERIES / NAME
PREVIOUS='normal-30s-01' if NAME=='normal-300s-01' else None
PRIOR=SERIES/PREVIOUS/'future-exclusion.json' if PREVIOUS else ROOT/'docs/test-plan/evidence/m10_asset_cache_v1/normal-300s-01/future-exclusion.json'
ENGINE = Path('/d/shin/stratadrive-tools/UnrealEngine_4.26')
CARLA = Path('/d/shin/stratadrive-tools/m7-source/carla-0.9.16')
sys.path.insert(0, str(SCRIPTS))
from endurance_profile_v1 import limits
from profile_host_v1 import host
from evidence_reproduction_v1 import require_reproduction
from runtime_restore import restore as restore_runtime


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
    restore_runtime(ROOT, SERIES, WORK, BUNDLE/'restoration.json')


def live():
    preparation=json.loads((SERIES/'asset-preparation.json').read_text())
    assert preparation['status']=='PREPARED_NOT_PHYSICAL_ACCEPTANCE' and preparation['validation_only'] is False
    if not PREVIOUS:assert 0<=time.monotonic_ns()-preparation['completed_wall_ns']<=300_000_000_000,'fresh preparation before first case'
    BUNDLE.mkdir(exist_ok=False)
    WORK.mkdir(exist_ok=False)
    if PREVIOUS:
        assert json.loads((SERIES/PREVIOUS/'disposition.json').read_text())['finite_diagnostic_pass'], 'stop on original failure'
    assert json.loads((SERIES/'code-equivalence.json').read_text())['status']=='PASS_PACKAGED_RENDERER_CANDIDATE'
    isolated=json.loads((ROOT/'docs/test-plan/evidence/m10_host_clock_v1/sensor-probe-01/result.json').read_text())
    assert isolated['status']=='RECORDED' and not isolated['native']['first_fault']
    assert isolated['monitor_slots']['missing']==isolated['monitor_slots']['late']==0
    assert isolated['profile_integrity']['status']=='PASS_MONITOR_DIAGNOSTIC_INTEGRITY'
    assert not RUN.exists(), 'single attempt must not overwrite an earlier run'
    base = json.loads((ROOT/'docs/test-plan/evidence/m10_host_profile_v5/h-repeat2/case.json').read_text())
    argv = base['argv'][:]
    for flag, value in [('--freeze', SERIES/'sources.json'), ('--resource-profile', ROOT/'profiles/perception-endurance-host-v5.json'), ('--output', RUN),
                        ('--endurance-seconds', str(SECONDS)),
                        ('--native', ROOT/'build/m10-hv50-cache-v1/native/tests/integration/carla/m7_1g/m7_carla_wall_owner'),
                        ('--endurance-build',ROOT/'build/m10-gc-feedback-v1/visual-tags-build-01/manifest.json')]:
        argv[argv.index(flag)+1] = str(value)
    argv[argv.index('--renderer-max-fps')+1]='0'
    argv+=['--wall-profile','wall5-hv50-v1','--release-recording-cache']
    argv+=['--packaged-renderer','/d/shin/stratadrive-tools/carla-0.9.16/server/CarlaUE4/Binaries/Linux/CarlaUE4-Linux-Shipping','--prefetch-owner-code']
    argv+=['--profile-state-path','--structured-state','--tensor-workspace','--profile-owner-gc','--owner-purge-slice','--owner-recovery-preview','--prefetch-inference-libraries','--owner-no-visual-tags']
    case = dict(base, declared_utc=datetime.now(timezone.utc).isoformat(),
                seconds=SECONDS, requested_intervals=SECONDS*200, run=str(RUN),
                freeze_sha256=sha(SERIES/'sources.json'),
                protocol='docs/test-plan/perception-hv50-cache-v1-protocol.md',
                comparison_case=NAME, argv=argv)
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
    required = limits(SECONDS)['stored_bytes']+4*1024**3
    free = {p: shutil.disk_usage(p).free for p in ('/tmp', '/d')}
    mem = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    available = int(mem['MemAvailable'].split()[0])*1024
    policy={n:Path('/sys/devices/system/cpu/intel_pstate',n).read_text().strip() for n in ('min_perf_pct','max_perf_pct','no_turbo')}
    qualified = policy==dict(min_perf_pct='16',max_perf_pct='70',no_turbo='0') and temperature <= 70 and min(free.values()) >= required and available >= 4*1024**3
    write(BUNDLE/'preflight.json', dict(status='PASS' if qualified else 'NOT_RUN',
          cpu_samples=samples, host_policy=policy, free_bytes=free, required_free_bytes=required,
          available_ram_bytes=available, minimum_available_ram_bytes=4*1024**3))
    assert qualified, 'prospective preflight not satisfied; do not start'
    print('START '+NAME, flush=True)
    with (WORK/'runner.log').open('w') as log, (WORK/'monitor.log').open('w') as out:
        runner = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        monitor = subprocess.Popen(['taskset', '-c', '0,8', str(PYTHON),
            str(SCRIPTS/'profile_host_v1.py'), '--pid', str(runner.pid), '--seconds', '1100',
            '--output', str(WORK/'profile.jsonl')], stdout=out, stderr=subprocess.STDOUT)
        clock = subprocess.Popen(['taskset','-c','0,8',str(PYTHON),str(SCRIPTS/'profile_host_clock_v1.py'),'--extended',
            '--pid',str(runner.pid),'--seconds','1100','--output',str(WORK/'clock.jsonl')],stdout=out,stderr=subprocess.STDOUT)
        native_host = subprocess.Popen(['taskset','-c','0,8',str(PYTHON),str(SCRIPTS/'profile_host_native_v1.py'),
            '--pid',str(runner.pid),'--seconds','1100','--output',str(WORK/'native-host.jsonl')],stdout=out,stderr=subprocess.STDOUT)
        code = runner.wait()
        native_host_code = native_host.wait(timeout=10)
        clock_code = clock.wait(timeout=10)
        monitor_code = monitor.wait(timeout=10)
    write(BUNDLE/'live-exit.json', dict(runner=code, monitor=monitor_code,clock=clock_code,native_host=native_host_code))
    print('SERVER EXIT', code, 'MONITOR', monitor_code, flush=True)
    assert monitor_code == clock_code == native_host_code == 0
    with (WORK/'profile.jsonl').open('rb') as source, gzip.open(RUN/'host-profile.jsonl.gz', 'wb') as out:
        shutil.copyfileobj(source, out)
    shutil.copy2(WORK/'profile.summary.json', RUN/'host-profile-summary.json')
    with (WORK/'clock.jsonl').open('rb') as source, gzip.open(RUN/'host-clock.jsonl.gz','wb') as out:
        shutil.copyfileobj(source,out)
    shutil.copy2(WORK/'clock.summary.json',RUN/'host-clock-summary.json')
    with (WORK/'native-host.jsonl').open('rb') as source,gzip.open(RUN/'host-native.jsonl.gz','wb') as out:
        shutil.copyfileobj(source,out)
    shutil.copy2(WORK/'native-host.summary.json',RUN/'host-native-summary.json')
    return code


def audit_and_seal(code):
    def script(name, args, log):
        return call([PYTHON, SCRIPTS/name, *args], BUNDLE/log)
    admission = script('audit_hv50_cache_v1.py', ['--run', RUN, '--output', BUNDLE/'admission-window.json'], 'admission-window.log')
    workspace = call([PYTHON, SERIES/'audit-workspace.py', '--run', RUN, '--output', BUNDLE/'workspace.json'], BUNDLE/'workspace.log')
    gc = script('audit_owner_gc_v1.py', ['--run', RUN, '--output', BUNDLE/'owner-gc.json'], 'owner-gc.log')
    audit = script('audit_paired_v1.py', [RUN, '--output', BUNDLE/'audit.json'], 'audit.log')
    shadow = script('audit_control_shadow_v1.py', [RUN, '--output', BUNDLE/'shadow-integrity.json'], 'shadow-integrity.log')
    state_path = script('audit_state_path_v1.py',['--run',RUN,'--output',BUNDLE/'state-path.json'],'state-path.log')
    structured = script('audit_structured_state_v1.py',['--run',RUN,'--output',BUNDLE/'structured-state.json'],'structured-state.log')
    watch = script('audit_watch_timing_v1.py',['--run',RUN,'--output',BUNDLE/'monitor-timing.json'],'monitor-timing.log')
    owner_wait=script('audit_owner_wait_v1.py',['--run',RUN,'--output',BUNDLE/'owner-wait.json'],'owner-wait.log')
    host_clock=script('audit_host_clock_v1.py',['--run',RUN,'--output',BUNDLE/'host-clock-audit.json'],'host-clock-audit.log')
    replay = WORK/'replay'
    replay_code = script('replay_wall_startup_v1.py', ['--capture', RUN/'capture',
        '--binary', ROOT/'build/m10-hv50-cache-v1/native/tests/integration/carla/m7_1g/m7_wall_startup_replay',
        '--scenario', ROOT/'tests/integration/carla/scenarios/m10_endurance_hold_v1.txt',
        '--output', replay, '--require-exact'], 'replay.log')
    if (replay/'validation.json').exists():
        shutil.copy2(replay/'validation.json', BUNDLE/'replay.json')
    fault_equal=False
    if (RUN/'capture/native-drive-fault.json').exists() and (replay/'replay-drive-fault.json').exists():
        fault_equal=json.loads((RUN/'capture/native-drive-fault.json').read_text())==json.loads((replay/'replay-drive-fault.json').read_text())
    write(BUNDLE/'drive-fault-replay.json',dict(status='PASS' if fault_equal else 'FAIL',equal=fault_equal))
    print('AUDITS', audit, shadow, replay_code, 'STATE', state_path, 'STRUCTURED', structured, 'WATCH',watch, flush=True)
    assert script('seal_endurance_v1.py', ['--run', RUN, '--bundle', BUNDLE,
        '--prior', PRIOR], 'seal.log') == 0
    print('SEALED; starting independent archive audit', flush=True)
    assert script('check_endurance_archive_v1.py', ['--series', SERIES, '--bundle', BUNDLE,
        '--work', WORK/'archive-check'], 'archive-check.log') == 0
    shutil.copy2(WORK/'archive-check/validation.json', BUNDLE/'archive-validation.json')
    reproduced=WORK/'state-path-reproduced.json'
    call([PYTHON,WORK/'archive-check/source/tests/integration/perception/audit_state_path_v1.py',
          '--run',WORK/'archive-check/run','--output',reproduced],WORK/'state-path-reproduced.log')
    require_reproduction(json.loads((BUNDLE/'state-path.json').read_text()),json.loads(reproduced.read_text()),RUN,WORK/'archive-check/run')
    write(BUNDLE/'state-path-reproduction.json',dict(status='PASS',original_status=json.loads(reproduced.read_text())['status']))
    reproduced_structured=WORK/'structured-state-reproduced.json'
    call([PYTHON,WORK/'archive-check/source/tests/integration/perception/audit_structured_state_v1.py',
          '--run',WORK/'archive-check/run','--output',reproduced_structured],WORK/'structured-state-reproduced.log')
    require_reproduction(json.loads((BUNDLE/'structured-state.json').read_text()),json.loads(reproduced_structured.read_text()),RUN,WORK/'archive-check/run')
    write(BUNDLE/'structured-state-reproduction.json',dict(status='PASS',original_status=json.loads(reproduced_structured.read_text())['status']))
    reproduced_watch=WORK/'monitor-timing-reproduced.json'
    call([PYTHON,WORK/'archive-check/source/tests/integration/perception/audit_watch_timing_v1.py',
          '--run',WORK/'archive-check/run','--output',reproduced_watch],WORK/'monitor-timing-reproduced.log')
    require_reproduction(json.loads((BUNDLE/'monitor-timing.json').read_text()),json.loads(reproduced_watch.read_text()),RUN,WORK/'archive-check/run')
    write(BUNDLE/'monitor-timing-reproduction.json',dict(status='PASS',original_status=json.loads(reproduced_watch.read_text())['status']))
    reproduced_host=WORK/'host-clock-reproduced.json'
    call([PYTHON,WORK/'archive-check/source/tests/integration/perception/audit_host_clock_v1.py',
          '--run',WORK/'archive-check/run','--output',reproduced_host],WORK/'host-clock-reproduced.log')
    require_reproduction(json.loads((BUNDLE/'host-clock-audit.json').read_text()),json.loads(reproduced_host.read_text()),RUN,WORK/'archive-check/run')
    write(BUNDLE/'host-clock-reproduction.json',dict(status='PASS',original_status=json.loads(reproduced_host.read_text())['status']))
    reproduced_wait=WORK/'owner-wait-reproduced.json'
    call([PYTHON,WORK/'archive-check/source/tests/integration/perception/audit_owner_wait_v1.py','--run',WORK/'archive-check/run','--output',reproduced_wait],WORK/'owner-wait-reproduced.log')
    require_reproduction(json.loads((BUNDLE/'owner-wait.json').read_text()),json.loads(reproduced_wait.read_text()),RUN,WORK/'archive-check/run')
    write(BUNDLE/'owner-wait-reproduction.json',dict(status='PASS',original_status=json.loads(reproduced_wait.read_text())['status']))
    reproduced_workspace=WORK/'workspace-reproduced.json'
    call([PYTHON,WORK/'archive-check/source/docs/test-plan/evidence/m10_hv50_cache_v1/audit-workspace.py','--run',WORK/'archive-check/run','--output',reproduced_workspace],WORK/'workspace-reproduced.log')
    require_reproduction(json.loads((BUNDLE/'workspace.json').read_text()),json.loads(reproduced_workspace.read_text()),RUN,WORK/'archive-check/run')
    write(BUNDLE/'workspace-reproduction.json',dict(status='PASS',original_status=json.loads(reproduced_workspace.read_text())['status']))
    reproduced_gc=WORK/'owner-gc-reproduced.json'
    call([PYTHON,WORK/'archive-check/source/tests/integration/perception/audit_owner_gc_v1.py','--run',WORK/'archive-check/run','--output',reproduced_gc],WORK/'owner-gc-reproduced.log')
    require_reproduction(json.loads((BUNDLE/'owner-gc.json').read_text()),json.loads(reproduced_gc.read_text()),RUN,WORK/'archive-check/run')
    write(BUNDLE/'owner-gc-reproduction.json',dict(status='PASS',original_status=json.loads(reproduced_gc.read_text())['status']))
    assert RUN.parent == Path('/tmp/stratadrive-m10-hv50-cache-v1')
    reproduced_admission=WORK/'admission-window-reproduced.json'
    call([PYTHON,WORK/'archive-check/source/tests/integration/perception/audit_hv50_cache_v1.py','--run',WORK/'archive-check/run','--output',reproduced_admission],WORK/'admission-window-reproduced.log')
    require_reproduction(json.loads((BUNDLE/'admission-window.json').read_text()),json.loads(reproduced_admission.read_text()),RUN,WORK/'archive-check/run')
    write(BUNDLE/'admission-window-reproduction.json',dict(status='PASS',original_status=json.loads(reproduced_admission.read_text())['status']))
    shutil.rmtree(RUN)
    write(BUNDLE/'disposition.json', dict(runner=code, physical_audit=audit, shadow_audit=shadow,
          admission_window=admission, owner_gc=gc, workspace=workspace, replay=replay_code, state_path=state_path,structured_state=structured,monitor_timing=watch,host_clock=host_clock,owner_wait=owner_wait,drive_fault_replay=fault_equal,archive='PASS',finite_diagnostic_pass=fault_equal and all(
          value == 0 for value in (code, audit, shadow, replay_code, state_path, structured,watch,host_clock,owner_wait,workspace,gc,admission)),
          native_perception_accepted=False, milestone_closed=False))
    print('ARCHIVE VERIFIED; redundant NVMe spool removed', flush=True)


if __name__ == '__main__':
    try:
        exit_code = live()
    finally:
        restore()
    audit_and_seal(exit_code)

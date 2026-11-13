import json,subprocess,hashlib,shutil
from pathlib import Path
from datetime import datetime,timezone
root=Path.cwd();py=root/'build/m10-perception/cuda-venv/bin/python';scripts=root/'tests/integration/perception'
series=root/'docs/test-plan/evidence/m10_endurance_v5';work=root/'build/m10-endurance-v5'
freeze=series/'sources.json';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
prior=root/'docs/test-plan/evidence/m10_endurance_v4/normal-30s-01/future-exclusion.json'
base=json.loads((root/'docs/test-plan/evidence/m10_endurance_v3/normal-30s-01/case.json').read_text())
names=[f'normal-30s-{i:02}' for i in range(1,4)]
(series/'series.json').write_text(json.dumps(dict(schema='m10-endurance-series-v1',declared_utc=datetime.now(timezone.utc).isoformat(),cases=names,conditional_300s='Only after all three original physical/shadow audits and exact replays pass',repeat_failed_case=False,freeze_sha256=sha(freeze)),indent=2)+'\n')
for index,name in enumerate(names+['normal-300s-01']):
    duration=300 if index==3 else 30;bundle=series/name;bundle.mkdir()
    run=Path('/tmp/stratadrive-m10-endurance-v5')/name
    argv=base['argv'][:]
    for flag,value in [('--freeze',freeze),('--output',run),('--endurance-seconds',duration)]:argv[argv.index(flag)+1]=str(value)
    argv+=['--resource-profile',str(root/'profiles/perception-endurance-host-v2.json')]
    case=dict(base,declared_utc=datetime.now(timezone.utc).isoformat(),attempt=1,seconds=duration,requested_intervals=duration*200,run=str(run),freeze_sha256=sha(freeze),protocol='docs/test-plan/perception-endurance-v4-protocol.md',argv=argv)
    (bundle/'case.json').write_text(json.dumps(case,indent=2)+'\n')
    print('START',name,flush=True)
    with (work/(name+'-runner.log')).open('w') as log:code=subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT).returncode
    print('SERVER EXIT',code,flush=True)
    def call(script,args,log):
        with (bundle/log).open('w') as out:return subprocess.run([str(py),str(scripts/script),*map(str,args)],stdout=out,stderr=subprocess.STDOUT).returncode
    audit=call('audit_paired_v1.py',[run,'--output',bundle/'audit.json'],'audit.log')
    shadow=call('audit_control_shadow_v1.py',[run,'--output',bundle/'shadow-integrity.json'],'shadow-integrity.log')
    replay=work/(name+'-replay')
    replay_code=call('replay_wall_startup_v1.py',['--capture',run/'capture','--binary',root/'build/m10-endurance-v3/native/tests/integration/carla/m7_1g/m7_wall_startup_replay','--scenario',root/'tests/integration/carla/scenarios/m10_endurance_hold_v1.txt','--output',replay,'--require-exact'],'replay.log')
    if (replay/'validation.json').exists():shutil.copy2(replay/'validation.json',bundle/'replay.json')
    print('AUDIT', (bundle/'audit.json').read_text()[:250], 'REPLAY',replay_code,flush=True)
    assert call('seal_endurance_v1.py',['--run',run,'--bundle',bundle,'--prior',prior],'seal.log')==0
    assert call('check_endurance_archive_v1.py',['--series',series,'--bundle',bundle,'--work',work/(name+'-archive-check')],'archive-check.log')==0
    shutil.copy2(work/(name+'-archive-check')/'validation.json',bundle/'archive-validation.json')
    print('SEALED',name,flush=True)
    # Only remove this invocation's NVMe spool after independent raw/source/verdict verification.
    assert run.parent==Path('/tmp/stratadrive-m10-endurance-v5') and run.is_dir()
    shutil.rmtree(run)
    prior=bundle/'future-exclusion.json'
    if code or audit or replay_code or shadow:
        (series/'disposition.json').write_text(json.dumps(dict(status='FAIL',failed_case=name,not_run=names[index+1:]+(['normal-300s-01'] if index<3 else []),reason='Stop after first failure for causal diagnosis; original case retained',future_exclusion=str(prior.relative_to(root))),indent=2)+'\n')
        break
else:(series/'disposition.json').write_text(json.dumps(dict(status='PASS_DIAGNOSTIC_SERIES_ONLY',future_exclusion=str(prior.relative_to(root))),indent=2)+'\n')

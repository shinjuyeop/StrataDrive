"""Bounded regression of shared owner/controller; preserve each raw run."""
import json
from pathlib import Path
import subprocess
import sys

root = Path('/d/shin/StrataDrive')
work = Path('/d/shin/stratadrive-tools/m7-source/pre-m8-refactor')
work.mkdir(exist_ok=False)
here = root / 'tests/integration/carla'
base = ['--engine', '/d/shin/stratadrive-tools/UnrealEngine_4.26',
        '--source', '/d/shin/stratadrive-tools/m7-source/carla-0.9.16',
        '--python', '/d/shin/stratadrive-tools/m7-source/m7-nodrive-venv/bin/python',
        '--fixture', '/d/shin/stratadrive-tools/m7-source/m7-1m-fixture']
results = []
for name, fault in [('normal', 'none'), ('gap', 'wall-gap')]:
    cmd = [sys.executable, str(here / 'm7_1o_run.py'), *base,
           '--runtime', str(work / ('runtime-' + name)), '--output', str(work / name),
           '--vehicle-substeps', '320', '--native-actual',
           str(root / 'build/m7-functional/tests/integration/carla/m7_1g/m7_carla_wall_owner'),
           '--solver-work', '--compact-work', '--wall-native', '--wall-step-ms', '5',
           '--wall-hv-dependency-ms', '50', '--held-steer-sleep', '--wall-inline-render',
           '--wall-nullrhi', '--scenario', str(here / 'scenarios/m7_integrated_v1.txt'),
           '--ticks', '900', '--native-fault', fault]
    with (work / (name + '-runner.log')).open('w') as log:
        completed = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)
    audit_cmd = [sys.executable, str(here / 'audit_m7_wall_carla.py'), str(work / name),
                 '--output', str(work / (name + '-audit.json'))]
    with (work / (name + '-audit.log')).open('w') as log:
        audit = subprocess.run(audit_cmd, stdout=log, stderr=subprocess.STDOUT)
    results.append(dict(name=name, argv=cmd, exit=completed.returncode,
                        audit_argv=audit_cmd, audit_exit=audit.returncode))
    (work / 'regression.json').write_text(json.dumps(results, indent=2) + '\n')
    print(name, completed.returncode, audit.returncode, flush=True)

cmd = [sys.executable, str(here / 'm7_integrated_run.py'), *base,
       '--native', str(root / 'build/m7-functional/tests/integration/carla/m7_1g/m7_wheel_shadow'),
       '--runtime', str(work / 'runtime-functional'), '--output', str(work / 'functional'),
       '--cases', 'camera-a', 'protected-sleep', '--compact-work', '--held-steer-sleep']
with (work / 'functional-runner.log').open('w') as log:
    completed = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)
results.append(dict(name='functional', argv=cmd, exit=completed.returncode))
(work / 'regression.json').write_text(json.dumps(results, indent=2) + '\n')
print('functional', completed.returncode, flush=True)

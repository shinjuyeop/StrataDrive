import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

root = Path('/d/shin/StrataDrive')
base = Path('/d/shin/stratadrive-tools/m7-source')
runtime = base/'m7-1s'
evidence = root/'docs/test-plan/evidence/m7_carla_1s'
evidence.mkdir(parents=True, exist_ok=True)
plan = [('legacy-a', 'legacy'), ('energy-a', 'energy'), ('legacy-b', 'legacy'),
        ('energy-b', 'energy'), ('zero-a', 'zero'), ('disabled-a', 'disabled'),
        ('legacy-c', 'legacy'), ('energy-c', 'energy'), ('zero-b', 'zero'),
        ('disabled-b', 'disabled'), ('ack-missing', 'ev-ack-missing'), ('command', 'command')]
results = []
for name, mode in plan:
    run = runtime/name
    out = evidence/name
    cmd = [sys.executable, str(root/'tests/integration/carla/m7_1o_run.py'),
           '--engine', '/d/shin/stratadrive-tools/UnrealEngine_4.26',
           '--source', str(base/'carla-0.9.16'), '--python', str(base/'m7-nodrive-venv/bin/python'),
           '--fixture', str(base/'m7-1m-fixture'), '--runtime', str(run), '--output', str(out),
           '--vehicle-substeps', '320']
    if mode == 'zero': cmd += ['--zero']
    elif mode == 'disabled': cmd += ['--flag-check', 'disabled']
    else:
        cmd += ['--native-actual', str(root/'build/m7-functional/tests/integration/carla/m7_1g/m7_wheel_shadow')]
        if mode != 'legacy': cmd += ['--solver-work']
        if mode in ('ev-ack-missing', 'command'): cmd += ['--native-fault', mode]
    with (runtime/(name+'-runner.log')).open('w') as log:
        proc = subprocess.run(cmd, cwd=root, stdout=log, stderr=subprocess.STDOUT)
    row = dict(name=name, mode=mode, argv=cmd, exit=proc.returncode, compressed={})
    for path in list(out.glob('*.jsonl')) + [run/'server.log', run/'client.log']:
        if not path.is_file(): continue
        dest = (path.with_suffix(path.suffix+'.gz') if path.parent == out else evidence/(name+'-'+path.name+'.gz'))
        data = path.read_bytes()
        dest.write_bytes(gzip.compress(data, compresslevel=6, mtime=0))
        assert gzip.decompress(dest.read_bytes()) == data
        row['compressed'][str(dest.relative_to(evidence))] = dict(raw_sha256=hashlib.sha256(data).hexdigest(), raw_bytes=len(data))
        if path.parent == out: path.unlink()
    results.append(row)
    (evidence/'live-suite.json').write_text(json.dumps(results, indent=2)+'\n')
    print(name, 'exit', proc.returncode, flush=True)
    if proc.returncode:
        sys.exit(proc.returncode)

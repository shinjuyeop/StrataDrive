"""Same archived raw input, separate sequential processes, no CARLA running."""
import json
from pathlib import Path
import subprocess
import sys

root = Path('/d/shin/StrataDrive')
out = root / 'build/pre-m8-refactor'
directory = root / 'docs/test-plan/evidence/m7_carla_wall_guard/carla-runtime/hv-budget-v1/runs/run01'
runner = '''import json,sys,types
from pathlib import Path
root=Path(sys.argv[1]);sys.path.insert(0,str(root/'tests/integration/carla'))
mod=types.ModuleType('measured_auditor');mod.__file__=str(root/'tests/integration/carla/audit_m7_wall_carla.py')
exec(compile(Path(sys.argv[2]).read_text(),mod.__file__,'exec'),mod.__dict__)
Path(sys.argv[4]).write_text(json.dumps(mod.audit(Path(sys.argv[3])),indent=2)+'\\n')
'''
results = {}
for label, source in [('before', out / 'audit-before.py'), ('after', root / 'tests/integration/carla/audit_m7_wall_carla.py')]:
    cmd = ['/usr/bin/time', '-f', '%e %M', '-o', str(out / (label + '-resource.txt')),
           sys.executable, '-c', runner, str(root), str(source), str(directory),
           str(out / (label + '-measured.json'))]
    subprocess.run(cmd, check=True)
    elapsed, rss = (out / (label + '-resource.txt')).read_text().split()
    results[label] = dict(elapsed_seconds=float(elapsed), max_rss_kib=int(rss))
assert (out / 'before-measured.json').read_bytes() == (out / 'after-measured.json').read_bytes()
results.update(output_identical=True, input=str(directory),
               scope='single archived 900-receipt run; audit process, not CARLA performance')
(out / 'audit-performance.json').write_text(json.dumps(results, indent=2) + '\n')
print(json.dumps(results), flush=True)

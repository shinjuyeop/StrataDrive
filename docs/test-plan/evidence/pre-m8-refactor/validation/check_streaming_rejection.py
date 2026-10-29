"""The streaming auditor must reject raw-tail damage before discarding payloads."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path('/d/shin/StrataDrive')
source = Path('/d/shin/stratadrive-tools/m7-source/pre-m8-refactor/normal')
results = []
for name in ('missing-last-substep', 'altered-last-substep', 'truncated-last-record'):
    with tempfile.TemporaryDirectory(prefix='strata-stream-audit-') as temporary:
        directory = Path(temporary)
        for path in source.iterdir():
            if path.is_file() and path.name != 'trace.jsonl':
                (directory / path.name).symlink_to(path)
        with (source / 'trace.jsonl').open() as reader, (directory / 'trace.jsonl').open('w') as writer:
            for index, line in enumerate(reader):
                if index == 0 and name != 'truncated-last-record':
                    row = json.loads(line)
                    steps = row['raw_solver']['trace']['steps']
                    if name == 'missing-last-substep':
                        steps.pop()
                    else:
                        steps[-1]['dt_s'] *= 2
                    line = json.dumps(row) + '\n'
                if index == 899 and name == 'truncated-last-record':
                    line = line[:len(line) // 2]
                writer.write(line)
        cmd = [sys.executable, str(root / 'tests/integration/carla/audit_m7_wall_carla.py'),
               str(directory), '--output', str(directory / 'audit.json')]
        completed = subprocess.run(cmd, capture_output=True, text=True)
        result = json.loads((directory / 'audit.json').read_text())
        assert completed.returncode != 0 and result['status'] == 'FAIL_AUDIT', (name, result)
        results.append(dict(case=name, exit=completed.returncode, result=result))
        print(name, result['error'], flush=True)
(root / 'build/pre-m8-refactor/streaming-rejection.json').write_text(json.dumps(results, indent=2) + '\n')

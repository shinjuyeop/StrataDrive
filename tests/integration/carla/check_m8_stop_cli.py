#!/usr/bin/env python3
"""Check terminal CLI serialization with prior stopped-wheel inputs; no physics."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from evidence_io import json_rows
from audit_m7_1q_native import frame, wire
from m8_stop_wire import stop_selection

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('directory', type=Path)
p.add_argument('binary', type=Path)
p.add_argument('--output', required=True, type=Path)
a = p.parse_args()
result = json.loads((a.directory / 'result.json').read_text())
inputs = []
for row in json_rows(a.directory / 'trace.jsonl'):
    if row.get('work_input'):
        inputs.append(row['work_input'])
    inputs.append(row['native_input'])
cmd = [str(a.binary.resolve()), '--native-solver-work', '1', '42', '7',
       str(result['binding']['actor']), '--sim-horizon-ms', '60000',
       '--speed-profile', 'v1-stop-protection']
run = subprocess.run(cmd, input='\n'.join(inputs) + '\n', text=True,
                     capture_output=True, timeout=60)
assert run.returncode == 0, run.stderr
rows = [json.loads(s) for s in run.stdout.splitlines()]
assert len(rows) == 4001
held = protected = 0
lease = causal = None
for row in rows:
    proof = row['native_export']
    admission = row['admission']
    assert admission['ok']
    assert len(proof['stop_requests']) == len(proof['stop_results']) == 3
    if proof['normal'] or admission['normal_stop']:
        actuals = [frame(wire(packet, 0 if j < 2 else 1, 7, 9), j, True,
                        require_wheel=False) for j, packet in enumerate(proof['actual'])]
        if proof['normal']:
            assert not held and not protected
            causal = [v['causal'] for v in actuals]
        else:
            assert not protected
            lease = stop_selection(proof, actuals, row['now_ns'], lease, causal)
            held += 1
    if admission['protection']:
        assert held and not admission['normal_stop'] and row['credit_mask'] == 0
        assert row['speed_terminal']['detection_ns'] == row['stop_handoff_ns'] + 100000000
        protected += 1
assert held >= 1 and protected >= 100
report = dict(status='PASS_TERMINAL_CLI_SERIALIZATION', observations=len(rows),
              held_observations=held, protected_observations=protected,
              binary_sha256=hashlib.sha256(a.binary.read_bytes()).hexdigest(),
              physics_executed=False, argv=cmd)
a.output.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))

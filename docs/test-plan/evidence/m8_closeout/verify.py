#!/usr/bin/env python3
"""Read-only M8 closeout provenance checks; no new runtime acceptance."""
import csv
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = ROOT / 'docs/test-plan/evidence'
GROUPS = ('m8_speed_pi', 'm8_speed_loop', 'm8_carla_speed', 'm8_route',
          'm8_reference', 'm8_saturation', 'm8_stop', 'm8_stop_fault', 'm8_stop30')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def verify():
    counts = {}
    for name in GROUPS:
        lines = (EVIDENCE / name / 'SHA256SUMS').read_text().splitlines()
        for line in lines:
            expected, relative = line.split('  ', 1)
            path = EVIDENCE / name / relative
            assert digest(path) == expected, str(path)
        counts[name] = len(lines)
    manifest = json.loads((EVIDENCE / 'm8_stop30/source-final-manifest.json').read_text())
    code = {p: h for p, h in manifest.items() if p.startswith(
        ('central/', 'zone/', 'vecu/', 'interfaces/', 'simulation/', 'tests/',
         'models/', 'tools/', 'cmake/', 'profiles/')) or p == 'CMakeLists.txt'}
    for relative, expected in code.items():
        assert digest(ROOT / relative) == expected, relative
    trace = list(csv.DictReader((ROOT / 'docs/test-plan/component-traceability.csv').open()))
    ids = [next(iter(row.values())) for row in trace]
    assert len(ids) == len(set(ids)), 'duplicate component IDs'
    m8_ids = [item for item in ids if item.startswith('C-M8-')]
    assert len(m8_ids) == 36, 'M8 traceability coverage'
    summary = json.loads((EVIDENCE / 'm8_stop30/results-summary.json').read_text())
    assert summary['status'] == 'PASS_SEPARATE_STOP30_NOMINAL_SIMULATION_ONLY'
    assert summary['tests']['cpp_unit_logical'] == 1217
    assert summary['tests']['python_unit'] == 237
    assert summary['tests']['asan_ubsan_affected'] == 33
    assert not summary['default_braking_budget_changed']
    commit = subprocess.check_output(['git', 'rev-parse', '457260e'], cwd=ROOT, text=True).strip()
    subprocess.run(['git', 'merge-base', '--is-ancestor', commit, 'HEAD'], cwd=ROOT, check=True)
    return dict(status='PASS_M8_CLOSEOUT_PROVENANCE', implementation_commit=commit,
                original_evidence_groups=counts, original_evidence_files=sum(counts.values()),
                unchanged_code_config_test_files=len(code), m8_component_rows=len(m8_ids),
                prior_runtime_tests=summary['tests'], new_runtime_runs=0,
                scope='Controller and fixed-fixture functional SIL only',
                full_reference_system_result='NOT RUN', wall_target_accepted=False)


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))

#!/usr/bin/env python3
"""Finite native3-ECU diagnostics campaign using the existing owner/IP runner."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CASES = ('normal', 'front-loss', 'rear-loss', 'drop-ack', 'context-delay', 'source-restart', 'rear-restart', 'collector-restart', 'both-restart', 'front-process-rejoin', 'rear-process-rejoin', 'central-process-rejoin')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output', type=Path); p.add_argument('--profile', choices=('normal', 'asan', 'tsan'), default='normal')
    p.add_argument('--cases', nargs='+', choices=CASES, default=CASES); p.add_argument('--fixed-layout', action='store_true')
    a = p.parse_args()
    if a.fixed_layout and a.profile != 'tsan': p.error('fixed-layout is TSan-only')
    output = a.output.resolve(); output.mkdir(parents=True, exist_ok=False)
    binary = ROOT/f'build/m5-someip-{a.profile}/project/tests/integration/someip/someip_front_adapter'
    rows = []
    for case in a.cases:
        destination = output/case
        command = [sys.executable, '-B', str(HERE/'front_run.py'), str(destination), '--three', '--diagnostics', '--profile', a.profile,
                   '--cases', 'central-rejoin' if case=='central-process-rejoin' else 'restart-live' if case.endswith('process-rejoin') else 'normal' if case == 'normal' else 'command-loss']
        if case in ('source-restart', 'rear-restart', 'collector-restart', 'both-restart'): command += ['--diagnostic-restart', {'source-restart':'front', 'rear-restart':'rear', 'collector-restart':'central', 'both-restart':'all'}[case], '--diagnostic-drop-ack']
        if case in ('rear-loss', 'rear-restart', 'rear-process-rejoin', 'central-process-rejoin'): command += ['--fault-zone', 'rear']
        if case == 'drop-ack': command += ['--diagnostic-drop-ack']
        if case == 'context-delay': command += ['--diagnostic-context-delay-ms', '1500']
        if a.fixed_layout: command += ['--fixed-layout']
        with (output/(case+'.run.log')).open('w') as log:
            code = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False).returncode
        audit_command = [sys.executable, '-B', str(ROOT/'tests/integration/diagnostics'/('audit_central_restart.py' if case=='central-process-rejoin' else 'audit_native_adoption.py' if case.endswith('process-rejoin') else 'audit_native_routing.py')),
                         str(destination/('central-rejoin-1' if case=='central-process-rejoin' else 'restart-live-1' if case.endswith('process-rejoin') else 'normal-1' if case == 'normal' else 'command-loss-1')), '--mutations']
        with (output/(case+'.audit.json')).open('w') as log, (output/(case+'.audit.stderr')).open('w') as err:
            audit = subprocess.run(audit_command, cwd=ROOT, stdout=log, stderr=err, check=False).returncode if code == 0 else None
        rows.append(dict(case=case, exit=code, audit_exit=audit, command=command, audit_command=audit_command))
        (output/'results.json').write_text(json.dumps(rows, indent=2)+'\n')
    (output/'manifest.json').write_text(json.dumps(dict(profile=a.profile, fixed_layout=a.fixed_layout,
        source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(), scope='Actual native3-ECU functional routing; guarded wall/Target acceptance separate'), indent=2)+'\n')
    print(json.dumps(dict(profile=a.profile, passed=sum(r['exit'] == r['audit_exit'] == 0 for r in rows), total=len(rows))))
    return 0 if all(r['exit'] == r['audit_exit'] == 0 for r in rows) else 1


if __name__ == '__main__': sys.exit(main())

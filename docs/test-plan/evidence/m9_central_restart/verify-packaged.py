#!/usr/bin/env python3
"""Verify checksums and rerun SDK-free original PCAP/journal/mutation audits."""
import hashlib
import json
from pathlib import Path
import runpy
import sys
import tarfile
import tempfile

sys.dont_write_bytecode = True
root = Path(__file__).resolve().parent
for line in (root/'SHA256SUMS').read_text().splitlines():
    expected, name = line.split('  ', 1)
    if hashlib.sha256((root/name).read_bytes()).hexdigest() != expected: raise ValueError('checksum mismatch: '+name)
sys.path.insert(0, str(root/'sources/tests/integration/diagnostics'))
auditors = {name: runpy.run_path(str(root/'sources/tests/integration/diagnostics'/file)) for name, file in
            [('routing', 'audit_native_routing.py'), ('adoption', 'audit_native_adoption.py'), ('central', 'audit_central_restart.py')]}
results = json.loads((root/'results.json').read_text())
for mode, cohort in results['functional'].items():
    with tempfile.TemporaryDirectory(prefix='stratadrive-central-audit-') as directory:
        with tarfile.open(root/cohort['archive']) as archive:
            for member in archive.getmembers():
                path = Path(member.name)
                if path.is_absolute() or '..' in path.parts or member.issym() or member.islnk(): raise ValueError('unsafe evidence member')
            archive.extractall(directory)
        profile = Path(directory)/Path(cohort['archive']).name.removesuffix('.tar.gz'); rows = json.loads((profile/'results.json').read_text()); passed = 0
        for row in rows:
            if row['exit'] != 0 or row['audit_exit'] != 0:
                print(mode, row['case'], 'FAIL preserved', row['exit'], row['audit_exit']); continue
            kind = 'central' if row['case'] == 'central-process-rejoin' else 'adoption' if row['case'].endswith('process-rejoin') else 'routing'
            case = 'central-rejoin-1' if kind == 'central' else 'restart-live-1' if kind == 'adoption' else 'normal-1' if row['case'] == 'normal' else 'command-loss-1'
            api = auditors[kind]; data = api['load'](profile/row['case']/case); report = api['judge'](data); report['mutations_rejected'] = api['mutations'](data)
            print(mode, row['case'], json.dumps(report, sort_keys=True)); passed += 1
        if passed != cohort['passed'] or len(rows) != cohort['total']: raise ValueError('changed cohort denominator')

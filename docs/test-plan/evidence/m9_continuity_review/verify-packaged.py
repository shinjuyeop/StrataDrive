#!/usr/bin/env python3
"""SDK-free integrity, native regression and local service crash-cut audit."""
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
api = {key:runpy.run_path(str(root/'sources/tests/integration/diagnostics'/file)) for key, file in [('routing','audit_native_routing.py'),('adoption','audit_native_adoption.py'),('central','audit_central_restart.py'),('review','audit_continuity_review.py')]}
results = json.loads((root/'results.json').read_text())

def extract(name, directory):
    with tarfile.open(root/name) as archive:
        for member in archive.getmembers():
            p = Path(member.name)
            if p.is_absolute() or '..' in p.parts or member.issym() or member.islnk(): raise ValueError('unsafe evidence archive')
        archive.extractall(directory)
    return Path(directory)/name.removesuffix('.tar.gz')

for mode, cohort in results['functional'].items():
    with tempfile.TemporaryDirectory(prefix='stratadrive-review-native-') as directory:
        profile = extract(cohort['archive'], directory); rows = json.loads((profile/'results.json').read_text()); passed = 0
        for row in rows:
            if row['exit'] != 0 or row['audit_exit'] != 0:
                print(mode, row['case'], 'FAIL preserved', row['exit'], row['audit_exit']); continue
            key = 'central' if row['case'] == 'central-process-rejoin' else 'adoption' if row['case'].endswith('process-rejoin') else 'routing'
            name = 'central-rejoin-1' if key == 'central' else 'restart-live-1' if key == 'adoption' else 'normal-1' if row['case'] == 'normal' else 'command-loss-1'
            d = api[key]['load'](profile/row['case']/name); report = api[key]['judge'](d); report['mutations_rejected'] = api[key]['mutations'](d); print(mode,row['case'],json.dumps(report,sort_keys=True)); passed += 1
        if (passed,len(rows)) != (cohort['passed'],cohort['total']): raise ValueError('native denominator mismatch')
for mode, cohort in results['service'].items():
    with tempfile.TemporaryDirectory(prefix='stratadrive-service-review-') as directory:
        source = extract(cohort['archive'], directory); d = api['review']['load'](source); report = api['review']['judge'](d); report['mutations_rejected'] = api['review']['mutations'](d); print(mode,'service',json.dumps(report,sort_keys=True))

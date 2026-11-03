#!/usr/bin/env python3
"""SDK-free immutable bundle integrity and final local peer service audit."""
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
api = runpy.run_path(str(root/'sources/tests/integration/diagnostics/audit_continuity_service.py'))
results = json.loads((root/'results.json').read_text())
for mode, cohort in results['service'].items():
    with tempfile.TemporaryDirectory(prefix='stratadrive-local-service-') as directory:
        with tarfile.open(root/cohort['archive']) as archive:
            for member in archive.getmembers():
                p = Path(member.name)
                if p.is_absolute() or '..' in p.parts or member.issym() or member.islnk(): raise ValueError('unsafe evidence archive')
            archive.extractall(directory)
        d = api['load'](Path(directory)/cohort['archive'].removesuffix('.tar.gz'))
        report = api['judge'](d);report['mutations_rejected'] = api['mutations'](d)
        if report != cohort['report']: raise ValueError('audit denominator mismatch: '+mode)
        print(mode, json.dumps(report, sort_keys=True))

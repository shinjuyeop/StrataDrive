#!/usr/bin/env python3
"""Audit the preserved gzip datasets without modifying this evidence bundle."""
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parent
auditor = root / 'sources/tests/integration/diagnostics/audit_startup_diagnostics.py'
reports = {}
with tempfile.TemporaryDirectory(prefix='stratadrive-startup-audit-') as target:
    for mode in ('normal', 'asan'):
        for phase in ('prepare', 'init', 'release'):
            out = Path(target) / mode / phase
            for source in (root / mode / phase).rglob('*'):
                if not source.is_file():
                    continue
                rel = source.relative_to(root / mode / phase)
                dest = out / (str(rel)[:-3] if source.suffix == '.gz' else str(rel))
                dest.parent.mkdir(parents=True, exist_ok=True)
                if source.suffix == '.gz':
                    dest.write_bytes(gzip.decompress(source.read_bytes()))
                else:
                    shutil.copy2(source, dest)
            result = subprocess.run([sys.executable, '-B', str(auditor), str(out), '--mutations'],
                                    check=True, capture_output=True, text=True)
            reports[f'{mode}/{phase}'] = json.loads(result.stdout)
print(json.dumps(reports, indent=2))

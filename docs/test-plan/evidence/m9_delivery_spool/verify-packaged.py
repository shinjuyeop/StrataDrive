#!/usr/bin/env python3
"""Verify preserved transport evidence without modifying this bundle."""
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parent
auditor = root/'sources/tests/integration/diagnostics/audit_diagnostics_delivery.py'
reports = {}
with tempfile.TemporaryDirectory(prefix='stratadrive-delivery-audit-') as target:
    for mode in ('normal', 'asan'):
        out = Path(target)/mode
        for source in (root/mode).rglob('*'):
            if not source.is_file():
                continue
            relative = source.relative_to(root/mode)
            dest = out/(str(relative)[:-3] if source.suffix == '.gz' else str(relative))
            dest.parent.mkdir(parents=True, exist_ok=True)
            if source.suffix == '.gz':
                dest.write_bytes(gzip.decompress(source.read_bytes()))
            else:
                shutil.copy2(source, dest)
        result = subprocess.run([sys.executable, '-B', str(auditor), str(out), '--mutations'],
                                capture_output=True, text=True, check=True)
        reports[mode] = json.loads(result.stdout)
print(json.dumps(reports, indent=2))

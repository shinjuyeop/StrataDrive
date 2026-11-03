#!/usr/bin/env python3
"""Audit compressed live SOME/IP evidence without modifying this bundle."""
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parent
auditor = root/'sources/tests/integration/diagnostics/audit_someip_diagnostics.py'
reports = {}
with tempfile.TemporaryDirectory(prefix='stratadrive-someip-audit-') as target:
    for mode, cases in [('normal', ('normal', 'loss', 'drop-ack', 'restart')),
                        ('asan', ('normal', 'loss', 'drop-ack', 'restart')), ('tsan', ('loss',))]:
        for case in cases:
            source_root = root/mode/case; out = Path(target)/mode/case
            for source in source_root.rglob('*'):
                if not source.is_file(): continue
                relative = source.relative_to(source_root)
                dest = out/(str(relative)[:-3] if source.suffix == '.gz' else str(relative)); dest.parent.mkdir(parents=True, exist_ok=True)
                if source.suffix == '.gz': dest.write_bytes(gzip.decompress(source.read_bytes()))
                else: shutil.copy2(source, dest)
            result = subprocess.run([sys.executable, '-B', str(auditor), str(out), '--mutations'], capture_output=True, text=True, check=True)
            reports[f'{mode}/{case}'] = json.loads(result.stdout)
print(json.dumps(reports, indent=2))

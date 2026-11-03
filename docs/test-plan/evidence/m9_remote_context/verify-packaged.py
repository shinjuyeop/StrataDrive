#!/usr/bin/env python3
"""Verify this immutable component evidence using its preserved auditor."""
import hashlib
from pathlib import Path
import runpy
import sys

root = Path(__file__).resolve().parent
for line in (root / 'SHA256SUMS').read_text().splitlines():
    digest, name = line.split('  ', 1)
    if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
        raise ValueError(f'checksum mismatch: {name}')
sys.path.insert(0, str(root / 'sources/tests/integration/diagnostics'))
auditor = runpy.run_path(str(root / 'sources/tests/integration/diagnostics/audit_remote_context.py'))
for profile in ('normal', 'asan'):
    print(profile, auditor['audit'](root / profile), 'mutations rejected', auditor['mutations'](root / profile))

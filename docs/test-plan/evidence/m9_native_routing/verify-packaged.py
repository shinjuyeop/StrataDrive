#!/usr/bin/env python3
"""Verify preserved hashes and independently audit all final native datasets."""
import hashlib
import json
from pathlib import Path
import runpy
import sys
import tarfile
import tempfile

root = Path(__file__).resolve().parent
for line in (root/'SHA256SUMS').read_text().splitlines():
    expected, name = line.split('  ', 1)
    if hashlib.sha256((root/name).read_bytes()).hexdigest() != expected:
        raise ValueError('checksum mismatch: '+name)
sys.path.insert(0, str(root/'sources/tests/integration/diagnostics'))
auditor = runpy.run_path(str(root/'sources/tests/integration/diagnostics/audit_native_routing.py'))
manifest = json.loads((root/'manifest.json').read_text())
for mode, name in manifest['functional_archives'].items():
    with tempfile.TemporaryDirectory(prefix='stratadrive-native-evidence-') as directory:
        target = Path(directory)
        with tarfile.open(root/name) as archive:
            for member in archive.getmembers():
                path = Path(member.name)
                if path.is_absolute() or '..' in path.parts or member.issym() or member.islnk():
                    raise ValueError('unsafe evidence member')
            archive.extractall(target)
        profile = target/Path(name).name.removesuffix('.tar.gz')
        rows = json.loads((profile/'results.json').read_text())
        for row in rows:
            if row['exit'] != 0 or row['audit_exit'] != 0:
                raise ValueError('failed final case')
            case = profile/row['case']/('normal-1' if row['case'] == 'normal' else 'command-loss-1')
            data = auditor['load'](case); result = auditor['judge'](data)
            result['mutations_rejected'] = auditor['mutations'](data)
            print(mode, row['case'], json.dumps(result, sort_keys=True))

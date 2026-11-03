#!/usr/bin/env python3
"""Verify all preserved hashes and independently re-audit accepted raw datasets."""
import hashlib
import json
from pathlib import Path
import runpy
import sys
import tarfile
import tempfile
import zlib

root = Path(__file__).resolve().parent
for line in (root/'SHA256SUMS').read_text().splitlines():
    expected, name = line.split('  ', 1)
    if hashlib.sha256((root/name).read_bytes()).hexdigest() != expected:
        raise ValueError('checksum mismatch: '+name)
sys.path.insert(0, str(root/'sources/tests/integration/diagnostics'))
auditor = runpy.run_path(str(root/'sources/tests/integration/diagnostics/audit_native_routing.py'))
manifest = json.loads((root/'manifest.json').read_text())
results = json.loads((root/'results.json').read_text())


def extract(name, target):
    with tarfile.open(root/name) as archive:
        for member in archive.getmembers():
            path = Path(member.name)
            if path.is_absolute() or '..' in path.parts or member.issym() or member.islnk():
                raise ValueError('unsafe evidence member')
        archive.extractall(target)
    return target/Path(name).name.removesuffix('.tar.gz')


for mode, name in manifest['functional_archives'].items():
    with tempfile.TemporaryDirectory(prefix='stratadrive-restart-audit-') as directory:
        profile = extract(name, Path(directory))
        rows = json.loads((profile/'results.json').read_text()); passed = 0
        for row in rows:
            if row['exit'] != 0 or row['audit_exit'] != 0:
                print(mode, row['case'], 'FAIL preserved', row['exit'], row['audit_exit'])
                continue
            case = profile/row['case']/('normal-1' if row['case'] == 'normal' else 'command-loss-1')
            data = auditor['load'](case); result = auditor['judge'](data)
            result['mutations_rejected'] = auditor['mutations'](data)
            print(mode, row['case'], json.dumps(result, sort_keys=True)); passed += 1
        if passed != results['functional'][mode]['passed'] or len(rows) != results['functional'][mode]['total']:
            raise ValueError('native denominator changed')
for name in ('process-final.tar.gz', 'process-final-asan.tar.gz'):
    with tempfile.TemporaryDirectory(prefix='stratadrive-restart-process-') as directory:
        home = extract(name, Path(directory)); journal = auditor['journal']; rows = auditor['csv_rows']; require = auditor['require']
        source, replica, merged = [journal(home/p, bytes) for p in ('fresh', 'replica', 'merged')]
        require(source == replica == merged and len(source) == 2, 'process original source/replica/merged bytes')
        require(journal(home/'replica-before-reconcile', bytes) == source, 'replica-only durable prefix before recovery')
        cuts = rows(home/'cuts.csv')
        require([r['phase'] for r in cuts] == ['source', 'replica', 'merged'] and len({r['pid'] for r in cuts}) == 3 and
                all(r['committed'] == '1' and r['signal'] == '9' for r in cuts), 'three observed commits and actual SIGKILL')
        require(rows(home/'restart-projection.csv') == [dict(condition='0', count='1', generation='1', cleared='0')], 'process restart projection Unknown/count1')
        data_seen = set(); ack_seen = set()
        for packet in (home/'wire').glob('*.bin'):
            kind, stream, ordinal, payload = auditor['wire'](packet.read_bytes())
            require(stream == 6001 and 1 <= ordinal <= 2, 'process exact stream/ordinal')
            require(payload == source[ordinal-1] if kind == 1 else int.from_bytes(payload, 'little') == zlib.crc32(source[ordinal-1]), 'process exact canonical Event/ACK')
            (data_seen if kind == 1 else ack_seen).add(ordinal)
        require(data_seen == ack_seen == {1, 2}, 'process all original ordinals replayed and ACKed')
        print(name, 'PASS; three SIGKILL cuts; two original events; Unknown/count1')

#!/usr/bin/env python3
"""Verify preserved hashes, native PCAP/journals and explicit volatile-loss export."""
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
auditors = {False: runpy.run_path(str(root/'sources/tests/integration/diagnostics/audit_native_routing.py')),
            True: runpy.run_path(str(root/'sources/tests/integration/diagnostics/audit_native_adoption.py'))}
manifest = json.loads((root/'manifest.json').read_text()); results = json.loads((root/'results.json').read_text())


def extract(name, target):
    with tarfile.open(root/name) as archive:
        for member in archive.getmembers():
            path = Path(member.name)
            if path.is_absolute() or '..' in path.parts or member.issym() or member.islnk():
                raise ValueError('unsafe evidence member')
        archive.extractall(target)
    return target/Path(name).name.removesuffix('.tar.gz')


for mode, name in manifest['functional_archives'].items():
    with tempfile.TemporaryDirectory(prefix='stratadrive-adoption-audit-') as directory:
        profile = extract(name, Path(directory)); rows = json.loads((profile/'results.json').read_text()); passed = 0
        for row in rows:
            if row['exit'] != 0 or row['audit_exit'] != 0:
                print(mode, row['case'], 'FAIL preserved', row['exit'], row['audit_exit']); continue
            full = row['case'].endswith('process-rejoin'); audit = auditors[full]
            case = profile/row['case']/('restart-live-1' if full else 'normal-1' if row['case'] == 'normal' else 'command-loss-1')
            data = audit['load'](case); result = audit['judge'](data); result['mutations_rejected'] = audit['mutations'](data)
            print(mode, row['case'], json.dumps(result, sort_keys=True)); passed += 1
        if passed != results['functional'][mode]['passed'] or len(rows) != results['functional'][mode]['total']:
            raise ValueError('native denominator changed')
for name in ('volatile-normal-final.tar.gz', 'volatile-asan-final.tar.gz'):
    with tempfile.TemporaryDirectory(prefix='stratadrive-volatile-audit-') as directory:
        home = extract(name, Path(directory)); api = auditors[True]; read = api['journal']; parse = api['event']; require = api['require']; csv = api['csv_rows']
        old = read(home/'old-source', bytes); fresh = read(home/'new-source', bytes); lost = parse((home/'volatile-event.bin').read_bytes())
        require(len(old) == 1 and parse(old[0])['kind'] == 6 and len(fresh) == 2 and parse(fresh[0])['kind'] == 6, 'only original committed contexts preserved')
        require(all(parse(raw)['_id'] != lost['_id'] for raw in old+fresh), 'volatile lost event never fabricated as durable history')
        gap = parse(fresh[1]); require(gap['kind'] == 1 and gap['code'] == 0x5001 and gap['_id'] == (10, (1 << 32)|30, 1) and
                                     gap['epoch'] == 2 and gap['_before'] == 1 and gap['_after'] == 2 and gap['_unknown'] and gap['_unmapped'] and gap['measured'] == 0,
                                     'fresh producer with explicit unverified continuity and no invented loss count')
        lifecycle = [parse(raw) for raw in read(home/'producer-lifecycle', bytes)]
        require([e['kind'] for e in lifecycle] == [9, 9, 0] and [e['event_sequence'] for e in lifecycle] == [1, 3, 4] and
                all(e['_id'][:2] == (10, 9001) for e in lifecycle), 'durable unique incarnation before new event')
        cuts = csv(home/'cuts.csv'); require(len(cuts) == 1 and cuts[0]['phase'] == 'volatile-queued' and int(cuts[0]['pid']) > 0 and cuts[0]['committed'] == '1' and cuts[0]['signal'] == '9', 'actual SIGKILL after publish before writer drain')
        print(name, 'PASS; volatile event absent; fresh producer; explicit unknown continuity')

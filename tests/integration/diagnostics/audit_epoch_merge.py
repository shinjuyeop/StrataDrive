#!/usr/bin/env python3
"""Independently check frozen native originals, three streams and the merge barrier."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import struct
import tempfile
import zlib
from audit_control_diagnostics import event, require
from audit_epoch_delivery import family, metadata


def rows(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def audit(folder):
    result = json.loads((folder/'result.json').read_text())
    require(result['pass'] and not result['forced_cleanup'] and result['capture_exit'] == 0, 'runtime verdict')
    require({(p['role'], p['generation']): p['exit'] for p in result['processes']} ==
            {('replica', 1): -9, ('publisher', 1): 0, ('replica', 2): 0}, 'exact injected exits')
    originals = [bytes.fromhex(line) for line in (folder/'original-events.hex').read_text().splitlines()]
    require(len({event(raw)['_id'] for raw in originals}) == len(originals), 'original identity collision')
    source_union, streams = {}, []
    for i, producer in enumerate((7, 30, 31)):
        source, info = family(folder/'source-store'/str(i))
        replica, _ = family(folder/'replica-store'/str(i))
        before, _ = family(folder/'replica-before-restart'/str(i))
        expected = [raw for epoch in (1, 2) for raw in originals
                    if event(raw)['epoch'] == epoch and (event(raw)['kind'] == 6 or event(raw)['_id'][1] == producer)]
        require(source == expected == replica and source[:len(before)] == before, 'original/source/replica prefix mismatch')
        require(info['stream'] == 7200+i and info['segments'] == 2, 'source rollover/identity')
        streams.append(info)
        for raw in source:
            identity = event(raw)['_id']
            require(identity not in source_union or source_union[identity] == raw, 'shared context changed')
            source_union[identity] = raw
    merged, info = family(folder/'replica-store/merged')
    before, _ = family(folder/'replica-before-restart/merged')
    require({event(raw)['_id']: raw for raw in merged} == source_union and len(merged) == len(source_union), 'merged lost or duplicated an original')
    epochs = [event(raw)['epoch'] for raw in merged]
    require(epochs == sorted(epochs) and set(epochs) == {1, 2} and info['segments'] == 2, 'merge checkpoint crossed an old tail')
    require(event(before[-1])['epoch'] == 1 and merged[:len(before)] == before, 'restart crossed barrier')
    membership = struct.unpack('<5Q', metadata(folder/'replica-store/merged/merge-sources'))
    require(membership == (1, 7900, 7200, 7201, 7202), 'fixed membership changed')
    first = rows(folder/'replica-1.csv');second = rows(folder/'replica-2.csv')
    require(all(int(r['merged_epoch']) >= int(r['epoch']) for r in first+second if r['ack_sent'] == '1'), 'ACK before merged epoch commit')
    held = [r for r in first if r['epoch'] == '2' and r['ack_sent'] == '0' and r['merged_epoch'] == '1']
    require(held, 'no original future boundary held')
    require(any(r['stream'] == '7201' and r['epoch'] == '1' and r['ordinal'] != '1' and r['ack_sent'] == '1' and r['merged_epoch'] == '1'
                for r in second), 'delayed old tail missing after restart')
    require(any(r['epoch'] == '2' and r['result'] == '1' and r['ack_sent'] == '1' for r in second), 'held boundary did not receive duplicate ACK')
    for receipt in rows(folder/'receipts.csv'):
        index = int(receipt['stream'])-7200
        require(int(receipt['committed']) == int(receipt['acknowledged']) == streams[index]['entries'], 'sender incomplete')
    require(len(rows(folder/'receipts.csv')) == 3 and {r['stream'] for r in rows(folder/'receipts.csv')} == {'7200', '7201', '7202'}, 'missing source receipt')
    faults = [event(raw) for raw in merged if event(raw)['kind'] == 1]
    passed = [event(raw) for raw in merged if event(raw)['kind'] == 5]
    require(faults and passed and {r['_related'] for r in passed} == {r['_id'] for r in faults}, 'native recovery lost original faults')
    records = rows(folder/'merged-records.csv')
    require(len(records) == len(faults) and all(r['count'] == '1' and r['generation'] == '1' and r['cleared'] == '0' for r in records), 'DTC count inflated')
    require((folder/'physical.csv').read_bytes() == (folder/'baseline-physical.csv').read_bytes(), 'diagnostics changed physics')
    for name in ('publisher-sdk.csv', 'replica-2-sdk.csv'):
        stats = rows(folder/name)
        require(len(stats) == 3 and all(r['dropped'] == r['rejected'] == '0' and int(r['highwater']) <= 8 for r in stats), 'SDK ingress errors')
    return dict(ok=True, streams=streams, merged=info, old_prefix_at_kill=len(before), faults=len(faults), passed=len(passed),
                physical_samples=len(rows(folder/'physical.csv')), scope='frozen native Central/Front/Rear events over real SOME/IP; fixed membership')


def mutations(folder):
    rejected = []
    for case in ('original_changed', 'membership_dropped', 'missing_old_segment', 'premature_ack', 'missing_delayed_tail', 'unexpected_exit'):
        with tempfile.TemporaryDirectory(prefix='stratadrive-merge-audit-') as name:
            target = Path(name)/'cohort';shutil.copytree(folder, target)
            if case == 'original_changed':
                path = target/'original-events.hex';lines = path.read_text().splitlines();lines.pop(0);path.write_text('\n'.join(lines)+'\n')
            elif case == 'membership_dropped':
                path = target/'replica-store/merged/merge-sources';raw = path.read_bytes()[:-16];path.write_bytes(raw+struct.pack('<Q', zlib.crc32(raw)))
            elif case == 'missing_old_segment':
                shutil.rmtree(target/'replica-store/merged/00000001')
            elif case in ('premature_ack', 'missing_delayed_tail'):
                path = target/('replica-1.csv' if case == 'premature_ack' else 'replica-2.csv');values = rows(path)
                fields = list(values[0])
                for r in values:
                    if case == 'premature_ack' and r['epoch'] == '2':r['ack_sent'] = '1'
                    if case == 'missing_delayed_tail' and r['stream'] == '7201' and r['epoch'] == '1':r['ack_sent'] = '0'
                with path.open('w') as stream:
                    writer = csv.DictWriter(stream, fields);writer.writeheader();writer.writerows(values)
            else:
                path = target/'result.json';result = json.loads(path.read_text());result['processes'][0]['exit'] = 0;path.write_text(json.dumps(result))
            try:
                audit(target)
            except (ValueError, OSError, struct.error) as error:
                rejected.append(dict(mutation=case, rejected=True, reason=str(error)))
            else:
                raise ValueError('audit accepted mutation: '+case)
    return rejected


def main():
    parser = argparse.ArgumentParser(description=__doc__);parser.add_argument('directory', type=Path)
    parser.add_argument('--output', type=Path, required=True);parser.add_argument('--mutations', action='store_true');args = parser.parse_args()
    result = audit(args.directory)
    if args.mutations:result['mutations'] = mutations(args.directory)
    args.output.write_text(json.dumps(result, indent=2)+'\n');print(json.dumps(result))


if __name__ == '__main__':
    main()

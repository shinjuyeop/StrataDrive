#!/usr/bin/env python3
"""Independent canonical-byte audit of the opt-in SOME/IP epoch-restart cohort."""
import argparse
import csv
import json
import shutil
import tempfile
from pathlib import Path
import struct
import zlib
from audit_control_diagnostics import checksum, event, journal, require


def metadata(path):
    raw = path.read_bytes()
    require(len(raw) >= 16 and raw[:8] == b'SDEPOCH\x01', 'family metadata schema')
    require(struct.unpack_from('<Q', raw, len(raw)-8)[0] == zlib.crc32(raw[:-8]), 'family metadata CRC')
    return raw[8:-8]


def family(path):
    require(not (path/'pending').exists() and not (path/'incomplete').exists(), 'incomplete family')
    manifest = metadata(path/'manifest')
    require(len(manifest) == 56, 'family manifest size')
    identity, limit, records, occurrences, clears, threshold, maximum = struct.unpack('<7Q', manifest)
    pointer = metadata(path/'current')
    require(len(pointer) == 16, 'family pointer size')
    generation, base = struct.unpack('<QQ', pointer)
    require(identity and 0 < generation <= maximum and 0 < threshold < limit, 'family bounds')
    original, counts = [], []
    for segment in range(1, generation+1):
        folder = path/f'{segment:08d}'
        store = (folder/'manifest').read_bytes()
        checksum(store, b'SDDMAN\x01\x00')
        require(struct.unpack_from('<Q', store, 8)[0] == identity+segment-1, 'segment identity')
        require(struct.unpack_from('<5I', store, 16) == (limit, records, occurrences, clears, 4), 'segment policy')
        require(not (folder/'pending').exists(), 'segment pending intent')
        rows = journal(folder, decoder=lambda payload: payload)
        require(0 < len(rows) <= limit, 'segment entry bounds')
        require(all(payload[0] == 0 for payload in rows), 'transport family is event only')
        if segment > 1:
            checkpoint = metadata(folder/'checkpoint')
            require(checkpoint, 'missing checkpoint')
            first = event(rows[0])
            require(first['kind'] in (6, 9) and first['epoch'] > event(original[-1])['epoch'], 'actual newer session boundary')
        if segment == generation:
            require(len(original) == base, 'global ordinal base')
        counts.append(len(rows));original.extend(rows)
    return original, dict(stream=identity, segments=generation, entries=len(original), active_entries=counts[-1], limit=limit)


def audit(folder):
    result = json.loads((folder/'result.json').read_text())
    require(result['pass'] and not result['forced_cleanup'] and result['capture_exit'] == 0, 'runtime verdict')
    exits = {(p['role'], p['generation']): p['exit'] for p in result['processes']}
    require(exits == {('replica', 1): -9, ('publisher', 1): 0, ('replica', 2): 0}, 'exact injected process exits')
    source, source_info = family(folder/'source-store')
    replica, replica_info = family(folder/'replica-store')
    before, _ = family(folder/'replica-before-restart')
    require(source == replica and source[:len(before)] == before, 'source/replica canonical mismatch')
    require(source_info['segments'] >= 2 and replica_info['segments'] >= 2, 'no rollover exercised')
    rollover = event(before[-1])
    require(rollover['kind'] == 6 and rollover['epoch'] == 2, 'kill was not at committed new session')
    with (folder/'replica-2.csv').open() as stream:
        receipts = list(csv.DictReader(stream))
    require(any(int(row['ordinal']) == len(before) and int(row['result']) == 1 and int(row['ack_sent']) == 1 for row in receipts), 'lost rollover ACK was not retried as duplicate')
    decoded = [event(payload) for payload in source]
    faults = [e for e in decoded if e['kind'] == 1]
    passed = [e for e in decoded if e['kind'] == 5]
    require(len(faults) == 2 and len(passed) == 1, 'native fault/recovery/recurrence events')
    require(passed[0]['_related'] == faults[0]['_id'] and passed[0]['epoch'] == 2, 'recovery lost original occurrence')
    for name in ('source-records.csv', 'replica-records.csv'):
        with (folder/name).open() as stream:
            records = list(csv.DictReader(stream))
        require(len(records) == 1 and int(records[0]['count']) == 2 and int(records[0]['generation']) == 1 and int(records[0]['cleared']) == 0, 'DTC history changed')
    publisher = json.loads((folder/'publisher.json').read_text())
    require(publisher['pass'] and publisher['on_off_identical'] and publisher['events'] == publisher['acknowledged'] == len(source), 'sender final receipt')
    require((folder/'physical.csv').read_bytes() == (folder/'baseline-physical.csv').read_bytes(), 'diagnostics changed plant trace')
    for name in ('publisher-sdk.json', 'replica-2-sdk.json'):
        stats = json.loads((folder/name).read_text())
        require(stats['dropped'] == 0 and stats['rejected'] == 0 and stats['highwater'] <= 8, 'SDK ingress error')
    return dict(ok=True, source=source_info, replica=replica_info, kill_ordinal=len(before), faults=len(faults), passed=len(passed), physical_samples=publisher['physical_samples'])


def mutations(folder):
    rejected = []
    for case in ('pointer_crc', 'missing_predecessor', 'valid_crc_payload_mutation', 'missing_duplicate_ack', 'physical_changed', 'unexpected_exit'):
        with tempfile.TemporaryDirectory(prefix='stratadrive-epoch-audit-') as name:
            target = Path(name)/'cohort';shutil.copytree(folder, target)
            if case == 'pointer_crc':
                path = target/'source-store/current';raw = bytearray(path.read_bytes());raw[-1] ^= 1;path.write_bytes(raw)
            elif case == 'missing_predecessor':
                shutil.rmtree(target/'source-store/00000001')
            elif case == 'valid_crc_payload_mutation':
                path = target/'replica-store/00000002/journal';raw = bytearray(path.read_bytes())
                cursor = 0
                while cursor < len(raw):
                    length = struct.unpack_from('<I', raw, cursor+16)[0];end = cursor+length+24
                    if end == len(raw):
                        raw[end-5] ^= 1
                        struct.pack_into('<I', raw, end-4, zlib.crc32(raw[cursor:end-4]))
                    cursor = end
                path.write_bytes(raw)
            elif case == 'missing_duplicate_ack':
                path = target/'replica-2.csv';lines = path.read_text().splitlines()
                path.write_text('\n'.join([lines[0]]+[line for line in lines[1:] if line.split(',')[2] != '1'])+'\n')
            elif case == 'physical_changed':
                with (target/'physical.csv').open('a') as stream:stream.write('changed\n')
            else:
                path = target/'result.json';result = json.loads(path.read_text());result['processes'][1]['exit'] = 1;path.write_text(json.dumps(result))
            try:
                audit(target)
            except (ValueError, OSError) as error:
                rejected.append(dict(mutation=case, rejected=True, reason=str(error)))
            else:
                raise ValueError('audit accepted mutation: '+case)
    return rejected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mutations', action='store_true')
    args = parser.parse_args()
    result = audit(args.directory)
    if args.mutations:result['mutations'] = mutations(args.directory)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()

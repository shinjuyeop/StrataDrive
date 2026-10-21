#!/usr/bin/env python3
"""Offline audit of extracted raw evidence. Never modifies raw outcomes."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import socket
import struct


def records(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def ip_streams(path):
    """Reassemble observed TCP sequence ranges; parse complete SOME/IP frames only."""
    data = path.read_bytes()
    assert data[:4] == b'\xd4\xc3\xb2\xa1'
    flows = {}
    at = 24
    while at < len(data):
        _, _, size, _ = struct.unpack_from('<IIII', data, at)
        packet = data[at + 16:at + 16 + size]
        at += 16 + size
        if len(packet) < 54 or packet[12:14] != b'\x08\x00':
            continue
        ip = packet[14:]
        h = (ip[0] & 15) * 4
        if ip[9] != 6:
            continue
        tcp = ip[h:struct.unpack_from('!H', ip, 2)[0]]
        if len(tcp) < 20:
            continue
        src, dst, seq = struct.unpack_from('!HHI', tcp)
        payload = tcp[(tcp[12] >> 4) * 4:]
        if not payload or not ({src, dst} & {30501, 30502, 30503, 30504}):
            continue
        key = (socket.inet_ntoa(ip[12:16]), src, socket.inet_ntoa(ip[16:20]), dst)
        flows.setdefault(key, {})[seq] = payload
    counts = {}
    for key, chunks in flows.items():
        buf = bytearray()
        end = None
        for seq, chunk in sorted(chunks.items()):
            if end is not None and seq > end:
                break  # A gap is not evidence of a complete frame.
            skip = 0 if end is None else max(0, end - seq)
            buf.extend(chunk[skip:])
            end = max(end or 0, seq + len(chunk))
        at = 0
        while at + 16 <= len(buf):
            service, method, length = struct.unpack_from('!HHI', buf, at)
            if length < 8 or at + 8 + length > len(buf):
                break
            if 0x5344 <= service <= 0x5347:
                label = f'{key[0]}:{key[1]}->{key[2]}:{key[3]} service={service:04x} method={method:04x} type={buf[at+14]:02x}'
                counts[label] = counts.get(label, 0) + 1
            at += 8 + length
    return counts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('raw', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    output = {'raw_outcomes_are_immutable': True, 'cohorts': [], 'final_cases': [],
              'normal_latency': {}, 'ip_sample': {}}
    for path in sorted((args.raw / 'runtime').glob('*/results.json')):
        rows = json.loads(path.read_text())
        name = path.parent.name
        kind = ('completed_cpp_campaign4' if name.endswith('-final4') else
                'runner_fix_restart_regression' if '-reset-' in name else
                'legacy_pilot_binding_regression' if name.startswith('someip-pilot-binding') else
                'isolated_sdk_logging_comparison' if name.endswith('sdk-observed') else 'development')
        output['cohorts'].append({'name': name, 'kind': kind, 'total': len(rows),
                                  'raw_pass': sum(r['exit'] == 0 for r in rows),
                                  'raw_fail': sum(r['exit'] != 0 for r in rows), 'rows': rows})
        if kind not in ('completed_cpp_campaign4', 'runner_fix_restart_regression'):
            continue
        for row in rows:
            folder = path.parent / f"{row['case']}-{row['repeat']}"
            result = json.loads((folder / 'result.json').read_text())
            entry = dict(cohort=name, case=row['case'], repeat=row['repeat'], raw_exit=row['exit'],
                         forced_cleanup=result['forced_cleanup'],
                         sanitizer_diagnostics=result['sanitizer_diagnostics'],
                         expected_sdk_faults=result.get('expected_sdk_faults', []))
            entry['processes'] = result['processes']
            entry['protection_and_credit_events'] = []
            for events in sorted(folder.glob('*.events.csv')):
                rs = records(events)
                selected = [r for r in rs if any(s in r['event'] for s in ('protect', 'expired', 'epoch-issued', 'armed'))]
                for r in selected:
                    entry['protection_and_credit_events'].append(dict(file=events.name, **r))
                credits = [r for r in rs if r['event'] == 'credit-issued']
                if credits:
                    entry['protection_and_credit_events'].append(dict(file=events.name, **credits[-1]))
            output['final_cases'].append(entry)
            if row['case'] == 'normal':
                central = records(folder / 'central-1.transport.csv')
                front = records(folder / 'front-1.transport.csv')
                accepted = [r for r in central if r['event'] == 'central-result-accepted' and r['peer'] == '0' and r['decision'] == '1']
                latency = [int(r['ns']) - int(r['sent']) for r in accepted]
                key = lambda r: tuple(r[k] for k in ('epoch', 'token', 'operation'))
                requests = {key(r): r for r in central if r['event'] == 'central-enqueued' and r['peer'] == '0'}
                received = {key(r): r for r in front if r['event'] == 'zone-received'}
                immutable = ('sent', 'deadline', 'original_source', 'inner_deadline')
                for result in accepted:
                    request = requests[key(result)]
                    arrival = received[key(result)]
                    assert all(request[k] == arrival[k] == result[k] for k in immutable)
                    assert int(result['ns']) < min(int(result['deadline']), int(result['sent']) + 20_000_000)
                output['normal_latency'][f'{name}/normal-{row["repeat"]}'] = {
                    'sample_count': len(latency), 'min_ns': min(latency), 'max_ns': max(latency),
                    'original_times_correlated_and_within_envelope': True,
                    'meaning': 'Central acceptance of Front Zone result minus original sent; not physical completion'}
    sample = args.raw / 'runtime/someip-adapter-normal-final4/normal-1'
    output['ip_sample'] = ip_streams(sample / 'traffic.pcap')
    output['all_raw_totals'] = {key: sum(c[key] for c in output['cohorts']) for key in ('total', 'raw_pass', 'raw_fail')}
    args.output.write_text(json.dumps(output, indent=2) + '\n')
    print(output['all_raw_totals'])


if __name__ == '__main__':
    main()

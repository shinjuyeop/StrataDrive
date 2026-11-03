#!/usr/bin/env python3
"""Independent wire CRC, durable prefix, replay and native source identity audit."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import struct
import zlib
from audit_control_diagnostics import checksum, csv_rows, event, journal, require


def load(root):
    stores = {name: journal(root/name, decoder=bytes) for name in
              ('source', 'replica-lost-ack', 'replica-delivered', 'replica')}
    contexts = {}
    for name in stores:
        m = (root/name/'manifest').read_bytes()
        contexts[name] = (int.from_bytes(m[8:16], 'little'), int.from_bytes(m[32:36], 'little'))
    return dict(stores=stores, contexts=contexts,
                logs=[csv_rows(root/f'round{i}.csv') for i in (1, 2, 3)],
                packets={p.name: p.read_bytes() for p in (root/'wire').glob('*.bin')},
                lost_ack=(root/'lost-ack.bin').read_bytes())


def frame(raw):
    require(40 <= len(raw) <= 2048, 'wire size')
    checksum(raw, b'SDDWIR\x01\x00')
    kind, reserved, registry, stream, ordinal, length = struct.unpack_from('<B3sIQQI', raw, 8)
    require(kind in (1, 2) and reserved == b'\0\0\0' and registry == 3 and stream == 6001 and
            1 <= ordinal <= 19 and length == len(raw)-40, 'wire context/kind/length')
    payload = raw[36:-4]
    require((kind == 1 and payload[:3] == b'\0\x01\0') or (kind == 2 and length == 4), 'event-only data or ACK')
    return kind, ordinal, payload


def judge(d):
    source = d['stores']['source']
    require(hashlib.sha256(b''.join(source)).hexdigest() ==
            '66ca61316afe0084384be22af4722b10e88e336c03d998894d49f9cf55f56b89', 'immutable native fixture identity')
    require(all(c == (6001, 3) for c in d['contexts'].values()), 'provisioned stream/registry')
    require(len(source) == 19 and d['stores']['replica-lost-ack'] == source[:2] and
            d['stores']['replica-delivered'] == d['stores']['replica'] == source, 'durable exact source prefixes')
    events = [event(p) for p in source]
    require(events[0]['kind'] == 9 and events[1]['kind'] == 1 and events[1]['code'] == 0x4101,
            'original startup Attempt and fault')
    require(sum(e['kind'] == 1 for e in events) == sum(e['kind'] == 5 for e in events) == 1 and
            [e['epoch'] for e in events if e['kind'] == 6] == [2], 'original one fault and qualified new release')
    require(len(d['logs']) == 3 and [len(rows) for rows in d['logs']] == [2, 21, 19], 'round denominators')
    pids = []
    for round_number, rows in enumerate(d['logs'], 1):
        receiver = {int(r['receiver_pid']) for r in rows}; sender = {int(r['sender_pid']) for r in rows}
        require(len(receiver) == len(sender) == 1 and min(receiver | sender) > 0 and receiver.isdisjoint(sender), 'separate process owners')
        pids += list(receiver | sender)
        if round_number == 2:
            for row, ordinal, result in zip(rows[:2], (19, 0), (5, 2)):
                require(int(row['ordinal']) == ordinal and int(row['result']) == result and int(row['watermark']) == 2 and
                        int(row['ack_ready']) == int(row['ack_sent']) == 0 and int(row['condition']) == 0 and
                        int(row['count']) == int(row['generation']) == 1 and int(row['cleared']) == 0, 'future/corrupt datagrams cannot commit or ACK')
            rows = rows[2:]
        for ordinal, r in enumerate(rows, 1):
            values = {k: int(v) for k, v in r.items()}
            duplicate = round_number == 3 or (round_number == 2 and ordinal <= 2)
            watermark = 19 if round_number == 3 else max(2, ordinal) if round_number == 2 else ordinal
            require(values['ordinal'] == ordinal and values['result'] == int(duplicate) and
                    values['watermark'] == watermark and values['watermark'] >= ordinal and values['ack_ready'] == 1 and
                    values['ack_sent'] == int(not (round_number == 1 and ordinal == 2)), 'durable ACK order and result')
            if round_number == 1 and ordinal == 1:
                require(values['condition'] == -1 and values['count'] == 0, 'Attempt alone has no DTC')
            else:
                require(values['count'] == values['generation'] == 1 and values['cleared'] == 0, 'retained one occurrence and uncleared history')
            if round_number == 1 and ordinal == 2:
                require(values['condition'] == 1, 'first fault Failed before process exit')
            if round_number == 3 or (round_number == 2 and ordinal <= 2):
                require(values['condition'] == 0, 'restart and duplicate replay keep Unknown')
        if round_number == 2:
            require(int(rows[-1]['condition']) == 2, 'original new epoch proof still qualifies when first delivered')
    require(len(set(pids)) == 6, 'fresh sender and receiver processes each round')
    require(len(d['packets']) == 81, 'actual datagram denominator')
    for round_number, count in ((1, 2), (2, 19), (3, 19)):
        expected = []
        for ordinal in range(1, count+1):
            expected.append((1, ordinal))
            if round_number != 1 or ordinal != 2:
                expected.append((2, ordinal))
        packets = sorted(((int(name.split('-')[0]), name, raw) for name, raw in d['packets'].items()
                          if f'-r{round_number}-' in name))
        if round_number == 2:
            require(packets[0][0] == 1 and packets[0][1] == '1-r2-data.bin', 'future frame capture')
            kind, ordinal, payload = frame(packets[0][2])
            require((kind, ordinal, payload) == (1, 19, source[18]), 'original future ordinal')
            index, name, corrupt = packets[1]
            require(index == 2 and name == '2-r2-corrupt.bin', 'corrupt frame capture')
            try:
                frame(corrupt)
            except ValueError:
                pass
            else:
                raise ValueError('injected corruption was accepted')
            repaired = corrupt[:-1]+bytes([corrupt[-1] ^ 1])
            require(frame(repaired) == (1, 1, source[0]), 'CRC corruption of original ordinal1')
            packets = [(index-2, name, raw) for index, name, raw in packets[2:]]
        require([index for index, _, _ in packets] == list(range(1, len(expected)+1)), 'contiguous per-round captures')
        require(len(packets) == len(expected), 'round wire denominator')
        for (_, name, raw), wanted in zip(packets, expected):
            kind, ordinal, payload = frame(raw)
            require((kind, ordinal) == wanted and name.endswith('-data.bin' if kind == 1 else '-ack.bin'), 'actual wire stop-and-wait order')
            require(payload == source[ordinal-1] if kind == 1 else
                    int.from_bytes(payload, 'little') == zlib.crc32(source[ordinal-1]), 'original event bytes and ACK checksum')
    kind, ordinal, payload = frame(d['lost_ack'])
    require((kind, ordinal) == (2, 2) and int.from_bytes(payload, 'little') == zlib.crc32(source[1]), 'committed but undelivered ACK')
    return dict(pass_=True, source_events=19, actual_datagrams=81, lost_acks=1, future_frames_rejected=1, corrupt_frames_rejected=1,
                fresh_processes=6, replica_prefixes=[2, 19, 19], fault_count=1, generation=1,
                final_replayed_condition='Unknown', history_cleared=False)


def mutations(data):
    names = ['wire-crc', 'wrong-stream', 'wrong-registry', 'future-ack', 'changed-event',
             'ack-before-commit', 'duplicate-count', 'replay-heals-unknown', 'erased-history', 'lost-prefix']
    for name in names:
        d = copy.deepcopy(data)
        if name in names[:5]:
            key = '4-r2-ack.bin' if name == 'future-ack' else '3-r2-data.bin'
            raw = bytearray(d['packets'][key])
            if name == 'wire-crc':
                raw[-1] ^= 1
            else:
                offset = {'wrong-stream': 16, 'wrong-registry': 12, 'future-ack': 24, 'changed-event': 40}[name]
                if name == 'future-ack':
                    struct.pack_into('<Q', raw, offset, 2)
                else:
                    raw[offset] ^= 1
                raw[-4:] = struct.pack('<I', zlib.crc32(raw[:-4]))
            d['packets'][key] = bytes(raw)
        elif name == 'ack-before-commit': d['logs'][0][1]['watermark'] = '1'
        elif name == 'duplicate-count': d['logs'][2][0]['count'] = '2'
        elif name == 'replay-heals-unknown': d['logs'][2][0]['condition'] = '2'
        elif name == 'erased-history': d['logs'][1][-1]['cleared'] = '1'
        else: d['stores']['replica-lost-ack'] = d['stores']['source'][:1]
        try:
            judge(d)
        except ValueError:
            pass
        else:
            raise ValueError('accepted mutation: '+name)
    return names


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('directory', type=Path); parser.add_argument('--mutations', action='store_true')
    args = parser.parse_args(); data = load(args.directory); result = judge(data)
    if args.mutations: result['mutations_rejected'] = mutations(data)
    print(json.dumps(result, indent=2))

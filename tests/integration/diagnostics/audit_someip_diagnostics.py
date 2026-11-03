#!/usr/bin/env python3
"""Independent native source, committed journals and TCP/SOME-IP reassembly audit."""
import argparse
import copy
import json
from pathlib import Path
import struct
import zlib
from audit_control_diagnostics import checksum, csv_rows, event, journal, require


def pcap(path):
    data = path.read_bytes(); require(data[:4] == b'\xd4\xc3\xb2\xa1', 'pcap format')
    position = 24; connections = {}; active = {}; syns = 0
    while position < len(data):
        require(position+16 <= len(data), 'pcap record')
        _, _, captured, original = struct.unpack_from('<IIII', data, position); position += 16
        require(captured == original and position+captured <= len(data), 'uncut IP capture')
        packet = data[position:position+captured]; position += captured
        if len(packet) < 34 or packet[12:14] != b'\x08\x00': continue
        ip = packet[14:]; ihl = (ip[0] & 15)*4
        if ip[9] != 6: continue
        require(ihl >= 20 and len(ip) >= ihl+20 and not (int.from_bytes(ip[6:8], 'big') & 0x3fff), 'unfragmented TCP')
        tcp = ip[ihl:]; source, destination, sequence = struct.unpack_from('!HHI', tcp)
        if not ({source, destination} & {40510, 40511}): continue
        pair = (bytes(ip[12:16]), bytes(ip[16:20]), source, destination)
        require(set(pair[:2]) == {b'\x0a\x59\0\x01', b'\x0a\x59\0\x02'}, 'isolated diagnostic IP peers')
        if tcp[13] & 2 and not tcp[13] & 16:
            if pair not in active or active[pair][0] != sequence:
                active[pair] = (sequence, syns); syns += 1
        generation = active.get(pair, (0, -1))[1]; key = pair+(generation,)
        header = (tcp[12] >> 4)*4; length = int.from_bytes(ip[2:4], 'big')
        require(header >= 20 and length <= len(ip), 'TCP/IP sizes')
        payload = ip[ihl+header:length]
        if payload:
            require(generation >= 0, 'capture starts before data connection')
            sequence += int(bool(tcp[13] & 2)); stream = connections.setdefault(key, {})
            for index, value in enumerate(payload, sequence):
                require(index not in stream or stream[index] == value, 'consistent TCP retransmission')
                stream[index] = value
    messages = []
    for key, values in connections.items():
        start, end = min(values), max(values)+1
        require(len(values) == end-start, 'complete TCP stream')
        data = bytes(values[i] for i in range(start, end)); cursor = 0
        while cursor < len(data):
            require(cursor+16 <= len(data), 'SOME/IP header')
            service, method, length, client, session, protocol, interface, kind, code = struct.unpack_from('!HHIHHBBBB', data, cursor)
            require(8 <= length <= 2056 and cursor+length+8 <= len(data), 'SOME/IP length')
            payload = data[cursor+16:cursor+length+8]; cursor += length+8
            require((service, method) in ((0x5d11, 0x101), (0x5d10, 0x102)) and protocol == interface == kind == 1 and code == 0 and session != 0,
                    'dedicated reliable request-no-return binding')
            require(client == 0x2211 if method == 0x101 else client in (0x2221, 0x2222), 'configured SDK client identity')
            messages.append(dict(service=service, method=method, client=client, payload=payload, flow=key))
    return messages, syns


def wire(raw):
    require(40 <= len(raw) <= 2048, 'wire bounds'); checksum(raw, b'SDDWIR\x01\x00')
    kind, reserved, registry, stream, ordinal, length = struct.unpack_from('<B3sIQQI', raw, 8)
    require(reserved == b'\0\0\0' and registry == 3 and stream == 7001 and ordinal > 0 and length == len(raw)-40, 'wire context')
    require(kind in (1, 2) and (kind == 1 or length == 4), 'wire event/ACK only')
    return kind, ordinal, raw[36:-4]


def load(root):
    case = json.loads((root/'result.json').read_text())['case']
    prefix = 'logical-normal' if case == 'normal' else 'logical-speed-input-loss'
    packets, syns = pcap(root/'traffic.pcap')
    return dict(case=case, runtime=json.loads((root/'result.json').read_text()), summary=json.loads((root/'publisher.json').read_text()),
                native=json.loads((root/'logical'/(prefix+'.json')).read_text()), owners=csv_rows(root/'logical'/(prefix+'-events.csv')),
                source=journal(root/'source-store', decoder=bytes), replica=journal(root/'replica-store', decoder=bytes),
                source_records=csv_rows(root/'source-records.csv'), records=csv_rows(root/'replica-records.csv'),
                writer=csv_rows(root/'publisher.csv'), receipts=[csv_rows(p) for p in sorted(root.glob('replica-[0-9].csv'))],
                physical=csv_rows(root/'physical.csv'), baseline=csv_rows(root/'baseline-physical.csv'), messages=packets, syns=syns,
                sdk=[json.loads(p.read_text()) for p in root.glob('*-sdk.json')],
                before=journal(root/'replica-before-restart', decoder=bytes) if case == 'restart' else None,
                contexts=[(struct.unpack_from('<Q', (root/store/'manifest').read_bytes(), 8)[0], struct.unpack_from('<I', (root/store/'manifest').read_bytes(), 32)[0]) for store in ('source-store', 'replica-store')],
                namespaces=[json.loads(p.read_text())['netns'] for p in root.glob('*-1.runtime.json')])


def judge(d):
    normal = d['case'] == 'normal'; expected = 12 if normal else 15; samples = 9200 if normal else 1300
    require(d['runtime']['pass'] and not d['runtime']['forced_cleanup'] and not d['runtime']['sanitizer_errors'] and d['native']['passed'], 'process/runtime verdict')
    require(len(d['source']) == len(d['replica']) == expected and d['source'] == d['replica'], 'exact durable source replica')
    require(d['contexts'] == [(7001, 3), (7001, 3)] and len(set(d['namespaces'])) == 2, 'provisioned independent IP namespaces')
    require(d['summary']['pass'] and d['summary']['events'] == d['summary']['acknowledged'] == expected and d['summary']['live_commits'] > 0 and d['summary']['on_off_identical'], 'live source drained and durable ACKed')
    require(all(s['dropped'] == s['rejected'] == 0 and 0 < s['highwater'] <= 8 for s in d['sdk']), 'bounded SDK ingress')
    events = [event(p) for p in d['source']]
    require([e['_id'] for e in events] == [(7001, 7, i) for i in range(1, expected+1)] and
            all(not e['_unmapped'] and e['_run'] == 7001 and e['_enable']['instance'] == 7001 and e['_enable']['domain'] == 1 for e in events), 'unaltered original producer and simulation clocks')
    require(events[0]['kind'] == 6 and all(e['kind'] not in (5, 9) for e in events), 'actual initial Session and no fabricated recovery')
    commits = [r for r in d['writer'] if r['action'] == 'commit']; acks = [r for r in d['writer'] if r['action'] == 'ack' and r['result'] == '0']
    require([int(r['ordinal']) for r in commits] == [int(r['ordinal']) for r in acks] == list(range(1, expected+1)), 'durable commit and accepted ACK order')
    require(all(int(r['wall_ns']) > 0 for r in d['writer']), 'separate positive monotonic transport clock')
    receipts = [r for rows in d['receipts'] for r in rows]
    require(all(int(r['watermark']) >= int(r['ordinal']) and r['result'] in ('0', '1') for r in receipts), 'receiver durable prefix before ACK')
    data_ordinals = set(); ack_ordinals = set()
    for message in d['messages']:
        kind, ordinal, payload = wire(message['payload']); require(ordinal <= expected, 'wire ordinal bound')
        require((message['service'], message['method']) == ((0x5d11, 0x101) if kind == 1 else (0x5d10, 0x102)), 'wire kind bound to SOME/IP direction')
        require(payload == d['source'][ordinal-1] if kind == 1 else int.from_bytes(payload, 'little') == zlib.crc32(d['source'][ordinal-1]), 'PCAP original bytes or exact event ACK checksum')
        (data_ordinals if kind == 1 else ack_ordinals).add(ordinal)
    require(data_ordinals == ack_ordinals == set(range(1, expected+1)) and d['syns'] >= 2, 'every event and ACK crossed actual TCP')
    physical = d['physical']; require(len(physical) == samples and physical == d['baseline'], 'all on/off physical samples identical')
    previous = None
    for row in physical:
        require(int(row['model_epoch']) == 7 and abs(float(row['balance_j'])) < 1e-4, 'original physical model and energy balance')
        if previous:
            require(int(row['source_ns']) > int(previous['source_ns']) and int(row['model_sequence']) > int(previous['model_sequence']) and
                    float(row['distance_m']) >= float(previous['distance_m'])-1e-9, 'continuous physical history')
        previous = row
    faults = [e for e in events if e['kind'] == 1]
    if normal:
        require(not faults and not d['records'] and not d['source_records'] and d['summary']['controls'] == 4350, 'normal full profile zero false DTC')
        require(int(physical[-1]['contacts']) == 0 and float(physical[-1]['bus_v']) <= 30, 'normal actual HV off')
    else:
        require(len(faults) == len(d['records']) == len(d['source_records']) == 1 and d['summary']['live_fault'], 'one live native fault')
        f = faults[0]; require(f['code'] == 0x1001 and f['detected_ns'] == 11_002_000_000, 'fixed10s injection and original detector')
        require(d['native']['first_fault_ns'] == 10_002_000_000, 'original runtime detector')
        require(next(r for r in commits if int(r['event_sequence']) == f['event_sequence'])['producer_running'] == '1', 'fault committed while owner still producing')
        selected = [e for e in events if e['kind'] == 2]; require(len(selected) == 5 and {e['source_producer'] for e in selected} == {4, 5, 6, 9, 10}, 'five original Leaf selections')
        require(all(e['related_sequence'] == f['event_sequence'] and 0 <= e['selected_ns']-f['detected_ns'] <= 100_000_000 for e in selected), 'original causality and selection budget')
        owner_for_producer = {9: 2, 5: 3, 4: 4, 10: 5, 6: 6}
        for selection in selected:
            require(any(r['kind'] == 'leaf-protection-selected' and int(r['owner']) == owner_for_producer[selection['source_producer']] and
                        int(r['time_ns']) == selection['selected_ns'] for r in d['owners']), 'original Leaf selection log')
        zone_acks = [e for e in events if e['kind'] == 3 and e['source_producer'] in (7, 8)]
        require(len(zone_acks) == 2, 'original two Zone ACKs')
        for ack in zone_acks:
            require(not ack['_times'][3]['present'] and ack['related_sequence'] == f['event_sequence'] and
                    any(r['kind'] == 'zone-protection-ack' and int(r['owner']) == ack['source_producer']-7 and int(r['time_ns']) == ack['acknowledged_ns'] for r in d['owners']), 'original ACK distinct from selection')
        parent = next(e for e in events if e['kind'] == 3 and e['source_producer'] == 3)
        require(not parent['_times'][3]['present'] and parent['related_sequence'] == f['event_sequence'] and
                max(e['acknowledged_ns'] for e in zone_acks) <= parent['acknowledged_ns'] <= f['detected_ns']+100_000_000, 'Central callback ACK after original Zone ACKs')
        actual = next(e for e in events if e['kind'] == 4 and e['code'] == 0x1001)
        require(0 <= actual['actual_source_ns']-f['detected_ns'] <= 230_000_000, 'fresh physical response acquisition')
        for record in d['source_records']+d['records']:
            require(int(record['code']) == 0x1001 and record['count'] == record['generation'] == '1' and record['cleared'] == '0', 'unchanged one occurrence history')
        require(d['source_records'][0]['condition'] == '1' and d['records'][0]['condition'] == ('0' if d['case'] == 'restart' else '1'), 'source Failed and restarted replica Unknown')
        response = [r for r in physical if int(r['source_ns']) >= f['detected_ns'] and abs(float(r['torque_nm'])) <= 1 and float(r['pressure_pa']) >= 1e6]
        require(response and int(response[0]['source_ns'])-f['detected_ns'] <= 230_000_000, 'actual torque and brake response budget')
    if d['case'] in ('drop-ack', 'restart'):
        first = d['receipts'][0]; require(any(r['ordinal'] == '2' and r['ack_sent'] == '0' for r in first), 'first fault durable ACK withheld')
        require(any(r['ordinal'] == '2' and r['result'] == '1' and r['ack_sent'] == '1' for r in receipts), 'same native event retried and duplicate ACKed')
    if d['case'] == 'restart':
        require(d['before'] == d['source'][:2] and len(d['receipts']) == 2 and d['syns'] >= 3 and d['runtime'].get('injected_replica_kill'), 'real replica kill and durable new SDK connection')
        require(all(r['condition'] == '0' for r in d['receipts'][1]), 'reconnection does not heal Unknown')
    return dict(pass_=True, case=d['case'], source_events=expected, intrinsic_dtc=len(faults), physical_samples=samples,
                tcp_connections=d['syns'], someip_messages=len(d['messages']), live_commits=d['summary']['live_commits'],
                final_condition='Unknown' if d['case'] == 'restart' else 'Failed' if not normal else 'no DTC')


def mutations(data):
    names = ['wire-header', 'someip-service', 'replica-bytes', 'physical-reset', 'false-live-source', 'source-clock', 'missing-ack', 'wrong-model', 'erased-record', 'false-response']
    if data['case'] == 'normal': names = names[:8]
    for name in names:
        d = copy.deepcopy(data)
        if name == 'wire-header':
            raw = bytearray(d['messages'][0]['payload']); raw[12] ^= 1; raw[-4:] = struct.pack('<I', zlib.crc32(raw[:-4])); d['messages'][0]['payload'] = bytes(raw)
        elif name == 'someip-service': d['messages'][0]['service'] = 0x5344
        elif name == 'replica-bytes': d['replica'][0] = d['replica'][0][:-1]+b'\xff'
        elif name == 'physical-reset':
            for rows in (d['physical'], d['baseline']): rows[100]['model_sequence'] = '1'
        elif name == 'false-live-source': d['summary']['live_commits'] = 0
        elif name == 'source-clock':
            for entries in (d['source'], d['replica']):
                raw = bytearray(entries[0]); raw[180] = 2; entries[0] = bytes(raw)
        elif name == 'missing-ack': d['messages'] = [m for m in d['messages'] if m['method'] != 0x102]
        elif name == 'wrong-model':
            for rows in (d['physical'], d['baseline']): rows[100]['model_epoch'] = '1'
        elif name == 'erased-record': d['records'][0]['cleared'] = '1'
        else:
            for rows in (d['physical'], d['baseline']):
                for row in rows: row['pressure_pa'] = '0'
        try: judge(d)
        except ValueError: pass
        else: raise ValueError('accepted mutation: '+name)
    return names


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('directory', type=Path); p.add_argument('--mutations', action='store_true'); a = p.parse_args(); data = load(a.directory); result = judge(data)
    if a.mutations: result['mutations_rejected'] = mutations(data)
    print(json.dumps(result, indent=2))

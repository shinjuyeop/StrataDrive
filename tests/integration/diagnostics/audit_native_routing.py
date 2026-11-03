#!/usr/bin/env python3
"""Actual native owner/context/control TCP and multi-stream journal audit."""
import argparse
import copy
import json
from pathlib import Path
import struct
import zlib
from audit_control_diagnostics import checksum, csv_rows, event, journal, require
from audit_someip_diagnostics import pcap

SOURCES = [(20, 'front', 0), (21, 'rear', 1), (22, 'front', 2), (23, 'front', 3),
           (24, 'rear', 4), (30, 'front', 0), (31, 'rear', 1), (32, 'rear', 5), (33, 'rear', 6)]
DOMAIN = 0x53444d4f4e4f
ROLES = ('central', 'front', 'rear')
IPS = {role: bytes([10, 88, 0, i+1]) for i, role in enumerate(ROLES)}
CLIENTS = dict(zip(ROLES, (0x1311, 0x1422, 0x1522)))


def wire(raw):
    require(40 <= len(raw) <= 2048, 'wire bounds'); checksum(raw, b'SDDWIR\x01\x00')
    kind, reserved, registry, stream, ordinal, length = struct.unpack_from('<B3sIQQI', raw, 8)
    require(reserved == b'\0\0\0' and registry == 3 and ordinal > 0 and length == len(raw)-40 and kind in (1, 2), 'wire context')
    require(kind == 1 or length == 4, 'ACK checksum length')
    return kind, stream, ordinal, raw[36:-4]


def lease(raw):
    if len(raw) != 85 or raw[:8] != b'SDRV\x01\0\0\0' or raw[24] != 2:
        return None
    crc = 0xffffffff
    for byte in raw[:-4]:
        crc ^= byte
        for _ in range(8): crc = (crc >> 1) ^ (0x82f63b78 if crc & 1 else 0)
    require((crc ^ 0xffffffff) == int.from_bytes(raw[-4:], 'little'), 'control CRC32C')
    sender, receiver, domain = struct.unpack_from('<IIQ', raw, 8)
    require(sender == 7 and receiver < 7 and domain == DOMAIN, 'original RunLease route/clock')
    values = struct.unpack_from('<IQQQQIQQ', raw, 25)
    return (receiver, *values)


def load(root):
    result = json.loads((root/'result.json').read_text()); home = root/'native-diagnostics'
    streams = {}; bindings = {}
    def add(stream, source, replica, sender, receiver, pub, rep):
        streams[stream] = dict(source=journal(source, bytes), replica=journal(replica, bytes), sender=sender, receiver=receiver, pub=pub, rep=rep,
                               manifests=[(int.from_bytes((p/'manifest').read_bytes()[8:16], 'little'), int.from_bytes((p/'manifest').read_bytes()[32:36], 'little')) for p in (source, replica)])
        bindings[(rep, 0x101)] = (CLIENTS[sender],); bindings[(pub, 0x102)] = (CLIENTS[receiver],)
    for z, role in enumerate(('front', 'rear')):
        add(8101+z, home/'central'/f'context-{z}', home/role/'context', 'central', role, 0x5e00+2*z, 0x5e01+2*z)
    for i, (producer, role, _) in enumerate(SOURCES):
        add(8200+i, home/role/f'source-{producer}', home/'central'/f'source-{producer}', role, 'central', 0x5e10+2*i, 0x5e11+2*i)
    for sid, sender in [(0x5344, 'central'), (0x5345, 'central'), (0x5348, 'central'), (0x5349, 'central'),
                        (0x5346, 'front'), (0x5347, 'front'), (0x534a, 'rear'), (0x534b, 'rear')]:
        for mid in (0x10, 0x20, 0x40, 0x50, 0x60, 0x70, 0x80): bindings[(sid, mid)] = (CLIENTS[sender],)
    restarts = {}
    for role in ROLES:
        trace = home/role/(role+'-1.restart.csv')
        after = home/role/'restart-after-records.csv'
        restarts[role] = dict(rows=csv_rows(trace) if trace.exists() else [],
                              after_records=csv_rows(after) if after.exists() else [],
                              source_records={p.name: csv_rows(p) for p in (home/role).glob('restart-after-source-*-records.csv')})
    packets, syns = pcap(root/'traffic.pcap', (*range(30501, 30509), 31610, 31611, 31612), tuple(IPS.values()), bindings)
    return dict(result=result, restarts=restarts, plan=json.loads((root.parent/'plan.json').read_text()), streams=streams,
                merged=journal(home/'central'/'merged', bytes), records=csv_rows(home/'central'/'records.csv'),
                boot=csv_rows(root/'central-1.events.csv'), physical=csv_rows(root/'physical.csv'),
                credits=[r for role in ('front', 'rear') for r in csv_rows(home/role/(role+'-1.credits.csv'))],
                originals=[r for role in ('front', 'rear') for r in csv_rows(home/role/(role+'-1.originals.csv'))],
                delivery=csv_rows(home/'central'/'central-1.delivery.csv'),
                channels=[r for role in ROLES for r in csv_rows(home/role/(role+'-1.channels.csv'))],
                placement=[json.loads((home/role/(role+'-1.writer.json')).read_text()) for role in ROLES],
                namespaces=[json.loads((root/(role+'.runtime.json')).read_text())['netns'] for role in ROLES],
                messages=packets, syns=syns,
                injection=int((root/'inject').read_text()) if (root/'inject').exists() else 0)


def judge(d):
    result = d['result']; normal = result['case'] == 'normal'; streams = d['streams']
    require(result['pass'] and result['rear']['pass'] and not result['forced_cleanup'] and not result['sanitizer_diagnostics'] and not result['sdk_errors'], 'original native runtime/physical verdict')
    require(len(set(d['namespaces'])) == 3, 'three distinct native ECU namespaces')
    require(all(p['allowed_cpus'] == [15] and p['policy'] == p['priority'] == 0 for p in d['placement']), 'actual non-RT writer placement')
    require(all(int(r['rejected']) == int(r['dropped']) == 0 and 0 < int(r['highwater']) <= 8 for r in d['channels']), 'bounded separate SDK ingress')
    merged = [event(raw) for raw in d['merged']]; identities = [e['_id'] for e in merged]
    require(len(set(identities)) == len(identities), 'merged original identity deduplication')
    sessions = [(raw, e) for raw, e in zip(d['merged'], merged) if e['kind'] == 6]
    require(len(sessions) == 1 and sessions[0][1]['_id'][:2] == (8001, 7), 'one genuine Central Session')
    global_raw, context = sessions[0]; enable = context['_enable']['ns']; completed = context['source_ns']
    require(context['epoch'] == 1 and context['received_roles'] == 255 and int.from_bytes(global_raw[-34:-30], 'little') == 255, 'complete global Release masks')
    released = [r for r in d['boot'] if r['event'] == 'session-ack' and r['value'] == '20']
    require({int(r['role']) for r in released} == set(range(8)), 'actual eight accepted Release ACKs')
    times = sorted(int(r['ns']) for r in released)
    require(enable <= times[-2] <= completed <= times[-1] <= context['observed_ns'] and times[-1]-completed <= 30_000_000, 'original global completion bounded by real final ACK')
    require(all(e['_run'] == 8001 and e['_profile'] == 1 and e['epoch'] == 1 and
                (e['kind'] == 9 or (e['_enable']['domain'] == 2 and e['_enable']['instance'] == DOMAIN and e['_enable']['ns'] == enable)) for e in merged), 'original run/profile/clock/epoch')
    # The existing Central observer explicitly retains an unassigned cause as
    # CodeNone Observation. Do not relabel it as a remote root or erase its flag.
    require(all(not e['_unmapped'] or (e['_id'][1] == 8 and e['kind'] == 0 and e['code'] == 0) for e in merged), 'unmapped cause retained only as Central observation')
    require(all(e['kind'] != 5 and e['_proof'] == 0 for e in merged), 'no fabricated recovery/clear')
    expected_ids = {e['_id'] for e in merged if e['_id'][1] in (7, 8)}
    for stream, s in streams.items():
        require(s['source'] == s['replica'] and s['source'] and s['manifests'] == [(stream, 3)]*2, 'exact source replica and stream manifests')
        require(s['source'][0] == global_raw, 'original context precedes all source events')
        if stream < 8200: require(len(s['source']) == 1, 'context-only channel')
        else:
            producer = SOURCES[stream-8200][0]
            require(all(event(raw)['_id'][1] == producer for raw in s['source'][1:]), 'one immutable local source identity')
        for raw in s['source']:
            identity = event(raw)['_id']; expected_ids.add(identity)
            require(d['merged'][identities.index(identity)] == raw, 'merged durable original bytes')
    require(set(identities) == expected_ids, 'no erased or invented merged events')
    data_seen = set(); ack_seen = set(); leases = set()
    for m in d['messages']:
        if m['method'] == 0x50:
            value = lease(m['payload']); require(value is not None, 'canonical native RunLease'); leases.add(value)
        if m['method'] in (0x101, 0x102): require(m['service'] >= 0x5d00, 'diagnostic method requires diagnostic service')
        if m['service'] < 0x5d00: continue
        kind, stream, ordinal, payload = wire(m['payload']); require(stream in streams, 'provisioned wire stream')
        s = streams[stream]; require(ordinal <= len(s['source']), 'bounded committed ordinal')
        sender, receiver = (s['sender'], s['receiver']) if kind == 1 else (s['receiver'], s['sender'])
        require(m['service'] == (s['rep'] if kind == 1 else s['pub']) and m['method'] == (0x101 if kind == 1 else 0x102), 'exact SOME/IP lane direction')
        require(m['flow'][0] == IPS[sender] and m['flow'][1] == IPS[receiver] and m['flow'][3] == 31610+ROLES.index(receiver), 'independent diagnostic IP endpoint')
        require(payload == s['source'][ordinal-1] if kind == 1 else int.from_bytes(payload, 'little') == zlib.crc32(s['source'][ordinal-1]), 'PCAP original Event or exact durable ACK')
        (data_seen if kind == 1 else ack_seen).add((stream, ordinal))
    expected = {(stream, i+1) for stream, s in streams.items() for i in range(len(s['source']))}
    require(data_seen == ack_seen == expected, 'all11 streams and every ordinal crossed real TCP with ACK')
    require(len(d['credits']) == 9 and {int(r['producer']) for r in d['credits']} == {s[0] for s in SOURCES}, 'actual endpoint accepted credit snapshots')
    for r in d['credits']:
        producer = int(r['producer']); role = next(s[2] for s in SOURCES if s[0] == producer)
        values = tuple(int(r[k]) for k in ('epoch', 'requested_ns', 'prepare_deadline_ns', 'enable_ns', 'commit_deadline_ns', 'lease_sequence', 'source_ns', 'expiry_ns'))
        require((role, *values) in leases and int(r['enable_ns']) == enable and completed <= int(r['source_ns']) <= int(r['captured_ns']) < int(r['expiry_ns']), 'original accepted credit matches actual issuer/control TCP and global completion')
    faults = [e for e in merged if e['kind'] == 1]
    restored = {tuple(r[k] for k in ('code','component','monitor','subject')) for r in d['restarts']['central']['after_records']}
    require(all(int(r['count']) == int(r['generation']) == 1 and r['cleared'] == '0' and r['condition'] == ('0' if tuple(r[k] for k in ('code','component','monitor','subject')) in restored else '1') for r in d['records']), 'DTC history and failed condition retained')
    require(len(faults) == len(d['records']), 'one original occurrence per record')
    if normal:
        require(not faults, 'normal zero false DTC')
    else:
        target = (20, 22, 23, 30) if result['fault_target'] == 'front' else (21, 24, 31)
        require(any(e['_id'][1] in target and e['code'] == 0x2001 for e in faults) and all(e['code'] in (0x2001, 0x2002) for e in faults), 'declared target command-loss and actual mapped native causes')
        require(all(e['detected_ns'] >= d['injection'] for e in faults), 'no pre-injection intrinsic fault')
        for f in faults:
            if f['_id'][1] < 30: continue
            original = [r for r in d['originals'] if int(r['producer']) == f['_id'][1] and int(r['monitor']) == f['monitor'] and int(r['detected_ns']) == f['detected_ns'] and int(r['reason']) == f['native_reason'] and r['propagation'] == '0']
            require(original, 'original native detector snapshot')
            require(any(int(r['violation_ns']) == f['_times'][1]['ns'] for r in original), 'unaltered native violation deadline')
            if f['_command']['present']:
                require(any(int(r['root_sequence']) == f['_command']['sequence'] and int(r['root_source']) == f['_command']['source']['ns'] and int(r['root_expiry']) == f['_command']['expiry']['ns'] for r in original), 'unaltered native root command identity')
            ack = [e for e in merged if e['_id'][1] == f['_id'][1] and e['kind'] == 3 and e['related_sequence'] == f['event_sequence']]
            require(len(ack) == 1 and 0 <= ack[0]['acknowledged_ns']-f['detected_ns'] <= 100_000_000 and any(int(r['selected_ns']) == ack[0]['acknowledged_ns'] for r in original), 'actual original Zone protection ACK')
        require(any(d['injection'] <= int(r['ns']) <= d['injection']+100_000_000 and abs(float(r['torque'])) <= 1 and float(r['pressure']) >= 100000 for r in d['physical']), 'original100ms physical torque/brake criterion')
    if d['plan']['diagnostic_drop_ack']:
        omitted = [r for r in d['delivery'] if r['action'] == 'omit-ack']; require(len(omitted) == 1, 'one durable Fault ACK omitted')
        require(any(r['action'] == 'duplicate' and r['stream'] == omitted[0]['stream'] and r['ordinal'] == omitted[0]['ordinal'] for r in d['delivery']), 'same committed ordinal duplicate retry')
    if d['plan']['diagnostic_context_delay_ms']:
        require(max(r['pending_highwater'] for r in result['diagnostics'].values()) > 0, 'actual source buffered before delayed context')
    requested = d['plan'].get('diagnostic_restart')
    for role in ROLES:
        expected_restart = requested in (role, 'all')
        require(result['diagnostics'][role].get('restarts', 0) == int(expected_restart), 'requested store/service reopen count')
        r = d['restarts'][role]; before = [row for row in r['rows'] if row['phase'] == 'before']; after = [row for row in r['rows'] if row['phase'] == 'after']
        if not expected_restart:
            require(not before and not after, 'no undeclared restart'); continue
        require(before and before == [dict(row, phase='before') for row in after], 'reopened committed source/replica prefix exact bytes')
        for row in after:
            stream, ordinal = int(row['stream']), int(row['ordinal'])
            require(bytes.fromhex(row['bytes']) == streams[stream]['source'][ordinal-1], 'restarted prefix remains original final history')
        require(all(row['condition'] == '0' and row['count'] == row['generation'] == '1' and row['cleared'] == '0'
                    for rows in [r['after_records'], *r['source_records'].values()] for row in rows), 'restart restores Unknown with original occurrence count')
        if role != 'central':
            sent = [m for m in d['messages'] if m['method'] == 0x101 and m['service'] >= 0x5d00]
            for stream in {int(row['stream']) for row in after}:
                require(sum(wire(m['payload'])[1:3] == (stream, 1) for m in sent) >= 2, 'restarted sender replays original ordinal1 over TCP')
    return dict(pass_=True, streams=len(streams), merged_events=len(merged), dtc=len(faults), tcp_messages=len(d['messages']), connections=d['syns'], original_credits=len(d['credits']))


def mutations(data):
    rejected = 0
    for name in ('wire-stream', 'service', 'replica', 'erase-record', 'missing-ack', 'accepted-credit', 'detector', 'physical', 'restart-bytes', 'restart-condition'):
        d = copy.deepcopy(data)
        if name == 'wire-stream':
            m = next(m for m in d['messages'] if m['service'] >= 0x5d00); raw = bytearray(m['payload']); raw[16] ^= 1; raw[-4:] = zlib.crc32(raw[:-4]).to_bytes(4, 'little'); m['payload'] = bytes(raw)
        elif name == 'service': next(m for m in d['messages'] if m['service'] >= 0x5d00)['service'] = 0x5344
        elif name == 'replica': d['streams'][8200]['replica'][0] = b'corrupt'
        elif name == 'erase-record':
            if not d['records']: continue
            d['records'] = []
        elif name == 'missing-ack': d['messages'] = [m for m in d['messages'] if m['method'] != 0x102]
        elif name == 'accepted-credit': d['credits'][0]['source_ns'] = str(int(d['credits'][0]['source_ns'])+1)
        elif name == 'detector':
            if not d['records']: continue
            for r in d['originals']: r['detected_ns'] = '0'
        elif name == 'physical':
            if not d['records']: continue
            for r in d['physical']: r['pressure'] = '0'
        elif name == 'restart-bytes':
            candidates = [r for role in ROLES for r in d['restarts'][role]['rows'] if r['phase'] == 'after']
            if not candidates: continue
            candidates[0]['bytes'] = '00'
        else:
            candidates = [r for role in ROLES for rows in [d['restarts'][role]['after_records'], *d['restarts'][role]['source_records'].values()] for r in rows]
            if not candidates: continue
            candidates[0]['condition'] = '2'
        try: judge(d)
        except (ValueError, KeyError): rejected += 1; continue
        raise ValueError('mutation accepted: '+name)
    return rejected


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('directory', type=Path); p.add_argument('--mutations', action='store_true'); a = p.parse_args()
    data = load(a.directory); result = judge(data)
    if a.mutations: result['mutations_rejected'] = mutations(data)
    print(json.dumps(result, sort_keys=True))

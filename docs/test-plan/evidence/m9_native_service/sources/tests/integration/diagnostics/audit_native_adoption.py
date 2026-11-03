#!/usr/bin/env python3
"""Independent actual ECU SIGKILL/rejoin, producer incarnation and prefix audit."""
import argparse
import copy
import json
from pathlib import Path
import struct
import zlib
from audit_control_diagnostics import checksum, csv_rows, event, journal, require
from audit_native_routing import SOURCES, DOMAIN, ROLES, IPS, CLIENTS, wire, lease
from audit_someip_diagnostics import pcap


def prefix(path, allow_tail=False):
    manifest, checkpoint, data = [(path/name).read_bytes() for name in ('manifest', 'commit', 'journal')]
    require(len(manifest) == 40 and len(checkpoint) == 28 and len(data) <= 64*1024*1024, 'prefix bounds')
    checksum(manifest, b'SDDMAN\x01\x00'); checksum(checkpoint, b'SDDCMT\x01\x00')
    count, end = struct.unpack_from('<QQ', checkpoint, 8)
    require(end <= len(data), 'committed prefix bounds')
    incomplete = (path/'incomplete').exists(); tail = data[end:]
    require(allow_tail or (not tail and not incomplete), 'only old crashed source may have incomplete suffix')
    rows = []; cursor = 0
    for ordinal in range(1, count+1):
        require(cursor+24 <= end, 'prefix frame header')
        number, length = struct.unpack_from('<QI', data, cursor+8)
        require(number == ordinal and length <= 256*1024 and cursor+length+24 <= end, 'prefix ordinal/length')
        frame = data[cursor:cursor+length+24]; checksum(frame, b'SDDEVT\x01\x00'); rows.append(frame[20:-4]); cursor += length+24
    require(cursor == end, 'prefix exact watermark')
    return dict(rows=rows, tail=tail, incomplete=incomplete, stream=int.from_bytes(manifest[8:16], 'little'), registry=int.from_bytes(manifest[32:36], 'little'))


def load(root):
    result = json.loads((root/'result.json').read_text()); home = root/'native-diagnostics'; target = result['fault_target']
    clients = {r: (c, c+1) if r == target else (c,) for r, c in CLIENTS.items()}; bindings = {}; streams = {}
    def add(stream, sender, receiver, source, replica, pub, rep, producer=7, generation=0):
        streams[stream] = dict(source=prefix(source, stream >= 8200 and generation == 1 and sender == target), replica=prefix(replica),
                               sender=sender, receiver=receiver, pub=pub, rep=rep, producer=producer, generation=generation)
        bindings[(rep, 0x101)] = clients[sender]; bindings[(pub, 0x102)] = clients[receiver]
    for z, role in enumerate(('front', 'rear')):
        add(8101+z, 'central', role, home/'central'/f'context-{z}', home/role/'context', 0x5e00+2*z, 0x5e01+2*z)
    for generation in (1, 2):
        for i, (base, role, _) in enumerate(SOURCES):
            producer = ((generation-1) << 32) | base; sid = (0x5e10 if generation == 1 else 0x5e40)+2*i
            add(8200+9*(generation-1)+i, role, 'central', home/role/f'source-{producer}', home/'central'/f'source-{producer}', sid, sid+1, producer, generation)
    for sid, sender in [(0x5344, 'central'), (0x5345, 'central'), (0x5348, 'central'), (0x5349, 'central'),
                        (0x5346, 'front'), (0x5347, 'front'), (0x534a, 'rear'), (0x534b, 'rear')]:
        for method in (0x10, 0x20, 0x40, 0x50, 0x60, 0x70, 0x80): bindings[(sid, method)] = clients[sender]
    packets, syns = pcap(root/'traffic.pcap', (*range(30501, 30509), 31610, 31611, 31612), tuple(IPS.values()), bindings)
    tags = [(r, r+'-1') for r in ROLES] + [(target, target+'-2')]
    def combined(suffix):
        return [row for role, tag in tags for row in csv_rows(home/role/(tag+suffix))]
    return dict(result=result, plan=json.loads((root.parent/'plan.json').read_text()), streams=streams, messages=packets, syns=syns,
                merged=journal(home/'central'/'merged', bytes), records=csv_rows(home/'central'/'records.csv'), physical=csv_rows(root/'physical.csv'),
                credits=combined('.credits.csv'), originals=combined('.originals.csv'),
                producers={(role, tag): json.loads((home/role/(tag+'.producer.json')).read_text()) for role, tag in tags},
                placement=[json.loads((home/role/(tag+'.writer.json')).read_text()) for role, tag in tags],
                lifecycle={r: journal(home/r/'producer-lifecycle', bytes) for r in ('front', 'rear')},
                archives=csv_rows(home/target/(target+'-2.archives.csv')),
                boot=[csv_rows(root/(p+'.events.csv')) for p in ('central-1', 'central-1-rejoined')],
                channels=[row for role, tag in tags if (home/role/(tag+'.channels.csv')).exists() for row in csv_rows(home/role/(tag+'.channels.csv'))],
                injection=int((root/'inject').read_text()))


def judge(d):
    result = d['result']; target = result['fault_target']; streams = d['streams']; crash = result['injected_crash']
    require(result['pass'] and result['rear']['pass'] and not result['forced_cleanup'] and not result['sanitizer_diagnostics'] and not result['sdk_errors'], 'native process/physical verdict')
    require(d['plan']['diagnostic_process_restart'] and result['case'] == 'restart-live' and crash['role'] == target and crash['generation'] == 1, 'declared full ECU crash')
    victims = [r for r in result['processes'] if r['role'] == target]
    require(len(victims) == 2 and victims[0]['exit'] == -9 and victims[0]['expected_abrupt_stop'] and victims[1]['exit'] == 0, 'actual old ECU SIGKILL and new successful process')
    require(result['survivor_pids_before'] == result['survivor_pids_after'] and len(result['survivor_pids_after']) == 2 and crash['pid'] not in result['survivor_pids_after'].values(), 'two real surviving ECU identities unchanged')
    require(all(p['allowed_cpus'] == [15] and p['policy'] == p['priority'] == 0 for p in d['placement']), 'actual non-RT diagnostic placement')
    require(all(int(r['rejected']) == int(r['dropped']) == 0 and 0 <= int(r['highwater']) <= 8 for r in d['channels']), 'bounded dedicated ingress')
    merged = [event(raw) for raw in d['merged']]; identities = [e['_id'] for e in merged]
    require(len(set(identities)) == len(identities), 'unique merged original identities')
    contexts = {e['epoch']: (raw, e) for raw, e in zip(d['merged'], merged) if e['kind'] == 6}
    require(set(contexts) == {1, 2} and sum(e['kind'] == 6 for e in merged) == 2, 'exactly two genuine Central Sessions')
    for epoch, rows in enumerate(d['boot'], 1):
        raw, e = contexts[epoch]; require(e['_id'][:2] == (8001, 7) and e['received_roles'] == 255 and int.from_bytes(raw[-34:-30], 'little') == 255, 'original full global Session masks')
        accepted = [int(r['ns']) for r in rows if r['event'] == 'session-ack' and r['value'] == '20']; roles = {int(r['role']) for r in rows if r['event'] == 'session-ack' and r['value'] == '20'}
        require(roles == set(range(8)) and len(accepted) == 8, 'eight genuine Release ACKs for each epoch')
        require(e['_enable']['ns'] <= sorted(accepted)[-2] <= e['source_ns'] <= max(accepted) <= e['observed_ns'], 'original Release completion axis')
    expected_ids = {e['_id'] for e in merged if e['_id'][1] in (7, 8)}
    for stream, s in streams.items():
        source, replica = s['source'], s['replica']; rows = source['rows']
        require(rows == replica['rows'] and (source['stream'], replica['stream']) == (stream, stream) and source['registry'] == replica['registry'] == 3, 'independent stream exact durable replicas')
        active = stream < 8200 or s['generation'] == 1 or s['sender'] == target
        require(bool(rows) == active, 'only declared producer incarnations active')
        if not active: continue
        first_epoch = 2 if s['generation'] == 2 else 1
        require(rows[0] == contexts[first_epoch][0], 'original context precedes incarnation events')
        if stream < 8200: require(rows == [contexts[i][0] for i in (1, 2)], 'two unmodified global contexts delivered')
        else:
            own = [event(raw) for raw in rows if event(raw)['kind'] != 6]
            require(all(e['_id'][1] == s['producer'] for e in own), 'immutable generation-specific publisher')
            require([e['event_sequence'] for e in own] == list(range(1, len(own)+1)), 'source sequence starts at1 and never reuses/skips')
            require(all(e['epoch'] == 2 for e in own) if s['generation'] == 2 else all(e['epoch'] in (1, 2) for e in own), 'new producer requires actual new application epoch')
        for raw in rows:
            identity = event(raw)['_id']; expected_ids.add(identity)
            require(identity in identities and d['merged'][identities.index(identity)] == raw, 'merged original bytes unchanged')
    require(set(identities) == expected_ids, 'no fabricated or erased history')
    data_seen = set(); ack_seen = set(); leases = set(); replayed = set()
    for m in d['messages']:
        if m['method'] == 0x50: leases.add(lease(m['payload']))
        if m['method'] in (0x101, 0x102): require(m['service'] >= 0x5d00, 'diagnostic method requires diagnostic service')
        if m['service'] < 0x5d00: continue
        kind, stream, ordinal, payload = wire(m['payload']); require(stream in streams, 'provisioned stream'); s = streams[stream]; rows = s['source']['rows']
        require(1 <= ordinal <= len(rows), 'committed ordinal only')
        sender, receiver = (s['sender'], s['receiver']) if kind == 1 else (s['receiver'], s['sender'])
        require(m['service'] == (s['rep'] if kind == 1 else s['pub']) and m['method'] == (0x101 if kind == 1 else 0x102), 'diagnostic lane direction')
        require(m['flow'][0] == IPS[sender] and m['flow'][1] == IPS[receiver] and m['flow'][3] == 31610+ROLES.index(receiver), 'real independent IP endpoint')
        require(payload == rows[ordinal-1] if kind == 1 else int.from_bytes(payload, 'little') == zlib.crc32(rows[ordinal-1]), 'canonical original Data/ACK')
        (data_seen if kind == 1 else ack_seen).add((stream, ordinal))
        if kind == 1 and s['generation'] == 1 and s['sender'] == target and ordinal == 1 and m['client'] == CLIENTS[target]+1: replayed.add(stream)
    expected = {(stream, i+1) for stream, s in streams.items() for i in range(len(s['source']['rows']))}
    require(data_seen == ack_seen == expected, 'every committed ordinal crossed actual TCP with durable ACK')
    old_streams = {stream for stream, s in streams.items() if s['generation'] == 1 and s['sender'] == target}
    require(replayed == old_streams and {int(r['stream']) for r in d['archives']} == old_streams, 'new SDK client replays old incarnation ordinal1')
    for row in d['archives']:
        s = streams[int(row['stream'])]['source']; require(int(row['committed']) == len(s['rows']) and int(row['uncommitted_bytes']) == len(s['tail']) and int(row['source_complete']) == int(not s['tail'] and not s['incomplete']), 'old tail retained and completeness reported honestly')
    require(len(d['credits']) == 18, 'original endpoint accepted credit snapshots in both epochs')
    for r in d['credits']:
        producer = int(r['producer']); base = producer & 0xffffffff; role = next(s[2] for s in SOURCES if s[0] == base)
        values = tuple(int(r[k]) for k in ('epoch', 'requested_ns', 'prepare_deadline_ns', 'enable_ns', 'commit_deadline_ns', 'lease_sequence', 'source_ns', 'expiry_ns'))
        require((role, *values) in leases and values[3] == contexts[values[0]][1]['_enable']['ns'] and values[-2] <= int(r['captured_ns']) < values[-1], 'actual native accepted credit matches original control wire')
    for role in ('front', 'rear'):
        lifecycle = [event(raw) for raw in d['lifecycle'][role]]; expected_kinds = [9, 9, 0] if role == target else [9, 0]
        require([e['kind'] for e in lifecycle] == expected_kinds and all(e['_id'][1] == 9100+ROLES.index(role) for e in lifecycle), 'durable process generation and clean close history')
        require(not any(e['kind'] == 6 for e in lifecycle), 'private incarnation history is never global Session')
        if role == target: require([e['epoch'] for e in lifecycle] == [1, 2, 2] and [e['event_sequence'] for e in lifecycle] == [1, 3, 4], 'unclean gap never reuses original producer allocation')
    metadata = d['producers'][(target, target+'-2')]; require(metadata['generation'] == 2 and metadata['previous_unclean'], 'unclean restart acknowledged')
    gaps = [e for e in merged if e['code'] == 0x5001 and e['kind'] == 1]; expected_gap_producers = {((1 << 32)|base) for base, role, _ in SOURCES if role == target}
    require({e['_id'][1] for e in gaps} == expected_gap_producers and len(gaps) == len(expected_gap_producers), 'one explicit continuity incident per restarted source')
    for e in gaps:
        require(e['event_sequence'] == 1 and e['epoch'] == 2 and e['native_reason'] == 1 and e['_before'] == 1 and e['_after'] == 2 and e['_unknown'] and e['_unmapped'] and e['_proof'] == 0 and e['measured'] == 0 and e['detected_ns'] == metadata['boot_ns'], 'unverified volatile loss preserves original boot observation and guesses no lost count')
    require(all(not e['_unmapped'] or e in gaps or (e['_id'][1] == 8 and e['kind'] == 0 and e['code'] == 0) for e in merged), 'unknown causes retained honestly')
    require(all(r['count'] == r['generation'] == '1' and r['cleared'] == '0' for r in d['records']), 'original DTC incidences not recounted or cleared')
    require(any(d['injection'] <= int(r['ns']) <= d['injection']+100_000_000 and abs(float(r['torque'])) <= 1 and float(r['pressure']) >= 100000 for r in d['physical']), 'original100ms physical protection after actual SIGKILL')
    for e in merged:
        require(e['_run'] == 8001 and e['_profile'] == 1 and e['epoch'] in (1, 2), 'original run/profile/epochs')
        if e['kind'] == 5:
            proof = next((p for p in merged if p['_id'] == e['_proof_event']), None)
            require(e['epoch'] == 2 and e['_id'][1] < (1 << 32) and proof and proof['_id'][1] == e['_id'][1] and proof['_proof'] == e['_proof'] and proof['epoch'] == 2 and proof['kind'] in (0, 4), 'only continuous original source proof can qualify recovery')
    return dict(pass_=True, active_streams=sum(bool(s['source']['rows']) for s in streams.values()), original_credits=len(d['credits']), gaps=len(gaps), merged_events=len(merged), tcp_messages=len(d['messages']), connections=d['syns'])


def mutations(data):
    for name in ('producer-reuse', 'erase-gap', 'fabricated-loss-count', 'credit', 'context', 'no-old-replay', 'physical', 'lifecycle', 'tail-report'):
        d = copy.deepcopy(data)
        if name == 'producer-reuse':
            stream = next(s for s in d['streams'].values() if s['generation'] == 2 and s['source']['rows']); stream['producer'] &= 0xffffffff
        elif name == 'erase-gap': d['merged'] = [raw for raw in d['merged'] if event(raw)['code'] != 0x5001]
        elif name == 'fabricated-loss-count': d['producers'][(d['result']['fault_target'], d['result']['fault_target']+'-2')]['boot_ns'] += 1
        elif name == 'credit': d['credits'][0]['source_ns'] = '0'
        elif name == 'context': d['boot'][1] = []
        elif name == 'no-old-replay': d['messages'] = [m for m in d['messages'] if not(m['client'] == CLIENTS[d['result']['fault_target']]+1 and m['method'] == 0x101 and 0x5e11 <= m['service'] <= 0x5e21)]
        elif name == 'physical':
            for row in d['physical']: row['pressure'] = '0'
        elif name == 'lifecycle': d['lifecycle'][d['result']['fault_target']] = []
        else: d['archives'][0]['uncommitted_bytes'] = str(int(d['archives'][0]['uncommitted_bytes'])+1)
        try: judge(d)
        except (ValueError, KeyError, IndexError): continue
        raise ValueError('mutation accepted: '+name)
    return 9


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('directory', type=Path); p.add_argument('--mutations', action='store_true'); a = p.parse_args()
    data = load(a.directory); result = judge(data)
    if a.mutations: result['mutations_rejected'] = mutations(data)
    print(json.dumps(result, sort_keys=True))

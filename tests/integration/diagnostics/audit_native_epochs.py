#!/usr/bin/env python3
"""Independent live ECU replacement, fixed logical streams and epoch-family audit."""
import argparse
import copy
import json
from pathlib import Path
import struct
import zlib
from audit_control_diagnostics import checksum, csv_rows, event, journal, require
from audit_epoch_delivery import family, metadata
from audit_native_routing import SOURCES, ROLES, IPS, CLIENTS, lease
from audit_someip_diagnostics import pcap


def wire(raw):
    require(40 <= len(raw) <= 2048, 'wire bounds'); checksum(raw, b'SDDWIR\x01\x00')
    kind, reserved, registry, stream, ordinal, length = struct.unpack_from('<B3sIQQI', raw, 8)
    require(reserved == b'\0\0\0' and registry == 4 and ordinal > 0 and length == len(raw)-40 and kind in (1, 2), 'family wire context')
    require(kind == 1 or length == 4, 'ACK checksum length')
    return kind, stream, ordinal, raw[36:-4]


def load(root):
    result = json.loads((root/'result.json').read_text()); home = root/'native-diagnostics'
    target = result['fault_target']; replacement = result['case'] == 'restart-live'
    clients = {r: (c, c+1) if replacement and r == target else (c,) for r, c in CLIENTS.items()}
    streams, bindings = {}, {}
    def add(stream, sender, receiver, source, replica, pub, rep, producer=7):
        original, info = family(source); copied, rep_info = family(replica)
        streams[stream] = dict(source=original, replica=copied, info=info, replica_info=rep_info,
                               sender=sender, receiver=receiver, pub=pub, rep=rep, producer=producer)
        bindings[(rep, 0x101)] = clients[sender]; bindings[(pub, 0x102)] = clients[receiver]
    for z, role in enumerate(('front', 'rear')):
        add(8101+z, 'central', role, home/'central'/f'context-{z}', home/role/'context', 0x5e00+2*z, 0x5e01+2*z)
    for i, (producer, role, _) in enumerate(SOURCES):
        add(8200+i, role, 'central', home/role/f'source-{producer}', home/'central'/f'source-{producer}', 0x5e10+2*i, 0x5e11+2*i, producer)
    for sid, sender in [(0x5344, 'central'), (0x5345, 'central'), (0x5348, 'central'), (0x5349, 'central'),
                        (0x5346, 'front'), (0x5347, 'front'), (0x534a, 'rear'), (0x534b, 'rear')]:
        for method in (0x10, 0x20, 0x40, 0x50, 0x60, 0x70, 0x80): bindings[(sid, method)] = clients[sender]
    packets, syns = pcap(root/'traffic.pcap', (*range(30501, 30509), 31610, 31611, 31612), tuple(IPS.values()), bindings)
    tags = [(r, r+'-1') for r in ROLES] + ([(target, target+'-2')] if replacement else [])
    final_tags = [(r, r+('-2' if replacement and r == target else '-1')) for r in ROLES]
    def combined(suffix, final=False):
        return [row for role, tag in (final_tags if final else tags) for row in csv_rows(home/role/(tag+suffix))]
    merged, merged_info = family(home/'central/merged')
    local, _ = family(home/'central/central-source'); local_replica, _ = family(home/'central/central-replica')
    member_bytes = metadata(home/'central/merged/merge-sources')
    return dict(result=result, plan=json.loads((root.parent/'plan.json').read_text()), streams=streams,
                merged=merged, merged_info=merged_info, local=local, local_replica=local_replica,
                membership=struct.unpack('<'+'Q'*(len(member_bytes)//8), member_bytes),
                messages=packets, syns=syns, physical=csv_rows(root/'physical.csv'),
                credits=combined('.credits.csv'), receipts=combined('.receipts.csv', True), channels=combined('.channels.csv', True),
                records=csv_rows(home/'central/records.csv'),
                placement=[json.loads((home/role/(tag+'.writer.json')).read_text()) for role, tag in tags],
                namespaces=[json.loads((root/(r+'.runtime.json')).read_text())['netns'] for r in ROLES],
                producers={(r, tag): json.loads((home/r/(tag+'.producer.json')).read_text()) for r, tag in tags},
                lifecycle={r: journal(home/r/'producer-lifecycle', bytes) for r in ('front', 'rear')} if replacement else {},
                before={8200+i: family(root/(target+'-before-restart')/f'source-{p}')[0]
                        for i, (p, r, _) in enumerate(SOURCES) if r == target} if replacement else {},
                boot=[csv_rows(root/(p+'.events.csv')) for p in (('central-1', 'central-1-rejoined') if replacement else ('central-1',))],
                cuts=csv_rows(home/'central/central-1.cuts.csv'), delivery=csv_rows(home/'central/central-1.delivery.csv'),
                injection=int((root/'inject').read_text()) if (root/'inject').exists() else 0)


def judge(d):
    result = d['result']; replacement = result['case'] == 'restart-live'; target = result['fault_target']; streams = d['streams']
    require(result['pass'] and not result['forced_cleanup'] and not result['sanitizer_diagnostics'] and not result['sdk_errors'], 'native runtime verdict')
    require(d['plan']['diagnostic_epochs'] and all(v['epochs'] and v['pass'] for v in result['diagnostics'].values()), 'explicit family profile')
    require(len(set(d['namespaces'])) == 3, 'independent ECU namespaces')
    require(all(p['allowed_cpus'] == [15] and p['policy'] == p['priority'] == 0 for p in d['placement']), 'non-RT writer placement')
    require(all(int(r['dropped']) == int(r['rejected']) == 0 and 0 < int(r['highwater']) <= 8 for r in d['channels']), 'bounded SDK ingress')
    require(d['membership'] == (1, 8000, *range(8200, 8209), 8300), 'fixed logical membership')
    expected_epochs = {1, 2} if replacement else {1}
    merged = [event(raw) for raw in d['merged']]; identities = [e['_id'] for e in merged]
    require(len(set(identities)) == len(identities), 'unique merged identities')
    epochs = [e['epoch'] for e in merged]
    require(epochs == sorted(epochs) and set(epochs) == expected_epochs and d['merged_info']['segments'] == len(expected_epochs), 'old tails precede new checkpoint')
    contexts = {e['epoch']: (raw, e) for raw, e in zip(d['merged'], merged) if e['kind'] == 6}
    require(set(contexts) == expected_epochs and sum(e['kind'] == 6 for e in merged) == len(contexts), 'genuine global Sessions only')
    for epoch, rows in enumerate(d['boot'], 1):
        raw, e = contexts[epoch]
        require(e['_id'][:2] == (8001, 7) and e['received_roles'] == 255 and int.from_bytes(raw[-34:-30], 'little') == 255, 'full original Release masks')
        acks = [r for r in rows if r['event'] == 'session-ack' and r['value'] == '20']
        require(len(acks) == 8 and {int(r['role']) for r in acks} == set(range(8)), 'actual eight-role Release')
        times = sorted(int(r['ns']) for r in acks)
        require(times[-2] <= e['source_ns'] <= times[-1] <= e['observed_ns'], 'original Release completion observation')
    require(d['local'] == d['local_replica'] and all(event(raw)['_id'][1] in (7, 8) for raw in d['local']), 'Central spool original replica')
    union = {event(raw)['_id']: raw for raw in d['local']}
    for stream, s in streams.items():
        rows = s['source']; decoded = [event(raw) for raw in rows]
        require(rows == s['replica'] and s['info']['stream'] == s['replica_info']['stream'] == stream, 'exact stable stream replica')
        require(s['info']['segments'] == s['replica_info']['segments'] == len(expected_epochs), 'source and replica rollover')
        require(rows[0] == contexts[1][0] and [e['epoch'] for e in decoded] == sorted(e['epoch'] for e in decoded), 'ordered original prefix')
        if stream < 8200:
            require(rows == [contexts[i][0] for i in sorted(contexts)], 'unmodified context route')
        else:
            by_producer = {}
            for e in decoded:
                if e['kind'] == 6: continue
                producer = ((1 << 32) | s['producer']) if replacement and s['sender'] == target and e['epoch'] == 2 else s['producer']
                require(e['_id'][1] == producer, 'trusted local producer lineage')
                by_producer.setdefault(producer, []).append(e['event_sequence'])
            require(all(sequences == list(range(1, len(sequences)+1)) for sequences in by_producer.values()), 'original producer sequences never reused or skipped')
        for raw in rows:
            identity = event(raw)['_id']; require(identity not in union or union[identity] == raw, 'shared context canonical bytes'); union[identity] = raw
    require({event(raw)['_id']: raw for raw in d['merged']} == union, 'no lost, fabricated or recounted original')
    receipts = {int(r['stream']): r for r in d['receipts']}
    require(len(receipts) == len(d['receipts']) == 12 and set(receipts) == {*streams, 8300}, 'all final durable receipts')
    for stream, r in receipts.items():
        count = len(d['local']) if stream == 8300 else len(streams[stream]['source'])
        require(int(r['entries']) == int(r['acknowledged']) == count and int(r['segments']) == len(expected_epochs), 'sender fully acknowledged')
    data_seen, ack_seen, replayed, leases = set(), set(), set(), set()
    for m in d['messages']:
        if m['method'] == 0x50: leases.add(lease(m['payload']))
        if m['service'] < 0x5d00: continue
        kind, stream, ordinal, payload = wire(m['payload']); require(stream in streams, 'declared wire stream')
        s = streams[stream]; require(1 <= ordinal <= len(s['source']), 'committed ordinal only')
        sender, receiver = (s['sender'], s['receiver']) if kind == 1 else (s['receiver'], s['sender'])
        require(m['service'] == (s['rep'] if kind == 1 else s['pub']) and m['method'] == (0x101 if kind == 1 else 0x102), 'diagnostic lane direction')
        require(m['flow'][0] == IPS[sender] and m['flow'][1] == IPS[receiver] and m['flow'][3] == 31610+ROLES.index(receiver), 'actual TCP ECU route')
        raw = s['source'][ordinal-1]
        require(payload == raw if kind == 1 else int.from_bytes(payload, 'little') == zlib.crc32(raw), 'canonical original Data/ACK')
        (data_seen if kind == 1 else ack_seen).add((stream, ordinal))
        if replacement and kind == 1 and s['sender'] == target and ordinal == 1 and m['client'] == CLIENTS[target]+1: replayed.add(stream)
    expected = {(s, i+1) for s, value in streams.items() for i in range(len(value['source']))}
    require(data_seen == ack_seen == expected, 'all committed originals and ACKs on actual TCP')
    require(len(d['credits']) == 9*len(expected_epochs), 'each actual endpoint credit captured')
    expected_credits = {((((1 << 32) | base) if replacement and role == target and epoch == 2 else base), epoch)
                        for base, role, _ in SOURCES for epoch in expected_epochs}
    require({(int(r['producer']), int(r['epoch'])) for r in d['credits']} == expected_credits, 'every producer has its own accepted evidence')
    for r in d['credits']:
        role = next(s[2] for s in SOURCES if s[0] == (int(r['producer']) & 0xffffffff))
        values = tuple(int(r[k]) for k in ('epoch', 'requested_ns', 'prepare_deadline_ns', 'enable_ns', 'commit_deadline_ns', 'lease_sequence', 'source_ns', 'expiry_ns'))
        require((role, *values) in leases and values[3] == contexts[values[0]][1]['_enable']['ns'] and values[-2] <= int(r['captured_ns']) < values[-1], 'actual accepted credit matches original control wire')
    gaps = [e for e in merged if e['code'] == 0x5001 and e['kind'] == 1]
    if replacement:
        crash = result['injected_crash']; victims = [p for p in result['processes'] if p['role'] == target]
        require(crash['role'] == target and len(victims) == 2 and victims[0]['exit'] == -9 and victims[0]['expected_abrupt_stop'] and victims[1]['exit'] == 0, 'actual replacement SIGKILL')
        require(result['survivor_pids_before'] == result['survivor_pids_after'] and len(result['survivor_pids_after']) == 2 and crash['pid'] not in result['survivor_pids_after'].values(), 'surviving ECU identities unchanged')
        require(replayed == set(d['before']) and replayed, 'new SDK client replays old stream ordinal1')
        for stream, before in d['before'].items():
            require(before and streams[stream]['source'][:len(before)] == before and all(event(raw)['epoch'] == 1 for raw in before), 'old process committed prefix preserved')
        require(len(d['cuts']) == 1 and d['cuts'][0]['retired_epoch'] == '1', 'one explicit owner retirement cut')
        cut = int(d['cuts'][0]['observed_ns'])
        require(any(r['event'] == 'ingress-transition-begin' and int(r['ns']) <= cut for r in d['boot'][0]), 'cut after actual owner transition begins')
        require(all(int(r['wall_ns']) >= cut for r in d['delivery'] if r['action'] == 'local-spool' and r['epoch'] == '2'), 'Central new prefix after retirement cut')
        for role in ('front', 'rear'):
            lifecycle = [event(raw) for raw in d['lifecycle'][role]]
            require([e['kind'] for e in lifecycle] == ([9, 9, 0] if role == target else [9, 0]) and all(e['_id'][1] == 9100+ROLES.index(role) for e in lifecycle), 'original process lifecycle')
            require([e['epoch'] for e in lifecycle] == ([1, 2, 2] if role == target else [1, 1]) and
                    [e['event_sequence'] for e in lifecycle] == ([1, 3, 4] if role == target else [1, 2]), 'durable generation allocation never reused')
        metadata = d['producers'][(target, target+'-2')]
        require(metadata['generation'] == 2 and metadata['previous_unclean'], 'unclean successor identity')
        expected_gaps = {((1 << 32) | base) for base, role, _ in SOURCES if role == target}
        require({e['_id'][1] for e in gaps} == expected_gaps and len(gaps) == len(expected_gaps), 'one continuity incident per replaced source')
        for e in gaps:
            require(e['event_sequence'] == 1 and e['epoch'] == 2 and e['_before'] == 1 and e['_after'] == 2 and e['_unknown'] and e['_unmapped'] and e['_proof'] == 0 and e['measured'] == 0 and e['detected_ns'] == metadata['boot_ns'], 'unknown precommit loss remains explicit')
    else:
        require(not gaps and not d['cuts'], 'no invented replacement or continuity incident')
    if result['case'] != 'normal':
        require(any(d['injection'] <= int(r['ns']) <= d['injection']+100_000_000 and abs(float(r['torque'])) <= 1 and float(r['pressure']) >= 100000 for r in d['physical']), 'original 100ms physical protection')
    if d['plan']['diagnostic_drop_ack']:
        require(result['diagnostics']['central']['ack_omitted'] and result['diagnostics']['central']['duplicates'] > 0, 'lost ACK retried without recount')
    require(all(r['count'] == r['generation'] == '1' and r['cleared'] == '0' for r in d['records']), 'DTC history not recounted or cleared')
    for e in merged:
        require(e['_run'] == 8001 and e['_profile'] == 1 and e['epoch'] in expected_epochs, 'original run/profile')
        if e['kind'] == 5:
            proof = next((p for p in merged if p['_id'] == e['_proof_event']), None)
            require(e['epoch'] == 2 and e['_id'][1] < (1 << 32) and proof and proof['_id'][1] == e['_id'][1] and proof['_proof'] == e['_proof'] and proof['epoch'] == 2 and proof['kind'] in (0, 4), 'continuous source recovery needs fresh proof')
    return dict(passed=True, streams=len(streams), merged=d['merged_info'], gaps=len(gaps), original_credits=len(d['credits']), tcp_messages=len(d['messages']), connections=d['syns'])


def mutations(data):
    names = ['membership', 'merged-original', 'credit', 'wire-ack', 'receipt', 'queue-loss']
    if data['result']['case'] == 'restart-live': names += ['prefix', 'retirement', 'producer-reuse', 'erase-gap', 'physical', 'lifecycle', 'no-old-replay']
    for name in names:
        d = copy.deepcopy(data)
        if name == 'membership': d['membership'] = d['membership'][:-1]
        elif name == 'merged-original': d['merged'].pop()
        elif name == 'credit': d['credits'][0]['source_ns'] = '0'
        elif name == 'wire-ack': d['messages'] = [m for m in d['messages'] if m['method'] != 0x102]
        elif name == 'receipt': d['receipts'][0]['acknowledged'] = '0'
        elif name == 'queue-loss': d['channels'][0]['dropped'] = '1'
        elif name == 'prefix': d['before'][next(iter(d['before']))] = []
        elif name == 'retirement': d['cuts'] = []
        elif name == 'producer-reuse': next(s for s in d['streams'].values() if s['sender'] == d['result']['fault_target'])['producer'] += 100
        elif name == 'erase-gap': d['merged'] = [r for r in d['merged'] if event(r)['code'] != 0x5001]
        elif name == 'physical':
            for row in d['physical']: row['pressure'] = '0'
        elif name == 'lifecycle': d['lifecycle'][d['result']['fault_target']] = []
        else: d['messages'] = [m for m in d['messages'] if not(m['client'] == CLIENTS[d['result']['fault_target']]+1 and m['method'] == 0x101)]
        try: judge(d)
        except (ValueError, KeyError, IndexError): continue
        raise ValueError('mutation accepted: '+name)
    return len(names)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('directory', type=Path); p.add_argument('--mutations', action='store_true'); a = p.parse_args()
    data = load(a.directory); result = judge(data)
    if a.mutations: result['mutations_rejected'] = mutations(data)
    print(json.dumps(result, sort_keys=True))

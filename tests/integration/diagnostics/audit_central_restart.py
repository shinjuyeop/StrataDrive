#!/usr/bin/env python3
"""Independent Central SIGKILL, trusted issuer succession and fresh replica audit."""
import argparse
import copy
import json
from pathlib import Path
import zlib
from audit_control_diagnostics import csv_rows, event, journal, require
from audit_native_adoption import prefix
from audit_native_routing import SOURCES, ROLES, IPS, CLIENTS, wire, lease
from audit_someip_diagnostics import pcap

SUCCESSOR = (1 << 32) | 7
OBSERVER = (1 << 32) | 8


def load(root):
    home = root/'native-diagnostics'; central = home/'central'; streams = {}; bindings = {}
    clients = {r: (c, c+1) if r == 'central' else (c,) for r, c in CLIENTS.items()}
    def add(stream, sender, receiver, source, replica, pub, rep, old):
        streams[stream] = dict(source=prefix(source), replica=prefix(replica), old=prefix(old, True), sender=sender, receiver=receiver, pub=pub, rep=rep)
        bindings[(rep, 0x101)] = clients[sender]; bindings[(pub, 0x102)] = clients[receiver]
    for z, role in enumerate(('front', 'rear')):
        add(8101+z, 'central', role, central/f'context-{z}-2', home/role/'context', 0x5e00+2*z, 0x5e01+2*z, central/f'context-{z}')
    for i, (producer, role, _) in enumerate(SOURCES):
        add(8200+i, role, 'central', home/role/f'source-{producer}', central/f'source-{producer}-2', 0x5e10+2*i, 0x5e11+2*i, central/f'source-{producer}')
    for sid, sender in [(0x5344, 'central'), (0x5345, 'central'), (0x5348, 'central'), (0x5349, 'central'), (0x5346, 'front'), (0x5347, 'front'), (0x534a, 'rear'), (0x534b, 'rear')]:
        for method in (0x10, 0x20, 0x40, 0x50, 0x60, 0x70, 0x80): bindings[(sid, method)] = clients[sender]
    messages, syns = pcap(root/'traffic.pcap', (*range(30501, 30509), 31610, 31611, 31612), tuple(IPS.values()), bindings)
    tags = [('central', 'central-1'), ('central', 'central-2'), ('front', 'front-1'), ('rear', 'rear-1')]
    release_rows=[csv_rows(central/(tag+'.release.csv')) for tag in ('central-1','central-2')]
    if json.loads((root.parent/'plan.json').read_text()).get('diagnostic_service'):release_rows=[release_rows[0],*[ [r for r in release_rows[1] if int(r['epoch'])==e] for e in (2,3)]]
    return dict(result=json.loads((root/'result.json').read_text()), plan=json.loads((root.parent/'plan.json').read_text()), streams=streams,
                merged=journal(central/'merged-2', bytes), old=prefix(central/'merged', True), records=csv_rows(central/'records.csv'),
                history=csv_rows(central/'central-2.history.csv'), releases=release_rows,
                delivery=csv_rows(central/'central-2.delivery.csv'), credits=[row for r in ('front', 'rear') for row in csv_rows(home/r/(r+'-1.credits.csv'))],
                metadata=json.loads((central/'central-2.producer.json').read_text()), lifecycle={r: journal(home/r/'producer-lifecycle', bytes) for r in ROLES},
                placements=[json.loads((home/r/(tag+'.writer.json')).read_text()) for r, tag in tags],
                physical=csv_rows(root/'physical.csv'), messages=messages, syns=syns, injection=int((root/'inject').read_text()))


def judge(d, service=False):
    epochs=(1,2,3) if service else (1,2)
    r = d['result']; streams = d['streams']; crash = r['injected_crash']
    require(r['pass'] and r['rear']['pass'] and not r['forced_cleanup'] and not r['sanitizer_diagnostics'] and not r['sdk_errors'], 'original runtime/physical verdict')
    require(d['plan']['diagnostic_central_restart'] and r['case'] == 'central-rejoin' and crash['role'] == 'central', 'explicit Central process restart')
    processes = [p for p in r['processes'] if p['role'] == 'central']
    require(len(processes) == 2 and processes[0]['expected_abrupt_stop'] and processes[0]['exit'] == -9 and processes[1]['exit'] == 0, 'actual Central SIGKILL and new successful process')
    require(r['central_rejoined'] and r['survivor_pids_before'] == r['survivor_pids_after'] and set(r['survivor_pids_after']) == {'front', 'rear'} and crash['pid'] not in r['survivor_pids_after'].values(), 'surviving ECU PIDs unchanged')
    require(all(p['allowed_cpus'] == [(d['plan'].get('auxiliary_placement') or {}).get('cpu',15)] and p['policy'] == p['priority'] == 0 for p in d['placements']), 'actual non-RT writer placement')
    merged = [event(raw) for raw in d['merged']]; ids = [e['_id'] for e in merged]
    require(len(set(ids)) == len(ids), 'unique merged identities')
    sessions = {e['epoch']: (raw, e) for raw, e in zip(d['merged'], merged) if e['kind'] == 6}
    require(set(sessions) == set(epochs) and sum(e['kind'] == 6 for e in merged) == len(epochs), 'two original global Sessions')
    for epoch, releases in enumerate(d['releases'], 1):
        raw, e = sessions[epoch]
        require(e['_id'][:2] == (8001, 7 if epoch == 1 else SUCCESSOR) and e['source_producer'] == e['_id'][1] and e['received_roles'] == 255 and int.from_bytes(raw[-34:-30], 'little') == 255, 'explicit issuer lineage and complete global masks')
        require(len(releases) == 8 and {int(a['role']) for a in releases} == set(range(8)) and all(int(a['epoch']) == epoch for a in releases), 'eight original accepted Release ACKs')
        require(max(int(a['ns']) for a in releases) == e['source_ns'] and e['_enable']['ns'] <= e['source_ns'] <= e['observed_ns'], 'original final ACK is Session source, never receipt time')
    expected = {e['_id'] for e in merged if e['_id'][1] in (7, 8, SUCCESSOR, OBSERVER)}
    for sid, s in streams.items():
        rows = s['source']['rows']
        require(rows == s['replica']['rows'] and rows and s['source']['stream'] == s['replica']['stream'] == sid and s['source']['registry'] == s['replica']['registry'] == 3, 'fresh exact replica and canonical manifest')
        require(s['old']['rows'] and rows[:len(s['old']['rows'])] == s['old']['rows'], 'old committed prefix retained unmodified')
        require(rows[0] == sessions[1][0] and sessions[2][0] in rows, 'original contexts precede actual epoch events')
        if sid < 8200: require(rows == [sessions[i][0] for i in epochs], 'fresh context source imports old ordinal before new Session')
        else:
            own = [event(raw) for raw in rows if event(raw)['kind'] != 6]
            require(all(e['_id'][1] == SOURCES[sid-8200][0] for e in own) and [e['event_sequence'] for e in own] == list(range(1, len(own)+1)), 'surviving source producer and sequence unchanged')
        for raw in rows:
            identity = event(raw)['_id']; expected.add(identity)
            require(identity in ids and d['merged'][ids.index(identity)] == raw, 'exact durable original in new merged store')
    require(set(ids) == expected, 'no erased or fabricated history')
    predecessors = {8000: d['old'], **{sid:s['old'] for sid, s in streams.items() if sid >= 8200}}
    require(len(d['history']) == len(predecessors), 'all old collector histories reported')
    for row in d['history']:
        old = predecessors[int(row['store'])]
        require(int(row['committed']) == len(old['rows']) and int(row['uncommitted_bytes']) == len(old['tail']) and int(row['writable']) == int(not old['tail'] and not old['incomplete']), 'old suffix/completeness reported honestly')
        for raw in old['rows']: require(raw in d['merged'], 'old committed original preserved')
    data_seen = set(); ack_seen = set(); fresh_acks = set(); leases = set()
    for m in d['messages']:
        if m['method'] == 0x50: leases.add(lease(m['payload']))
        if m['service'] < 0x5d00: continue
        kind, sid, ordinal, payload = wire(m['payload']); require(sid in streams, 'provisioned diagnostic stream'); s = streams[sid]; rows = s['source']['rows']
        require(1 <= ordinal <= len(rows), 'committed ordinal only')
        sender, receiver = (s['sender'], s['receiver']) if kind == 1 else (s['receiver'], s['sender'])
        require(m['service'] == (s['rep'] if kind == 1 else s['pub']) and m['method'] == (0x101 if kind == 1 else 0x102) and m['flow'][0] == IPS[sender] and m['flow'][1] == IPS[receiver] and m['flow'][3] == 31610+ROLES.index(receiver), 'canonical separate IP lane')
        require(payload == rows[ordinal-1] if kind == 1 else int.from_bytes(payload, 'little') == zlib.crc32(rows[ordinal-1]), 'canonical original Data/ACK')
        (data_seen if kind == 1 else ack_seen).add((sid, ordinal))
        if kind == 2 and sid >= 8200 and m['client'] == CLIENTS['central']+1: fresh_acks.add((sid, ordinal))
    all_rows = {(sid, i+1) for sid, s in streams.items() for i in range(len(s['source']['rows']))}
    require(data_seen == ack_seen == all_rows and fresh_acks == {p for p in all_rows if p[0] >= 8200}, 'every surviving source ordinal replayed and ACKed by new SDK client')
    require({int(a['stream']) for a in d['delivery'] if a['action'] == 'replica-commit' and a['ordinal'] == '1'} == set(range(8200, 8209)), 'fresh collector starts every replica at original ordinal1')
    require(len(d['credits']) == 9*len(epochs), 'two actual credits for every surviving source')
    for row in d['credits']:
        role = next(s[2] for s in SOURCES if s[0] == int(row['producer']))
        values = tuple(int(row[k]) for k in ('epoch', 'requested_ns', 'prepare_deadline_ns', 'enable_ns', 'commit_deadline_ns', 'lease_sequence', 'source_ns', 'expiry_ns'))
        require((role, *values) in leases and values[3] == sessions[values[0]][1]['_enable']['ns'] and sessions[values[0]][1]['source_ns'] <= values[-2] <= int(row['captured_ns']) < values[-1], 'actual local accepted credit matches native control wire')
    for role, raws in d['lifecycle'].items():
        rows = [event(raw) for raw in raws]
        require([e['kind'] for e in rows] == ([9, 9, 0] if role == 'central' else [9, 0]) and all(e['_id'][1] == 9100+ROLES.index(role) for e in rows), 'durable process lifecycle')
        if role == 'central': require([e['event_sequence'] for e in rows] == [1, 3, 4] and [e['epoch'] for e in rows] == [1, 2, 2], 'unclean Central generation never reused')
    gaps = [e for e in merged if e['kind'] == 1 and e['code'] == 0x5001]; meta = d['metadata']
    require(meta['generation'] == 2 and meta['previous_unclean'] and len(gaps) == 1, 'one unverified Central process continuity incident')
    e = gaps[0]
    require(e['_id'][1:] == (OBSERVER, 1) and e['epoch'] == 2 and e['detected_ns'] == meta['boot_ns'] and e['_unknown'] and e['_unmapped'] and e['_before'] == 1 and e['_after'] == 2 and e['_proof'] == 0 and e['measured'] == 0, 'original unverified boot observation, no invented loss count/proof')
    require(all(a['cleared'] == '0' for a in d['records']) and any(int(a['code']) == 0x5001 for a in d['records']), 'successful rejoin/replay cannot clear continuity DTC')
    require(not any(e['_id'][1] == OBSERVER and e['code'] == 0x5001 and e['kind'] != 1 for e in merged), 'no automatic Passed or recovery for unknown loss')
    require(any(d['injection'] <= int(p['ns']) <= d['injection']+100_000_000 and abs(float(p['torque'])) <= 1 and float(p['pressure']) >= 100000 for p in d['physical']), 'original100ms physical protection')
    require(all(e['_run'] == 8001 and e['_profile'] == 1 and e['epoch'] in epochs for e in merged), 'original run/profile/epochs')
    return dict(pass_=True, active_streams=len(streams), merged_events=len(merged), original_credits=len(d['credits']), gaps=len(gaps), tcp_messages=len(d['messages']), connections=d['syns'])


def mutations(data):
    names = ('issuer', 'release', 'old-prefix', 'tail', 'gap', 'boot', 'credit', 'fresh-ack', 'ordinal1', 'clear', 'physical', 'survivor')
    for name in names:
        d = copy.deepcopy(data)
        if name == 'issuer': d['streams'][8101]['source']['rows'].reverse()
        elif name == 'release': d['releases'][0].pop()
        elif name == 'old-prefix': d['old']['rows'].append(b'fabricated')
        elif name == 'tail': d['history'][0]['uncommitted_bytes'] = str(int(d['history'][0]['uncommitted_bytes'])+1)
        elif name == 'gap': d['merged'] = [raw for raw in d['merged'] if event(raw)['code'] != 0x5001]
        elif name == 'boot': d['metadata']['boot_ns'] += 1
        elif name == 'credit': d['credits'][0]['source_ns'] = '0'
        elif name == 'fresh-ack': d['messages'] = [m for m in d['messages'] if not(m['method'] == 0x102 and m['client'] == CLIENTS['central']+1)]
        elif name == 'ordinal1': d['delivery'] = [a for a in d['delivery'] if a['ordinal'] != '1']
        elif name == 'clear': d['records'][0]['cleared'] = '1'
        elif name == 'physical':
            for row in d['physical']: row['pressure'] = '0'
        else: d['result']['survivor_pids_after']['front'] += 1
        try: judge(d)
        except (ValueError, KeyError, IndexError): continue
        raise ValueError('mutation accepted: '+name)
    return len(names)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('directory', type=Path); parser.add_argument('--mutations', action='store_true'); args = parser.parse_args()
    data = load(args.directory); report = judge(data)
    if args.mutations: report['mutations_rejected'] = mutations(data)
    print(json.dumps(report, sort_keys=True))

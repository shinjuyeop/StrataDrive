#!/usr/bin/env python3
"""Independent local service review/clear and four real SIGKILL commit cuts."""
import argparse
import copy
import json
import struct
from pathlib import Path
import zlib
from audit_control_diagnostics import Reader, csv_rows, event, require
from audit_native_adoption import prefix


def evidence(r):
    stamps = {k:r.stamp() for k in ('now', 'enable', 'wheel', 'drive', 'brake')}
    return dict(**stamps, wheel_rad_s=r.real(), torque_nm=r.real(), pressure_pa=r.real(), valid=r.boolean(), inhibited=r.boolean())


def transaction(raw):
    if raw[0] == 0: return dict(tag=0, event=event(raw), related=struct.unpack_from('<QQQ', raw, 27), raw=raw)
    r = Reader(raw); tag = r.uint(1); identity = r.identity()
    if tag == 2:
        incident, proof = r.identity(), r.identity(); session = (r.uint(8), r.uint(4)); revision, disposition = r.uint(8), r.uint(1); service = evidence(r)
        count = r.uint(4); require(1 <= count <= 32, 'review stream bound')
        cuts = [dict(stream=r.uint(8), producer=r.uint(8), committed=r.uint(8), tip=r.identity(), crc=r.uint(4)) for _ in range(count)]
        value = dict(tag=tag, id=identity, incident=incident, proof=proof, session=session, revision=revision, disposition=disposition, evidence=service, streams=cuts)
    elif tag == 1:
        session = (r.uint(8), r.uint(4)); service = evidence(r); all_ = r.boolean(); count = r.uint(4); require(1 <= count <= 4096, 'clear target bound')
        targets = [dict(key=tuple(r.uint(width) for width in (2, 4, 4, 4)), revision=r.uint(8)) for _ in range(count)]
        value = dict(tag=tag, id=identity, session=session, evidence=service, all=all_, targets=targets)
    else: raise ValueError('unknown local service tag')
    require(r.pos == len(raw), 'canonical service transaction length'); return value


def load(root):
    cases = []
    for cut in range(1, 5):
        directory = root/f'cut-{cut}'; store = prefix(directory/'case')
        cases.append(dict(stage=cut, store=store, entries=[transaction(raw) for raw in store['rows']], summary=json.loads((directory/'summary.json').read_text()),
                          source=[prefix(directory/f'source-{i}') for i in range(2)], replica=[prefix(directory/f'replica-{i}') for i in range(2)]))
    return dict(cases=cases, release=csv_rows(root/'release.csv'), credits=csv_rows(root/'credits.csv'))


def fresh(e, enable):
    now = e['now']; require(e['valid'] and e['inhibited'] and 0 <= e['wheel_rad_s'] <= .01 and abs(e['torque_nm']) <= .1 and 100000 <= e['pressure_pa'] <= 1500000, 'stationary inhibited current service inputs')
    require(e['enable'] == enable and now['domain'] == 2 and now['instance'] == 99 and now['trusted'] and now['present'] and now['ns'] >= enable['ns'], 'original service clock/enable')
    times = []
    for key in ('wheel', 'drive', 'brake'):
        stamp = e[key]; require(stamp['domain'] == now['domain'] and stamp['instance'] == now['instance'] and stamp['present'] and stamp['trusted'] and enable['ns'] <= stamp['ns'] <= now['ns'] and now['ns']-stamp['ns'] <= 30000000, 'fresh original Actual source'); times.append(stamp['ns'])
    require(max(times)-min(times) <= 20000000, 'original Actual skew')


def judge(d):
    original = d['cases'][0]['store']['rows'][:5]; require(len(original) == 5, 'committed original baseline')
    incident = event(original[2]); identity = incident['_id']; key = (incident['code'], incident['component'], incident['monitor'], incident['subject'])
    require(identity == (10, (1 << 32)|30, 1) and incident['kind'] == 1 and incident['code'] == 0x5001 and incident['_unknown'] and incident['_unmapped'] and incident['_proof'] == 0 and incident['measured'] == 0 and incident['_before'] == 1 and incident['_after'] == 2, 'immutable original unknown-loss incident, never a zero-loss assertion')
    sessions = {event(raw)['epoch']:event(raw) for raw in original if event(raw)['kind'] == 6}; require(set(sessions) == {2, 3}, 'fresh actual global Session after incident')
    for raw in original:
        if event(raw)['kind'] == 6: require(int.from_bytes(raw[-34:-30], 'little') == 255, 'complete original expected role mask')
    for epoch, s in sessions.items():
        rows = [r for r in d['release'] if int(r['epoch']) == epoch]
        require(len(rows) == 8 and {int(r['role']) for r in rows} == set(range(8)) and max(int(r['ns']) for r in rows) == s['source_ns'] and s['received_roles'] == 255, 'all eight original accepted Release ACKs')
    require(len(d['credits']) == 4 and {(int(r['epoch']), int(r['role'])) for r in d['credits']} == {(epoch, role) for epoch in (2, 3) for role in (0, 1)}, 'both real accepted endpoint credits in both epochs')
    for r in d['credits']:
        s = sessions[int(r['epoch'])]; require(int(r['enable']) == s['_enable']['ns'] and s['source_ns'] <= int(r['source']) <= int(r['captured']) < int(r['expiry']), 'original credit/Session clock ordering')
    for case in d['cases']:
        cut = case['stage']; entries = case['entries']; summary = case['summary']; rows = case['store']['rows']
        require(case['store']['registry'] == 4 and case['store']['stream'] == 9000 and len(rows) == 5+cut and rows[:5] == original, 'local registry4 and unchanged original prefix')
        require(summary['stage'] == cut and summary['pid'] > 0 and summary['signal'] == 9 and summary['watermark'] == len(rows) and summary['count'] == summary['generation'] == 1 and summary['condition'] == 0 and summary['cleared'] == (cut == 4), 'real SIGKILL committed boundary and conservative reopen projection')
        proof = entries[5]['event']; require(proof['_id'] == (10, 99, 1) and proof['kind'] == 0 and proof['_proof'] == 8 and proof['_occurrence'] == incident['_occurrence'] and entries[5]['related'] == identity and proof['epoch'] == 3 and proof['_unknown'] and not proof['_unmapped'] and proof['_latch'] == 2, 'fresh recording proof concerns current state and retains unknown history')
        require(proof['observed_ns'] == proof['source_ns'] and proof['_enable'] == sessions[3]['_enable'], 'recording observation source and actual enable')
        for i, producer in enumerate(((1 << 32)|30, 31)):
            source, replica = case['source'][i], case['replica'][i]; require(source['rows'] == replica['rows'] and source['stream'] == replica['stream'] == 500+i and source['registry'] == replica['registry'] == 3, 'exact independently committed current source/replica')
            require(event(source['rows'][0])['_id'] == sessions[2]['_id'] and event(source['rows'][-1])['_id'] == sessions[3]['_id'], 'actual original context precedes current recording cut')
            require(all(event(raw)['kind'] == 6 or event(raw)['_id'][1] == producer for raw in source['rows']), 'trusted source binding')
        if cut >= 2:
            review = entries[6]; require(review['tag'] == 2 and review['id'] == (10, 99, 2) and review['incident'] == identity and review['proof'] == proof['_id'] and review['session'] == (10, 3) and review['revision'] == 3 and review['disposition'] == 1, 'explicit scoped unknown-history service disposition at exact revision')
            fresh(review['evidence'], sessions[3]['_enable']); require(review['evidence']['now']['ns'] == proof['observed_ns'], 'fresh inspected service cut')
            require(len(review['streams']) == 2, 'entire fixed source manifest covered')
            for i, c in enumerate(review['streams']):
                source = case['source'][i]; require((c['stream'], c['producer'], c['committed']) == (500+i, ((1 << 32)|30) if i == 0 else 31, len(source['rows'])) and c['tip'] == event(source['rows'][-1])['_id'] and c['crc'] == zlib.crc32(source['rows'][-1]), 'durable scope/ordinal/tip checksum attestation')
        if cut >= 3:
            passed = entries[7]['event']; require(passed['kind'] == 5 and passed['_id'] == (10, 99, 3) and passed['_proof_event'] == proof['_id'] and entries[7]['related'] == review['id'] and passed['_occurrence'] == incident['_occurrence'] and passed['_proof'] == 8 and passed['epoch'] == 3, 'separate Passed after durable disposition')
        if cut == 4:
            clear = entries[8]; require(clear['tag'] == 1 and clear['id'] == (10, 100, 1) and clear['session'] == (10, 3) and clear['targets'] == [dict(key=key, revision=8)] and not clear['all'], 'explicit exact-revision clear after Passed')
            fresh(clear['evidence'], sessions[3]['_enable'])
    return dict(pass_=True, crash_cuts=4, actual_release_acks=16, actual_credits=4, immutable_unknown_history=True, automatic_clear=False)


def mutations(data):
    names = ('disposition', 'incident', 'proof', 'partial-scope', 'ordinal', 'replica', 'release', 'credit', 'moving', 'clear-revision', 'fake-kill', 'missing-passed')
    for name in names:
        d = copy.deepcopy(data); c = d['cases'][3]
        if name == 'disposition': c['entries'][6]['disposition'] = 0
        elif name == 'incident': c['entries'][6]['incident'] = c['entries'][5]['event']['_id']
        elif name == 'proof': c['entries'][5]['related'] = (10, 31, 1)
        elif name == 'partial-scope': c['entries'][6]['streams'].pop()
        elif name == 'ordinal': c['entries'][6]['streams'][0]['committed'] += 1
        elif name == 'replica': c['replica'][0]['rows'].pop()
        elif name == 'release': d['release'].pop()
        elif name == 'credit': d['credits'][0]['source'] = '0'
        elif name == 'moving': c['entries'][6]['evidence']['wheel_rad_s'] = .02
        elif name == 'clear-revision': c['entries'][8]['targets'][0]['revision'] += 1
        elif name == 'fake-kill': c['summary']['signal'] = 0
        else: c['entries'][7]['event']['kind'] = 0
        try: judge(d)
        except (ValueError, KeyError, IndexError): continue
        raise ValueError('mutation accepted: '+name)
    return len(names)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('directory', type=Path); p.add_argument('--mutations', action='store_true'); args = p.parse_args()
    d = load(args.directory); report = judge(d)
    if args.mutations: report['mutations_rejected'] = mutations(d)
    print(json.dumps(report, sort_keys=True))

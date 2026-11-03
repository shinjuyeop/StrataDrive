#!/usr/bin/env python3
"""Independent local Linux peer service, original Actuals and durable cut audit."""
import argparse
import copy
import json
from pathlib import Path
import struct
import zlib
from audit_control_diagnostics import csv_rows, event, require
from audit_native_adoption import prefix
from audit_continuity_review import transaction, fresh


def load(root):
    cases = []
    for cut in range(1, 5):
        p = root/f'cut-{cut}'; store = prefix(p/'case')
        cases.append(dict(stage=cut, store=store, entries=[transaction(r) for r in store['rows']],
            summary=json.loads((p/'summary.json').read_text()), request=(p/'review.request').read_bytes(),
            sources=[prefix(p/f'source-{i}') for i in range(2)], replicas=[prefix(p/f'replica-{i}') for i in range(2)],
            samples=[dict(drive=(p/f'sample-{i}.drive').read_bytes(), brake=(p/f'sample-{i}.brake').read_bytes())
                     for i in range(1, {1:1, 2:2, 3:3, 4:5}[cut]+1)]))
    return dict(cases=cases, release=csv_rows(root/'release.csv'), credits=csv_rows(root/'credits.csv'))


def actual(raw, length, data_id):
    require(len(raw) == length and raw[2:4] == b'\x02\x01' and raw[24:29] == b'\x03\x02\0\0\0', 'original valid protection Actual metadata')
    crc = 0xffff
    for byte in raw[:29]+raw[31:]+struct.pack('<H', data_id):
        crc ^= byte << 8
        for _ in range(8): crc = ((crc << 1) ^ (0x1021 if crc & 0x8000 else 0)) & 0xffff
    require(crc == int.from_bytes(raw[29:31], 'little'), 'independent original Actual P05 checksum')
    sequence, epoch, source = struct.unpack_from('<IIQ', raw, 4)
    require(sequence > 0 and epoch == 3, 'original current Actual identity')
    return sequence, source


def sample_matches(evidence, sample):
    drive, brake = sample['drive'], sample['brake']; ds, dt = actual(drive, 64, 0x1202); bs, bt = actual(brake, 32, 0x1102)
    wheel_time = struct.unpack_from('<Q', drive, 40)[0]
    require(ds == bs and drive[34] == 1, 'both fresh Actual streams and independent wheel valid')
    require((evidence['drive']['ns'], evidence['brake']['ns'], evidence['wheel']['ns']) == (dt, bt, wheel_time), 'preserve original acquisitions, never replace by service polling time')
    require(evidence['torque_nm'] == struct.unpack_from('<h', drive)[0]*.1 and evidence['pressure_pa'] == int.from_bytes(brake[:2], 'little')*1000 and
            evidence['wheel_rad_s'] == int.from_bytes(drive[32:34], 'little')*.01, 'original physical value encoding')
    require(bt < dt < wheel_time < evidence['now']['ns'], 'distinct original acquisition times')


def judge(d):
    original = d['cases'][0]['store']['rows'][:5]; require(len(original) == 5, 'original immutable prefix')
    incident = event(original[2]); identity = (10, (1 << 32)|30, 1); key = (0x5001, 7, 10, 30)
    require(incident['_id'] == identity and incident['kind'] == 1 and incident['_unknown'] and incident['_unmapped'] and incident['measured'] == 0 and
            (incident['code'], incident['component'], incident['monitor'], incident['subject']) == key, 'unknown historical loss remains explicit')
    sessions = {event(r)['epoch']:event(r) for r in original if event(r)['kind'] == 6}; require(set(sessions) == {2, 3}, 'actual higher global Epoch')
    for epoch, global_ in sessions.items():
        rows = [r for r in d['release'] if int(r['epoch']) == epoch]
        require(global_['received_roles'] == 255 and len(rows) == 8 and {int(r['role']) for r in rows} == set(range(8)) and max(int(r['ns']) for r in rows) == global_['source_ns'], 'actual eight accepted original Release ACKs')
    require(len(d['credits']) == 4 and {(int(r['epoch']), int(r['role'])) for r in d['credits']} == {(e, r) for e in (2, 3) for r in (0, 1)}, 'actual accepted credit coverage')
    for r in d['credits']:
        global_ = sessions[int(r['epoch'])]; require(int(r['enable']) == global_['_enable']['ns'] and global_['source_ns'] <= int(r['source']) <= int(r['captured']) < int(r['expiry']), 'accepted original endpoint credit ordering')
    for case in d['cases']:
        cut, entries, summary = case['stage'], case['entries'], case['summary']; store = case['store']
        require(store['registry'] == 4 and store['stream'] == 9000 and store['rows'][:5] == original and len(entries) == 5+cut, 'local service committed prefix')
        require(summary['stage'] == cut and summary['signal'] == 9 and summary['condition'] == 0 and summary['cleared'] == (cut == 4) and summary['watermark'] == len(entries) and
                min(summary['server_pid'], summary['authorized_pid'], summary['denied_pid']) > 0 and len({summary['server_pid'], summary['authorized_pid'], summary['denied_pid']}) == 3, 'real separate server/client/unauthorized peer and SIGKILL checkpoint')
        request = case['request']; require(len(request) == 76 and request[:4] == b'SDS\x01' and request[4:20] == b'B'*16, 'bounded explicit local protocol / fixture boot capability')
        require(struct.unpack_from('<QQIQQQQBBH', request, 20) == (1, 10, 3, *identity, 3, 1, 1, 0), 'authorized exact incident/revision/session and explicit disposition')
        proof = entries[5]['event']; require(proof['_id'] == (10, 99, 1) and proof['kind'] == 0 and proof['_proof'] == 8 and proof['_occurrence'] == incident['_occurrence'] and entries[5]['related'] == identity and proof['_unknown'] and not proof['_unmapped'], 'fresh current recording proof retains unknown history')
        for i, source in enumerate(case['sources']):
            replica = case['replicas'][i]; producer = ((1 << 32)|30) if i == 0 else 31
            require(source['stream'] == replica['stream'] == 500+i and source['registry'] == replica['registry'] == 3 and source['rows'] == replica['rows'] and summary['source_acks'][i] == len(source['rows']), 'frozen full source/replica/actual ACK coverage')
            require(event(source['rows'][0])['_id'] == sessions[2]['_id'] and event(source['rows'][-1])['_id'] == sessions[3]['_id'] and all(event(r)['kind'] == 6 or event(r)['_id'][1] == producer for r in source['rows']), 'fixed manifest original context and producer')
        for sample in case['samples']: actual(sample['drive'], 64, 0x1202); actual(sample['brake'], 32, 0x1102)
        require(proof['source_ns'] == struct.unpack_from('<Q', case['samples'][0]['drive'], 12)[0]+2000 and proof['observed_ns'] == proof['source_ns'] and proof['epoch'] == 3, 'proof generated at first current capture')
        if cut >= 2:
            review = entries[6]; require(review['id'] == (10, 99, 2) and review['incident'] == identity and review['proof'] == proof['_id'] and review['revision'] == 3 and review['disposition'] == 1 and review['session'] == (10, 3), 'durable explicit Review binding')
            fresh(review['evidence'], sessions[3]['_enable']); sample_matches(review['evidence'], case['samples'][1]);require(len(review['streams']) == 2, 'whole manifest reviewed')
            for i, c in enumerate(review['streams']):
                source = case['sources'][i]; producer = ((1 << 32)|30) if i == 0 else 31
                require((c['stream'], c['producer'], c['committed'], c['tip'], c['crc']) == (500+i, producer, len(source['rows']), event(source['rows'][-1])['_id'], zlib.crc32(source['rows'][-1])), 'exact frozen source ordinal/tip/CRC')
        if cut >= 3:
            passed = entries[7]['event']; require(passed['_id'] == (10, 99, 3) and passed['kind'] == 5 and passed['_proof_event'] == proof['_id'] and entries[7]['related'] == review['id'] and passed['observed_ns'] > review['evidence']['now']['ns'] and passed['source_ns'] == proof['source_ns'] and passed['source_sequence'] == proof['source_sequence'], 'separate Passed after newly sampled Review')
        if cut == 4:
            clear = entries[8];require(clear['tag'] == 1 and clear['id'] == (10, 99, 8) and clear['session'] == (10, 3) and not clear['all'] and clear['targets'] == [dict(key=key, revision=8)], 'second explicit request clears exact Passed revision')
            fresh(clear['evidence'], sessions[3]['_enable']);sample_matches(clear['evidence'], case['samples'][4]);require(clear['evidence']['now']['ns'] > passed['observed_ns'], 'new physical evidence on separate clear')
    return dict(pass_=True, crash_cuts=4, actual_release_acks=16, actual_credits=4, original_actual_pairs=11, immutable_unknown_history=True, automatic_clear=False, scope='local Linux peer service; injected logical clock and Actuals, not live three-ECU service')


def mutations(data):
    names = ('capability', 'explicit-disposition', 'peer', 'partial-manifest', 'acks', 'tip', 'release', 'credit', 'wheel-time', 'actual-crc', 'actual-value', 'clear-revision', 'clear-time', 'passed-binding', 'proof-acquisition', 'unknown-history')
    for name in names:
        d = copy.deepcopy(data);c = d['cases'][3]
        if name in ('capability', 'explicit-disposition'):
            r = bytearray(c['request']);r[4 if name == 'capability' else 73] ^= 1;c['request'] = bytes(r)
        elif name == 'peer': c['summary']['denied_pid'] = c['summary']['authorized_pid']
        elif name == 'partial-manifest': c['entries'][6]['streams'].pop()
        elif name == 'acks': c['summary']['source_acks'][0] -= 1
        elif name == 'tip': c['entries'][6]['streams'][0]['crc'] ^= 1
        elif name == 'release': d['release'].pop()
        elif name == 'credit': d['credits'][0]['source'] = '0'
        elif name == 'wheel-time': c['entries'][6]['evidence']['wheel']['ns'] += 1
        elif name == 'actual-crc':
            b = bytearray(c['samples'][1]['drive']);b[29] ^= 1;c['samples'][1]['drive'] = bytes(b)
        elif name == 'actual-value': c['entries'][6]['evidence']['torque_nm'] = .1
        elif name == 'clear-revision': c['entries'][8]['targets'][0]['revision'] += 1
        elif name == 'clear-time': c['entries'][8]['evidence']['now']['ns'] = c['entries'][7]['event']['observed_ns']
        elif name == 'passed-binding': c['entries'][7]['related'] = (10, 99, 1)
        elif name == 'proof-acquisition': c['entries'][7]['event']['source_ns'] += 1
        elif name == 'unknown-history': c['store']['rows'][2] = c['store']['rows'][1]
        try: judge(d)
        except ValueError: continue
        raise ValueError('mutation accepted: '+name)
    return len(names)


def main():
    p = argparse.ArgumentParser(description=__doc__);p.add_argument('root', type=Path);p.add_argument('--mutations', action='store_true');a = p.parse_args()
    d = load(a.root);report = judge(d)
    if a.mutations: report['mutations_rejected'] = mutations(d)
    print(json.dumps(report, sort_keys=True));return 0


if __name__ == '__main__': raise SystemExit(main())

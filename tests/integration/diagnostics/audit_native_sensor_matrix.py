#!/usr/bin/env python3
"""Independent canonical DTC/native/physical audit of the fixed M9 sensor matrix."""
import argparse
import copy
import json
import re
import struct
from pathlib import Path

from audit_control_diagnostics import csv_rows, journal, require


def load(path):
    match = re.fullmatch(r'bms(\d+)_power([0-3])_(recover|latched)', path.name)
    require(match is not None, 'named recipe')
    return dict(bms=int(match[1]), power=int(match[2]), recover=match[3] == 'recover',
                registry=struct.unpack_from('<I', (path/'store/manifest').read_bytes(), 32)[0],
                events=journal(path/'store'), native=csv_rows(path/'native.csv'),
                samples=csv_rows(path/'samples.csv'), records=csv_rows(path/'records.csv'),
                physical=csv_rows(path/'physical.csv'),
                owners=csv_rows(path/'logical-native-sensor-fault-events.csv'),
                runtime=json.loads((path/'logical-native-sensor-fault.json').read_text()))


def judge(d):
    mask, power, recover = d['bms'], d['power'], d['recover']
    require(mask in (0, 1, 2, 4, 8, 16, 32, 64, 128, 170) and (mask or power), 'recipe bounds')
    require(not power or mask in (0, 170), 'fixed combination')
    r = d['runtime']; rows = d['events']; physical = d['physical']; owners = d['owners']
    require(d['registry'] == 2 and all(r[k] for k in ('passed', 'physical_ok', 'model_preserved', 'ownership_ok')), 'runtime/registry')
    require((r['native_bms_trip_mask'], r['native_power_sensor_fault'], r['native_input_restore_ns']) == (mask, power, 10_200_000_000), 'declared injection')
    require(r['duration_ns'] == (24 if recover else 14)*10**9 and r['recovery_ns'] == (20*10**9 if recover else 0), 'fixed windows')
    require(all(e['_run'] == 9501 and e['_id'][1] in (7, 30, 31, 32, 33) and not e['_unmapped'] and
                e['_enable']['domain'] == 1 and e['_enable']['instance'] == 9501 for e in rows), 'source dictionary')
    for who in {e['_id'][1] for e in rows}:
        sequences = [e['event_sequence'] for e in rows if e['_id'][1] == who]
        require(sequences == list(range(1, len(sequences)+1)), 'source sequence continuity')
    sessions = [e for e in rows if e['kind'] == 6]
    require([e['epoch'] for e in sessions] == ([1, 2] if recover else [1]) and
            all(e['_id'][1] == 7 for e in sessions), 'real global release')
    for owner, needed in ((5, bool(mask)), (6, bool(power))):
        injections = [o for o in owners if o['kind'] == 'native-sensor-fault' and int(o['owner']) == owner]
        restores = [o for o in owners if o['kind'] == 'native-sensor-restored' and int(o['owner']) == owner]
        require(len(injections) == len(restores) == int(needed), 'input-copy transition count')
        if needed:
            require(int(injections[0]['time_ns']) == 11_000_000_000 and int(restores[0]['time_ns']) == 11_200_000_000, 'original injection clocks')
    require(not any(o['kind'] in ('fault-observed', 'leaf-protection-selected', 'zone-protection-ack') and
                    int(o['time_ns']) < 11_000_000_000 for o in owners), 'no prior fault')
    expected = {}
    if mask: expected[8] = (0x3101, 10, 32, 2)
    if power and not (mask and power == 3): expected[9] = (0x3201, 6, 33, {1: 5, 2: 6, 3: 8}[power])
    faults = [e for e in rows if e['kind'] == 1]; passes = [e for e in rows if e['kind'] == 5]
    require(len(faults) == len(d['records']) == len(expected) and {e['monitor'] for e in faults} == set(expected), 'intrinsic root count')
    require(len(passes) == (len(expected) if recover else 0), 'no implicit recovery')
    by_id = {e['_id']: e for e in rows}
    for f in faults:
        monitor = f['monitor']; code, actor, producer, reason = expected[monitor]
        require((f['code'], f['component'], f['_id'][1], f['native_reason'], f['epoch']) ==
                (code, actor, producer, reason, 1) and not f['_unknown'], 'original intrinsic reason')
        source = [n for n in d['native'] if (int(n['producer']), int(n['event_sequence'])) == f['_id'][1:]]
        require(len(source) == 1, 'native snapshot count'); n = source[0]
        require(int(n['reason']) == reason and n['propagation'] == '0' and int(n['observed_ns']) == f['detected_ns'] and
                int(n['epoch']) == 1 and int(n['model_epoch']) == f['_model'] == 7 and
                int(n['state']) == f['_before'] and int(n['detail']) == f['_after'], 'native snapshot correlation')
        require(f['detected_ns'] >= 11_000_000_000, 'detector follows injection')
        samples = [s for s in d['samples'] if (int(s['producer']), int(s['event_sequence'])) == f['_id'][1:]]
        require(len(samples) == 5 and [int(s['slot']) for s in samples] == list(range(5)), 'fault input slots')
        for s in samples[:5 if monitor == 8 else 1]:
            require(s['present'] == '1' and s['epoch'] == '7' and
                    int(n['enable_ns']) <= int(s['dependency_ns']) <= int(s['source_ns']) <= f['detected_ns'] and
                    f['detected_ns']-int(s['source_ns']) <= int(n['source_age_ns']), 'original fault acquisition')
        if monitor == 8:
            require(int(n['detail']) == mask and f['detected_ns']-int(n['violation_ns']) == 40_000_000 and
                    f['detected_ns'] <= 11_060_000_000, 'original BMS dwell/mask')
            values = [(3, 'v0', 2.7), (3, 'v1', 4.3), (1, 'v0', 279), (1, 'v0', 426),
                      (4, 'v0', -35), (4, 'v1', 65), (1, 'v1', -110), (1, 'v1', 260)]
            for bit, (slot, field, value) in enumerate(values):
                if mask & (1 << bit): require(float(samples[slot][field]) == value, 'declared raw trip input')
        elif mask and power == 2:
            require(int(n['state']) == 9 and int(n['contactor_timeout_ns']) == 100_000_000 and
                    f['detected_ns']-int(n['phase_origin_ns']) == 100_000_000, 'original shutdown contactor deadline')
        else:
            require(f['detected_ns'] <= 11_010_000_000, 'Power Ready detection')
        if monitor == 9 and power == 2: require(int(n['detail']) & 4, 'original precharge feedback mismatch')
        if monitor == 9 and power == 3: require(float(samples[0]['v1']) == 200, 'original low bus acquisition')
        matching = [rec for rec in d['records'] if int(rec['monitor']) == monitor]
        require(len(matching) == 1, 'projection count'); rec = matching[0]
        require((int(rec['code']), int(rec['component']), int(rec['subject'])) == (code, actor, reason) and
                all(rec[k] == v for k, v in [('condition', '2' if recover else '1'), ('count', '1'), ('generation', '1'), ('cleared', '0')]), 'history and latch')
        response = [p for p in physical if int(p['source_ns']) >= f['detected_ns'] and p['gate'] == '0' and
                    abs(float(p['torque_nm'])) <= 1 and float(p['pressure_pa']) >= 1_000_000]
        require(response and int(response[0]['source_ns'])-f['detected_ns'] <= 230_000_000, 'measured physical response')
        if recover:
            good = [e for e in passes if e['monitor'] == monitor]
            require(len(good) == 1, 'single qualified pass'); p = good[0]; proof = by_id.get(p['_proof_event'])
            require(p['epoch'] == 2 and p['_occurrence'] == f['_occurrence'] and p['_id'][1] == producer and
                    p['related_sequence'] == f['event_sequence'] and p['_latch'] == 2, 'same retained occurrence')
            require(proof and proof['kind'] == 0 and proof['_id'][1] == producer and proof['epoch'] == 2 and
                    proof['_occurrence'] == f['_occurrence'] and proof['_proof'] == p['_proof'] == (1 if monitor == 8 else 2) and
                    proof['event_sequence'] < p['event_sequence'], 'qualified source proof')
            require(p['source_ns'] > sessions[1]['_enable']['ns'], 'INIT is not recovery')
            ns = [n for n in d['native'] if (int(n['producer']), int(n['event_sequence'])) == p['_id'][1:]]
            require(len(ns) == 1, 'recovery native snapshot'); n = ns[0]
            require(n['reason'] == '0' and n['qualified'] == '1' and n['propagation'] == '0' and n['epoch'] == '2' and
                    int(n['state']) == (2 if monitor == 8 else 7) and int(n['observed_ns']) == p['source_ns'] and
                    int(n['enable_ns']) == sessions[1]['_enable']['ns'], 'actual healthy native state')
            samples = [s for s in d['samples'] if (int(s['producer']), int(s['event_sequence'])) == p['_id'][1:]]
            require(len(samples) == 5 and {int(s['slot']) for s in samples} == set(range(5)), 'native sample slots')
            for s in samples[:5 if monitor == 8 else 2]:
                source, dependency = int(s['source_ns']), int(s['dependency_ns'])
                require(s['present'] == '1' and int(s['epoch']) == (2 if monitor == 9 and s['slot'] == '1' else 7) and
                        p['_enable']['ns'] <= dependency <= source <= p['source_ns'] and
                        p['source_ns']-source <= int(n['source_age_ns']) and
                        p['source_ns']-dependency <= int(n['dependency_age_ns']), 'original fresh recovery acquisition')
    if mask and power in (2, 3):
        propagation = [e for e in rows if e['kind'] == 0 and e['monitor'] == 9 and e['_unknown']]
        require(propagation and propagation[0]['code'] == 0 and propagation[0]['native_reason'] == 4 and
                propagation[0]['detected_ns'] < next(f for f in faults if f['monitor'] == 8)['detected_ns'], 'BMS inhibition precedes own fault')
    require(len(physical) == (2400 if recover else 1400) and all(p['model_epoch'] == '7' and
            abs(float(p['balance_j'])) <= 1e-5 for p in physical), 'physical denominator/energy')
    for a, b in zip(physical, physical[1:]):
        require(int(b['source_ns'])-int(a['source_ns']) == 10_000_000 and int(b['model_sequence']) > int(a['model_sequence']) and
                float(b['distance_m']) >= float(a['distance_m']), 'physical continuity')
    held = [p for p in physical if 14_000_000_000 <= int(p['source_ns']) < 21_000_000_000]
    require(held and all(p['gate'] == '0' and p['contacts'] == '0' and float(p['bus_v']) <= 30 and
                        abs(float(p['speed_mps'])) <= .01 for p in held), 'stationary HV-off interval')
    require(r['replaced_links'] == int(recover), 'explicit rejoin only')
    return dict(passed=True, roots=len(faults), qualified_passes=len(passes), physical_samples=len(physical), events=len(rows))


def mutations(data):
    names = ['false-reason', 'false-detection', 'erased-history', 'false-response', 'physical-reset', 'false-HV-off', 'wrong-injection', 'restamped-fault']
    if data['recover']: names += ['INIT-as-pass', 'wrong-proof', 'stale-recovery']
    for name in names:
        d = copy.deepcopy(data)
        if name == 'false-reason': next(e for e in d['events'] if e['kind'] == 1)['native_reason'] = 999
        elif name == 'false-detection': next(e for e in d['events'] if e['kind'] == 1)['detected_ns'] -= 1
        elif name == 'erased-history': d['records'][0]['count'] = '0'
        elif name == 'false-response':
            for p in d['physical']:
                if 11_000_000_000 <= int(p['source_ns']) < 11_500_000_000: p['pressure_pa'] = '0'
        elif name == 'physical-reset': d['physical'][1200]['model_sequence'] = '1'
        elif name == 'false-HV-off': d['physical'][1300]['contacts'] = '3'
        elif name == 'wrong-injection': d['runtime']['native_input_restore_ns'] += 1
        elif name == 'restamped-fault':
            f = next(e for e in d['events'] if e['kind'] == 1)
            next(s for s in d['samples'] if (int(s['producer']), int(s['event_sequence'])) == f['_id'][1:])['source_ns'] = str(f['detected_ns']+1)
        elif name == 'INIT-as-pass': next(e for e in d['events'] if e['kind'] == 5)['source_ns'] = next(e for e in d['events'] if e['kind'] == 6 and e['epoch'] == 2)['_enable']['ns']
        elif name == 'wrong-proof': next(e for e in d['events'] if e['kind'] == 5)['_proof_event'] = (9501, 7, 999)
        else:
            p = next(e for e in d['events'] if e['kind'] == 5)
            next(s for s in d['samples'] if (int(s['producer']), int(s['event_sequence'])) == p['_id'][1:])['source_ns'] = '1'
        try: judge(d)
        except ValueError: pass
        else: raise ValueError('accepted mutation: '+name)
    return names


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path); parser.add_argument('--mutations', action='store_true')
    args = parser.parse_args(); data = load(args.directory); result = judge(data)
    if args.mutations: result['mutations_rejected'] = mutations(data)
    print(json.dumps(result, indent=2))

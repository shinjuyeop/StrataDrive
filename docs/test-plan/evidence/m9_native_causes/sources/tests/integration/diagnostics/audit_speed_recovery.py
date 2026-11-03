#!/usr/bin/env python3
"""Independent M9 SD-1001 recovery/clear audit; never imports the C++ projection."""
import argparse
import copy
import json
from pathlib import Path
from audit_control_diagnostics import Reader, csv_rows, event, journal, require


def transaction(payload):
    if payload[0] == 0:
        return dict(tag='event', value=event(payload))
    r = Reader(payload)
    require(r.uint(1) == 1, 'clear tag')
    identity, run, epoch = r.identity(), r.uint(8), r.uint(4)
    stamps = {name: r.stamp() for name in ('now', 'enable', 'wheel', 'drive', 'brake')}
    wheel, torque, pressure = r.real(), r.real(), r.real()
    streams, inhibited, all_ = r.boolean(), r.boolean(), r.boolean()
    size = r.uint(4)
    require(0 < size <= 4096, 'clear count')
    targets = [(r.uint(2), r.uint(4), r.uint(4), r.uint(4), r.uint(8)) for _ in range(size)]
    require(r.pos == len(payload), 'clear trailing bytes')
    return dict(tag='clear', value=dict(id=identity, run=run, epoch=epoch, stamps=stamps,
                wheel=wheel, torque=torque, pressure=pressure, streams=streams, inhibited=inhibited,
                all=all_, targets=targets))


def load(directory):
    return dict(entries=journal(directory/'store', transaction), checkpoints=csv_rows(directory/'checkpoints.csv'),
                physical=csv_rows(directory/'physical.csv'), energy=csv_rows(directory/'energy.csv'),
                actuals=csv_rows(directory/'logical-speed-input-loss.csv'),
                control=csv_rows(directory/'control.csv'), owners=csv_rows(directory/'logical-speed-input-loss-events.csv'),
                runtime=json.loads((directory/'logical-speed-input-loss.json').read_text()))


def judge(data):
    entries, checkpoints = data['entries'], data['checkpoints']
    rows = [e['value'] for e in entries if e['tag'] == 'event']
    clears = [e['value'] for e in entries if e['tag'] == 'clear']
    require(data['runtime']['passed'] and len(clears) == 1, 'runtime/clear count')
    require(all(e['_run'] == 2001 and e['_id'][:2] == (2001, 7) and not e['_unmapped'] for e in rows), 'event identity')
    require([e['event_sequence'] for e in rows] == list(range(1, len(rows)+1)), 'event sequence')
    sessions = [e for e in rows if e['kind'] == 6]
    require([e['epoch'] for e in sessions] == [1, 2, 3], 'INIT epochs')
    faults = [e for e in rows if e['kind'] == 1]
    require(len(faults) == 2 and all((e['code'], e['component'], e['monitor'], e['subject'], e['native_reason']) ==
                                  (0x1001, 1, 1, 1, 768) for e in faults), 'SD-1001 episodes')
    require([e['epoch'] for e in faults] == [1, 3] and
            all(injection <= e['detected_ns'] < injection+20_000_000 and
                any(o['kind'] == 'fault-observed' and int(o['epoch']) == e['epoch'] and int(o['time_ns']) == e['detected_ns'] for o in data['owners'])
                for e, injection in zip(faults, (11_000_000_000, 37_000_000_000))), 'actual detection times')
    passed = [e for e in rows if e['kind'] == 5]
    require(len(passed) == 1, 'qualified pass count')
    p = passed[0]
    require(p['epoch'] == 2 and p['_occurrence'] == faults[0]['_occurrence'] and p['related_sequence'] == faults[0]['event_sequence'] and
            p['_proof'] == 1 and p['_latch'] == 2, 'qualified pass identity')
    proof = next((e for e in rows if e['_id'] == p['_proof_event']), None)
    require(proof is not None and proof['kind'] == 4 and proof['_proof'] == 1 and proof['epoch'] == 2 and
            proof['_occurrence'] == p['_occurrence'], 'original recovery proof')
    now = p['observed_ns']
    require(21_000_000_000 < now < 23_000_000_000, 'INIT alone does not pass')
    command = p['_command']
    roots = [c for c in data['control'] if 0 <= now-int(c['now_ns']) <= 30_000_000 and int(c['epoch']) == 2 and
             int(c['sequence']) == command['sequence'] and int(c['source_ns']) == command['source']['ns'] and
             int(c['expiry_ns']) == command['expiry']['ns']]
    require(len(roots) == 1 and p['source_producer'] == 11 and p['source_ns'] == p['actual_source_ns'] == command['source']['ns'] and
            0 <= now-p['source_ns'] <= 30_000_000 and now < command['expiry']['ns'], 'native successful accepted root/source')
    clear = clears[0]
    require(clear['id'] == (2001, 99, 1) and clear['run'] == 2001 and clear['epoch'] == 2 and not clear['all'] and
            clear['targets'][0][:4] == (0x1001, 1, 1, 1) and len(clear['targets']) == 1, 'explicit selective clear')
    times = clear['stamps']
    require(times['now']['ns'] == 29_000_000_000 and times['enable'] == sessions[1]['_enable'], 'clear time/session enable')
    require(all(s['trusted'] and s['present'] and s['domain'] == 1 and s['instance'] == 2001 for s in times.values()), 'trusted clear clock')
    sources = [times[s]['ns'] for s in ('wheel', 'drive', 'brake')]
    require(clear['streams'] and clear['inhibited'] and 0 <= clear['wheel'] <= .01 and abs(clear['torque']) <= .1 and
            100_000 <= clear['pressure'] <= 1_500_000 and min(sources) >= times['enable']['ns'] and
            0 <= times['now']['ns']-max(sources) and times['now']['ns']-min(sources) <= 30_000_000 and
            max(sources)-min(sources) <= 20_000_000, 'stationary safe clear evidence')
    # Independently fold only the DTC condition/generation/revision contract.
    condition, cleared, generation, count, revision, epoch, pass_id = 0, 0, 1, 0, 0, 0, None
    target_revision = None
    for number, entry in enumerate(entries, 1):
        e = entry['value']
        if entry['tag'] == 'clear':
            require(condition == 2 and not cleared and epoch == 2 and pass_id is not None and
                    e['targets'][0][4] == target_revision, 'clear projection/precondition')
            cleared, target_revision = 1, number
        elif e['kind'] == 6:
            epoch, condition, pass_id = e['epoch'], 0, None
        elif e['kind'] == 1:
            if cleared:
                generation, count, cleared = generation+1, 0, 0
            count, condition, target_revision = count+1, 1, number
        elif e['kind'] == 5:
            condition, pass_id, target_revision = 2, e['_id'], number
        revision = number
    require((condition, cleared, generation, count) == (1, 0, 2, 1), 'recurrence history')
    by_time = {int(c['now_ns']): c for c in checkpoints}
    at_restore, at_run, at_clear, at_restart, final = (by_time[t] for t in (14_000_000_000, 23_000_000_000, 29_000_000_000, 30_000_000_000, 41_000_000_000))
    require((at_restore['epoch'], at_restore['gate'], at_restore['condition'], at_restore['cleared']) == ('1', '0', '1', '0') and
            at_restore['speed_fault'] != '0', 'restoration keeps protection')
    require((at_run['epoch'], at_run['gate'], at_run['condition'], at_run['cleared']) == ('2', '1', '2', '0'), 'passed retains DTC')
    require(at_clear['normal_armed'] == '0' and at_clear['stopping'] == '1' and at_clear['stop_state'] == '5' and
            at_clear['core_fault'] == '0' and at_clear['speed_fault'] == '0' and at_clear['cleared'] == '1', 'actual stop for clear')
    require(abs(float(at_clear['wheel_rad_s'])-clear['wheel']) < 1e-12 and
            abs(float(at_clear['torque_nm'])-clear['torque']) < 1e-12 and
            abs(float(at_clear['pressure_pa'])-clear['pressure']) < 1e-9, 'clear actual values')
    stopped = [a for a in data['actuals'] if 0 <= times['now']['ns']-int(a['source_ns']) <= 10_000_000]
    require(len(stopped) == 1 and stopped[0]['normal_armed'] == '0' and stopped[0]['stop_state'] == '5' and
            stopped[0]['management'] == '6' and stopped[0]['contacts'] == '0' and float(stopped[0]['bus_v']) <= 30, 'original Complete/HV-off actual')
    require(at_restart['cleared'] == '1' and at_restart['condition'] == '0' and at_restart['count'] == '1', 'replay keeps tombstone, current health unknown')
    require((final['condition'], final['cleared'], final['generation'], final['count']) == ('1', '0', '2', '1'), 'projection crosscheck')
    for fault in faults:
        selections = [e for e in rows if e['kind'] == 2 and e['epoch'] == fault['epoch']]
        require({e['received_roles'] for e in selections} == {4, 8, 16, 32, 64}, 'both epochs retain local selections')
        for e in selections:
            require(e['related_sequence'] == fault['event_sequence'] and e['selected_ns'] >= fault['detected_ns'] and
                    any(o['kind'] == 'leaf-protection-selected' and int(o['time_ns']) == e['selected_ns'] and
                        int(o['epoch']) == e['epoch'] and (1 << int(o['owner'])) == e['received_roles'] for o in data['owners']), 'original local selection')
    require(any(o['kind'] == 'explicit-dtc-clear' and int(o['time_ns']) == times['now']['ns'] for o in data['owners']), 'explicit service action')
    physical = data['physical']
    require(len(physical) == 4000 and all(int(r['model_epoch']) == 7 and abs(float(r['balance_j'])) <= 1e-5 for r in physical), 'physical model identity/balance')
    for a, b in zip(physical, physical[1:]):
        require(int(b['model_sequence']) > int(a['model_sequence']) and int(b['source_ns'])-int(a['source_ns']) == 10_000_000 and
                float(b['distance_m']) >= float(a['distance_m']), 'physical continuity')
    energy = data['energy']
    require(len(energy) > 3900 and float(energy[-1]['received_dc_j']) > 0 and all(int(e['model_epoch']) == 7 and
            abs(float(e['combined_balance_j'])) <= .001 and abs(float(e['coupling_balance_j'])) <= 1e-6 for e in energy), 'EV cumulative balance/regeneration')
    energy_by_time = {int(e['end_ns']): e for e in energy}
    initial = 180_000_000*.63
    for row in physical:
        e = energy_by_time.get(int(row['source_ns']))
        if e:
            require(abs(float(row['energy_j'])-(initial-float(e['battery_draw_j']))) <= 1e-5, 'chemical energy continuity')
    return dict(pass_=True, events=len(rows), clear_transactions=len(clears), faults=2, qualified_pass_ns=now,
                first_detected_ns=faults[0]['detected_ns'], recurrence_ns=faults[1]['detected_ns'], generation=generation,
                physical_samples=len(physical), energy_samples=len(energy), transaction_watermark=revision)


def mutations(data):
    cases = []
    for name in ('pass-reference', 'clear-moving', 'clear-revision', 'clear-untrusted', 'clear-armed', 'cleared-history', 'model-reset', 'missing-first-selection'):
        d = copy.deepcopy(data)
        rows = [e['value'] for e in d['entries'] if e['tag'] == 'event']
        c = next(e['value'] for e in d['entries'] if e['tag'] == 'clear')
        if name == 'pass-reference':
            next(e for e in rows if e['kind'] == 5)['_proof_event'] = (2001, 7, 999)
        elif name == 'clear-moving': c['wheel'] = 1
        elif name == 'clear-revision': c['targets'][0] = (*c['targets'][0][:4], 999)
        elif name == 'clear-untrusted': c['stamps']['wheel']['trusted'] = False
        elif name == 'clear-armed':
            next(e for e in d['checkpoints'] if e['now_ns'] == '29000000000')['normal_armed'] = '1'
        elif name == 'cleared-history': d['checkpoints'][-1]['generation'] = '1'
        elif name == 'model-reset': d['physical'][3200]['model_sequence'] = '1'
        elif name == 'missing-first-selection':
            d['owners'] = [o for o in d['owners'] if not (o['kind'] == 'leaf-protection-selected' and o['epoch'] == '1')]
        try:
            judge(d)
        except (ValueError, StopIteration):
            cases.append(name)
        else:
            raise ValueError('mutation accepted: '+name)
    return cases


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    parser.add_argument('--mutations', action='store_true')
    args = parser.parse_args()
    data = load(args.directory)
    result = judge(data)
    if args.mutations:
        result['mutations_rejected'] = mutations(data)
    print(json.dumps(result, indent=2))

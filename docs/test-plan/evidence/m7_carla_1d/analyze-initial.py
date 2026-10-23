#!/usr/bin/env python3
"""Independent raw-trace oracle. Logical cadence != wall-time freshness."""
import argparse
import json
import math
from pathlib import Path


def check(ok, reason):
    if not ok:
        raise ValueError(reason)


def rows(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s]


def stats(values):
    ordered = sorted(values)
    return {'count': len(values), 'mean': sum(values)/len(values),
            'p95': ordered[math.ceil(.95*len(values))-1],
            'p99': ordered[math.ceil(.99*len(values))-1], 'max': max(values)}


def analyze_case(folder, count, fault):
    result = json.loads((folder/'result.json').read_text())
    ticks, packets = rows(folder/'ticks.jsonl'), rows(folder/'packets.jsonl')
    check(result['status'] == 'COLLECTED', 'collection failed')
    check(result['collection_ticks'] == count and len(ticks) == count+1, 'incomplete collection/cleanup ticks')
    for i, t in enumerate(ticks):
        check(t['frame'] == t['snapshot_frame'] == t['previous_frame']+1, 'tick frame mismatch')
        check(t['end_ns'] >= t['begin_ns'], 'wall clock reversal')
        check(abs(t['delta_s']-.01) <= 1e-6 and abs(t['sim_s']-t['previous_sim_s']-.01) <= 1e-6, '10ms cadence')
        if i:
            check(t['frame'] == ticks[i-1]['frame']+1 and t['previous_sim_s'] == ticks[i-1]['sim_s'] and
                  t['begin_ns'] >= ticks[i-1]['end_ns'], 'tick discontinuity')
    frames = [t['frame'] for t in ticks[:count]]
    first = frames[0]
    by_frame = {t['frame']: t for t in ticks[:count]}
    index = {}
    for p in packets:
        key = p['frame'], p['stream']
        check(p['frame'] in by_frame and p['stream'] in ('state', 'rgb.front', 'gt.front'), 'unexpected packet')
        check(key not in index, 'duplicate stored packet')
        check(p['run_id'] == result['run_id'] and p['plant_epoch'] == result['plant_epoch'], 'epoch contamination')
        check(p['sequence'] == p['frame'] and p['validity'] == 'valid', 'identity/validity')
        check(p['source_time_ns'] == round(p['timestamp_seconds']*1e9), 'source restamp')
        check(abs(p['timestamp_seconds']-by_frame[p['frame']]['sim_s']) <= 1e-6, 'wrong acquisition frame/time')
        if p['stream'] != 'state':
            check(p['source_id'] == f"sensor:{result['sensors'][p['stream']]['id']}", 'sensor identity')
            check(p['width'] == 800 and p['height'] == 600 and p['stride'] == 3200 and p['encoding'] == 'BGRA8', 'camera schema')
            check(p['delivery_monotonic_ns'] >= p['arrival_monotonic_ns'], 'delivery before callback')
        else:
            check(p['source_id'] == f"ego:{result['ego_id']}", 'ego identity')
        if p['stream'] == 'gt.front':
            check(sum(p['class_histogram'].values()) == 480000 and len(p['class_histogram']) > 1, 'GT labels')
        index[key] = p
    phases, windows = {}, {}
    for stream in ('rgb.front', 'gt.front'):
        observed = sorted(f for f, s in index if s == stream)
        startup = [f for f in observed if f < first+100]
        check(startup, 'camera phase not established during startup')
        # Freeze the first startup phase; main gaps cannot redefine cadence.
        phases[stream] = startup[0] % 5
        check(all(f % 5 == phases[stream] for f in observed), 'camera stride changed')
    check(phases['rgb.front'] == phases['gt.front'], 'RGB/GT phases differ')
    drops = {(e['frame'], e['stream']) for e in result['events'] if e['reason'] == 'injected_drop'}
    expected_drops = {(f, 'state') for f in range(first+130, first+135)} if fault else set()
    if fault:
        expected_drops |= {(f, s) for s, phase in phases.items() for f in range(first+130, first+135) if f % 5 == phase}
    check(drops == expected_drops, 'fault injection mismatch')
    check(not any(e['reason'] in ('overflow', 'closed_callback') for e in result['events']), 'callback loss outside injection')
    check(not result['join_events'], 'unexpected duplicate/reorder/epoch rejection')
    for name, selected in [('startup', frames[:100]), ('main', frames[100:-100]), ('drain', frames[-100:])]:
        windows[name] = {}
        for stream in ('state', 'rgb.front', 'gt.front'):
            expected = [f for f in selected if stream == 'state' or f % 5 == phases[stream]]
            missing = [f for f in expected if (f, stream) not in index]
            injected = [f for f in expected if (f, stream) in drops]
            windows[name][stream] = {'expected': len(expected), 'received': len(expected)-len(missing), 'missing_frames': missing}
            if name == 'main' or stream == 'state':
                check(missing == injected, f'unexpected {name} {stream} loss')
    for f in frames:
        rgb, gt = index.get((f, 'rgb.front')), index.get((f, 'gt.front'))
        if rgb and gt:
            check(abs(rgb['timestamp_seconds']-gt['timestamp_seconds']) <= 1e-6 and rgb['pose_carla'] == gt['pose_carla'], 'RGB/GT mismatch')
    for channel, allowed in [('online', {'state', 'rgb.front'}), ('training_evaluation', {'gt.front'})]:
        check(rows(folder/channel/'records.jsonl') == [p for p in packets if p['stream'] in allowed], 'channel contamination/loss')
    # Simulation-time consumer replay of live state packets, no native ECU claims.
    current, age_trace = None, []
    for t in ticks[:count]:
        current = index.get((t['frame'], 'state'), current)
        age = round(t['sim_s']*1e9)-current['source_time_ns'] if current else None
        check(age is None or age >= 0, 'future source')
        age_trace.append({'frame': t['frame'], 'source_frame': current['frame'] if current else None,
                          'source_time_ns': current['source_time_ns'] if current else None,
                          'age_ns': age, 'available': age is not None and age <= 30_000_000})
    stale = [a for a in age_trace if not a['available']]
    check(bool(stale) == fault, 'logical stale result')
    if fault:
        check([a['frame'] for a in stale] == [first+133, first+134], 'state drop did not yield 40/50ms stale')
        check(age_trace[135]['age_ns'] == 0, 'new measured state did not recover availability')
    pause = result.get('pause')
    if not fault:
        check(pause and pause['before_frame'] == pause['after_frame'] and
              pause['before_sim_s'] == pause['after_sim_s'] and pause['end_ns']-pause['begin_ns'] >= 250_000_000,
              'pause failed')
    check(result['callback_quiet'] and not any(result['listeners_after_stop'].values()) and
          not result['remaining_owned_ids'] and len(result['destroy_results']) == 3 and all(result['destroy_results'].values()), 'cleanup')
    check(max(result['queue_high_water'].values()) <= 64, 'queue bound')
    collection = ticks[:count]
    wall = (collection[-1]['end_ns']-collection[0]['begin_ns'])/1e9
    gaps = [(collection[i]['end_ns']-collection[i-1]['end_ns'])/1e6 for i in range(1, count)]
    excluding_pause = [gap for i, gap in enumerate(gaps, 1)
                       if not pause or collection[i-1]['frame'] != pause['before_frame']]
    deliveries = [p['arrival_monotonic_ns'] for p in packets if p['stream'] == 'state']
    return {'status': 'PASS', 'scope': 'non-driving logical cadence/collection; no native ECU or wall freshness acceptance',
            'windows': windows, 'camera_phase_mod5': phases, 'sim_s': count*.01, 'collection_wall_s': wall,
            'real_time_factor': count*.01/wall, 'tick_rpc_ms': stats([(t['end_ns']-t['begin_ns'])/1e6 for t in collection]),
            'snapshot_completion_gap_ms_including_pause': stats(gaps),
            'snapshot_completion_gap_ms_excluding_pause': stats(excluding_pause),
            'completion_gaps_over_30ms_excluding_pause': sum(g > 30 for g in excluding_pause),
            'state_receipt_gap_ms_including_pause_and_drops': stats([(b-a)/1e6 for a, b in zip(deliveries, deliveries[1:])]),
            'logical_state_age_ns': stats([a['age_ns'] for a in age_trace]), 'stale_frames': stale,
            'wall_source_freshness': 'NOT RUN: acquisition clock mapping and ECU bridge unavailable',
            'wheel_feedback': 'NOT RUN: actor velocity is not measured wheel angular speed',
            'queue_high_water': result['queue_high_water']}


def analyze(attempt):
    summary = json.loads((attempt/'summary.json').read_text())
    check(summary['status'] == 'COLLECTED' and summary['versions'] == ['0.9.16']*2, 'incomplete runtime')
    check(summary['settings_before'] == summary['settings_after'] and not summary['remaining_actors'], 'final restore')
    check(summary['settings_during']['synchronous_mode'] and abs(summary['settings_during']['fixed_delta_seconds']-.01) < 1e-6, '10ms setup')
    reset = json.loads((attempt/'reset.json').read_text())
    check(reset['before_episode'] != reset['after_episode'] and reset['before_run'] != reset['after_run'] and
          reset['before_epoch'] == 1 and reset['after_epoch'] == 2, 'reset identity')
    check(len(reset['old_metadata_rejections']) == 3 and
          {r['stream'] for r in reset['old_metadata_rejections']} == {'state', 'rgb.front', 'gt.front'} and
          all(r['reason'] == 'old_epoch' for r in reset['old_metadata_rejections']), 'old metadata not rejected')
    return {'status': 'PASS', 'cases': {name: analyze_case(attempt/name, count, fault)
            for name, count, fault in [('nominal', 800, False), ('drop', 400, True), ('after_reset', 400, False)]}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('attempt', type=Path)
    args = parser.parse_args()
    result = analyze(args.attempt)
    (args.attempt/'offline-verification.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

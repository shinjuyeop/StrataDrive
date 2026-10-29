#!/usr/bin/env python3
"""Recompute the functional shadow verdict from raw trace; never a wall verdict."""
import argparse
import json
import math
from pathlib import Path


def require(value, why):
    if not value:
        raise ValueError(why)


def analyze(folder):
    process = json.loads((folder/'process.json').read_text())
    summary = json.loads((folder/'capture/summary.json').read_text())
    rows = [json.loads(line) for line in (folder/'capture/frames.jsonl').read_text().splitlines()]
    require(process['client_exit'] == 0 and not process['remaining_listeners'], 'client/cleanup')
    require(summary['status'] == 'SHADOW_COMPLETE' and summary['mode'] == 'functional-shadow' and
            summary['driving'] is False and summary['carla_apply_calls'] == 0, 'mode')
    require(summary['versions'] == ['0.9.16', '0.9.16'] and summary['ego']['physics'] is False, 'fixture')
    require(summary['scope'] == [1, 42, 7] and summary['clock_domain'] == 0x4D3746554E435449, 'trusted test scope')
    require(len(rows) == summary['ticks_completed'] == summary['ticks_planned'] == 320, 'frame count')
    require(not summary['overflow'] and summary['cleanup']['settings_restored'] and
            summary['cleanup']['remaining_owned'] == [] and not summary['cleanup'].get('errors'), 'cleanup')
    max_age, max_interval, armed = 0, 0, []
    gaps, native_times = [], []
    for index, row in enumerate(rows):
        reply = row['native']
        request = row['request'].split()
        require(row['index'] == index and len(request) == 8 and request[0] == 'STEP', 'STEP shape')
        require(list(map(int, request[1:4])) == summary['scope'] and int(request[4]) == summary['clock_domain'], 'scope')
        require(int(request[5]) == row['frame'] and float(request[6]) == row['sim_s'] and
                abs(float(request[7])-.01) < 1e-6, 'original request')
        require(reply['status'] == 'SHADOW_BARRIER' and reply['driving'] is False and reply['service_mask'] == 255, 'barrier')
        require(reply['next_frame'] == row['tick_frame'] == row['frame']+1, 'tick order')
        require(math.isfinite(row['sim_s']) and abs(reply['now_ns']-round(row['sim_s']*1e9)) <= 1, 'restamped clock')
        require(abs(row['tick_sim_s']-row['sim_s']-.01) < 1e-6, 'delta')
        require(row['begin_ns'] <= row['ack_ns'] <= row['tick_end_ns'], 'wall audit order')
        native_times.append((row['ack_ns']-row['begin_ns'])/1e6)
        if index:
            previous = rows[index-1]
            require(row['frame'] == previous['tick_frame'] and row['sim_s'] == previous['tick_sim_s'], 'frame chain')
            gaps.append((row['tick_end_ns']-previous['tick_end_ns'])/1e6)
        if reply['credit_mask']:
            require(reply['release_mask'] == reply['credit_mask'] == 255, 'credit before all release ACKs')
            require(reply['lease_expiry_ns']-reply['lease_source_ns'] == 60_000_000 and
                    0 <= reply['now_ns']-reply['lease_source_ns'] <= 30_000_000 and
                    reply['now_ns'] < reply['lease_expiry_ns'], 'native credit thresholds')
        if reply['armed_fixture']:
            armed.append(index)
            require(reply['actual_interval_fixture'] and reply['credit_mask'] == 255, 'fixture not ready')
            sources = reply['actual_sources_ns']
            require(len(sources) == 3 and max(sources)-min(sources) <= 10_000_000, 'Actual skew')
            for source in sources:
                age = reply['now_ns']-source
                require(0 <= age and age+10_000_000 <= 30_000_000, 'Actual source interval')
                max_age, max_interval = max(max_age, age), max(max_interval, age+10_000_000)
        if index >= 150:
            require(reply['armed_fixture'], 'main readiness')
    require(armed, 'no armed fixture')
    for injection in summary['injections']:
        require(injection['kind'] in ('slow-host', 'pause') and injection['wall_end_ns']-injection['wall_begin_ns'] >= 90_000_000, 'injection')
        row = rows[injection['index']]
        require(row['frame'] == injection['frame'] and row['sim_s'] == injection['sim_s'], 'pause restamp')
        require(rows[injection['index']-1]['tick_end_ns'] <= injection['wall_begin_ns'] <
                injection['wall_end_ns'] <= row['begin_ns'], 'pause audit order')
    require(len(summary['injections']) == 2, 'injection count')
    negative = summary['negative']
    require(negative['reply']['status'] == 'FAIL' and negative['reply']['next_frame'] is None and
            negative['frame_before'] == negative['frame_after'] == rows[-1]['tick_frame'] and summary['native_exit'] == 1,
            'tick after rejection')
    return {'functional_shadow': 'PASS', 'world_ticks': len(rows), 'armed_fixture_frames': len(armed),
            'first_armed_index': armed[0], 'max_actual_source_age_ms': max_age/1e6,
            'max_actual_source_interval_end_age_ms': max_interval/1e6,
            'max_wall_tick_gap_including_injections_ms': max(gaps),
            'native_barrier_wall_mean_ms': sum(native_times)/len(native_times),
            'native_barrier_wall_max_ms': max(native_times),
            'wall_deadline': 'NOT_RUN', 'carla_normal_driving': 'NOT_RUN',
            'carla_wheel_input': 'NOT_RUN', 'calibrated_actuation': 'NOT_RUN',
            'server_shutdown': 'PASS' if process['server_exit'] == 0 else 'FAIL',
            'server_exit': process['server_exit']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    args = parser.parse_args()
    result = analyze(args.folder)
    (args.folder/'analysis.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

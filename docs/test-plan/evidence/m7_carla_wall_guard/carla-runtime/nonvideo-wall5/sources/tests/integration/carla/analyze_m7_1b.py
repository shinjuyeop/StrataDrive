#!/usr/bin/env python3
"""Offline checks of raw M7-1b frame/packet traces; no CARLA dependency."""
import argparse
import json
import math
from pathlib import Path


def check(condition, reason):
    if not condition:
        raise ValueError(reason)


def read_lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def analyze(folder):
    result = json.loads((folder/'result.json').read_text())
    packets = read_lines(folder/'packets.jsonl')
    ticks = read_lines(folder/'ticks.jsonl')
    frames = [r['return_frame'] for r in ticks[:result['collection_ticks']]]
    check(len(frames) == result['collection_ticks'], 'missing tick trace')
    for i, tick in enumerate(ticks):
        check(tick['request_frame'] == tick['return_frame'] == tick['snapshot_frame'], 'tick ID mismatch')
        check(abs(tick['delta_seconds'] - 0.05) <= 1e-6, 'not 50ms')
        check(tick['end_ns'] >= tick['begin_ns'], 'wall clock rollback')
        if i:
            check(tick['return_frame'] == ticks[i-1]['return_frame']+1, 'frame gap')
            check(abs(tick['sim_seconds'] - ticks[i-1]['sim_seconds'] - 0.05) <= 1e-6, 'sim clock gap')
    index = {}
    classes = set()
    for packet in packets:
        key = packet['frame'], packet['stream']
        check(key not in index, 'duplicate stored packet')
        check(packet['run_id'] == result['run_id'] and packet['plant_epoch'] == result['plant_epoch'], 'epoch contamination')
        check(packet['source_time_ns'] == round(packet['timestamp_seconds']*1e9), 'source timestamp rewrite')
        check(packet['validity'] == 'valid', 'invalid stored packet')
        if packet['stream'] != 'state':
            check(packet['encoding'] == 'BGRA8' and packet['stride'] == 3200 and
                  packet['width'] == 800 and packet['height'] == 600, 'camera schema')
            check(packet['delivery_monotonic_ns'] >= packet['arrival_monotonic_ns'], 'delivery before arrival')
        if packet['stream'] == 'gt.front':
            check(sum(packet['class_histogram'].values()) == 800*600, 'GT histogram size')
            classes.update(int(k) for k in packet['class_histogram'])
        index[key] = packet
    joined = 0
    for frame in frames:
        group = [index.get((frame, stream)) for stream in ('rgb.front', 'gt.front', 'state')]
        if all(group):
            check(max(p['timestamp_seconds'] for p in group)-min(p['timestamp_seconds'] for p in group)
                  <= 1e-6, 'cross sensor timestamp mismatch')
            check(group[0]['pose_carla'] == group[1]['pose_carla'], 'camera pose mismatch')
            joined += 1
    windows = {}
    if 'windows' in result:
        for name, selected in [('startup', frames[:20]), ('main', frames[20:-20]), ('drain', frames[-20:])]:
            windows[name] = {stream: [f for f in selected if (f, stream) not in index]
                             for stream in ('rgb.front', 'gt.front', 'state')}
            for stream, lost in windows[name].items():
                check(lost == result['windows'][name]['streams'][stream]['missing_frames'], 'summary/raw missing mismatch')
        if not result['fault_injection']:
            check(not any(windows['main'].values()), 'main window loss')
        check(joined == result['joined_frames'], 'join summary mismatch')
    for channel, allowed in [('online', {'rgb.front', 'state'}), ('training_evaluation', {'gt.front'})]:
        rows = read_lines(folder/channel/'records.jsonl')
        check(all(p['stream'] in allowed for p in rows), 'GT/online routing violation')
        check(len(rows) == sum(p['stream'] in allowed for p in packets), 'channel loss')
    check(result['callback_quiet'] and not any(result['listeners_after_stop'].values()), 'listener cleanup')
    check(not result['remaining_owned_ids'] and all(result['destroy_results'].values()), 'actor cleanup')
    check(max(result['queue_high_water'].values(), default=0) <= 64, 'unbounded queue')
    check(classes and len(classes) > 1, 'empty/uniform GT')
    return {'status': 'PASS', 'collection_frames': len(frames), 'joined_frames': joined,
            'missing_by_window': windows, 'semantic_class_ids': sorted(classes),
            'packet_count': len(packets), 'queue_high_water': result['queue_high_water']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('attempt', type=Path)
    args = parser.parse_args()
    summary = json.loads((args.attempt/'summary.json').read_text())
    check(summary['status'] == 'PASS', 'runtime attempt failed/incomplete')
    check(summary['settings_before'] == summary['settings_after'], 'settings changed')
    check(not summary['remaining_vehicles'] and not summary['remaining_sensors'], 'final actors remain')
    output = {'status': 'PASS', 'scope': 'independent raw trace/packet recomputation', 'cases': {}}
    for case in summary['cases']:
        output['cases'][case['case']] = analyze(args.attempt/case['case'])
    (args.attempt/'offline-verification.json').write_text(json.dumps(output, indent=2)+'\n')
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()

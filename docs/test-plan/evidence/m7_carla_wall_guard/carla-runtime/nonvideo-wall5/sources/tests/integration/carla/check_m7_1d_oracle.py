#!/usr/bin/env python3
"""Mutate temporary copies of recorded evidence to check oracle rejection."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile

spec = importlib.util.spec_from_file_location('oracle', Path(__file__).with_name('analyze_m7_1d.py'))
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


def run(attempt):
    results = []
    for mutation in ('source_restamp', 'world_delta', 'main_state_loss', 'main_camera_phase', 'online_GT'):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)/'nominal'
            shutil.copytree(attempt/'nominal', folder)
            path = folder/('ticks.jsonl' if mutation == 'world_delta' else 'packets.jsonl')
            data = oracle.rows(path)
            if mutation == 'source_restamp':
                data[0]['source_time_ns'] += 1
            elif mutation == 'world_delta':
                data[150]['delta_s'] = .05
            elif mutation == 'main_state_loss':
                states = [p for p in data if p['stream'] == 'state']
                data.remove(states[150])
            elif mutation == 'main_camera_phase':
                cameras = [p for p in data if p['stream'] == 'rgb.front']
                p = cameras[40]
                p['frame'] += 1
                p['sequence'] = p['frame']
                t = next(t for t in oracle.rows(folder/'ticks.jsonl') if t['frame'] == p['frame'])
                p['timestamp_seconds'], p['source_time_ns'] = t['sim_s'], round(t['sim_s']*1e9)
            else:
                path = folder/'online/records.jsonl'
                data = oracle.rows(path) + [next(p for p in data if p['stream'] == 'gt.front')]
            path.write_text(''.join(json.dumps(p)+'\n' for p in data))
            try:
                oracle.analyze_case(folder, 800, False)
            except ValueError as exc:
                results.append({'mutation': mutation, 'rejected': True, 'reason': str(exc)})
            else:
                raise AssertionError(f'oracle accepted {mutation}')
    return {'status': 'PASS', 'scope': 'offline mutated copies only', 'tests': results}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('attempt', type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.attempt), indent=2))

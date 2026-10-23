#!/usr/bin/env python3
"""Offline corrupted-copy checks for the M7-1f raw-trace oracle."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('oracle', Path(__file__).with_name('analyze_m7_1f.py'))
    oracle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(oracle)
    original = [json.loads(line) for line in (args.folder/'capture/frames.jsonl').read_text().splitlines()]
    changes = {
        'restamped_clock': lambda r: r[160]['native'].__setitem__('now_ns', r[160]['begin_ns']),
        'missing_role': lambda r: r[160]['native'].__setitem__('service_mask', 127),
        'credit_without_all_release': lambda r: r[160]['native'].__setitem__('release_mask', 127),
        'stale_actual_source': lambda r: r[160]['native'].__setitem__('actual_sources_ns', [r[160]['native']['now_ns']-31_000_000]*3),
        'skipped_tick': lambda r: r[160].__setitem__('tick_frame', r[160]['tick_frame']+1),
        'expired_credit': lambda r: r[160]['native'].__setitem__('lease_expiry_ns', r[160]['native']['now_ns']),
    }
    result = []
    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp)
        (folder/'capture').mkdir()
        for path in ('process.json', 'capture/summary.json'):
            (folder/path).write_bytes((args.folder/path).read_bytes())
        for name, change in changes.items():
            rows = copy.deepcopy(original)
            change(rows)
            (folder/'capture/frames.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            try:
                oracle.analyze(folder)
            except ValueError as error:
                result.append({'mutation': name, 'rejected': True, 'reason': str(error)})
            else:
                raise AssertionError('oracle accepted '+name)
    print(json.dumps({'status': 'PASS', 'scope': 'offline corrupted copies', 'cases': result}, indent=2))


if __name__ == '__main__':
    main()

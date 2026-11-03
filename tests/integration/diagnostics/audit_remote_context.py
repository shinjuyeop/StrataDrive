#!/usr/bin/env python3
"""Independent canonical journal audit of the remote context component export."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
import zlib

from audit_control_diagnostics import event, journal, require


def audit(root):
    raw = {name: (root / f'{name}-event.bin').read_bytes() for name in ('global', 'front', 'rear')}
    context = event(raw['global'])
    require(context['kind'] == 6 and context['_id'][:2] == (10, 20) and
            context['_profile'] == 1 and context['received_roles'] == 255, 'global origin/mask')
    require(context['_enable']['domain'] == 2 and context['_enable']['instance'] == 99 and
            context['_enable']['trusted'], 'global clock')
    ids = {context['_id']}
    for name, stream, producer, component in [('front', 101, 30, 7), ('rear', 102, 31, 8)]:
        source, replica = root / name, root / f'{name}-replica'
        for directory in (source, replica):
            manifest = (directory / 'manifest').read_bytes()
            require(int.from_bytes(manifest[8:16], 'little') == stream, 'stream binding')
            entries = journal(directory, lambda payload: payload)
            require(entries == [raw['global'], raw[name]], 'original context/fault bytes or order')
        for filename in ('manifest', 'commit', 'journal'):
            require((source / filename).read_bytes() == (replica / filename).read_bytes(), 'replica divergence')
        fault = event(raw[name])
        require(fault['kind'] == 1 and fault['code'] == 0x2101 and fault['component'] == component and
                fault['_id'][:2] == (10, producer) and fault['epoch'] == context['epoch'] and
                fault['_enable'] == context['_enable'], 'local identity/context')
        require(fault['detected_ns'] >= context['_enable']['ns'], 'original detection')
        ids.add(fault['_id'])
    require(len(ids) == 3, 'merged identity denominator')
    return dict(pass_=True, streams=2, entries_per_stream=2, unique_events=3, faults=2)


def mutations(root):
    def flip(path):
        data = bytearray(path.read_bytes()); data[-1] ^= 1; path.write_bytes(data)

    def stream(path):
        data = bytearray(path.read_bytes()); data[8] ^= 1
        data[-4:] = zlib.crc32(data[:-4]).to_bytes(4, 'little'); path.write_bytes(data)

    cases = [('global-event.bin', flip), ('front-event.bin', flip),
             ('rear-replica/journal', flip), ('rear-replica/manifest', stream)]
    for filename, mutate in cases:
        with tempfile.TemporaryDirectory(prefix='stratadrive-context-audit-') as tmp:
            candidate = Path(tmp) / 'case'; shutil.copytree(root, candidate); mutate(candidate / filename)
            try:
                audit(candidate)
            except ValueError:
                continue
            raise ValueError(f'mutation accepted: {filename}')
    return len(cases)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path); parser.add_argument('--mutations', action='store_true')
    args = parser.parse_args(); result = audit(args.directory)
    if args.mutations:
        result['mutations_rejected'] = mutations(args.directory)
    print(json.dumps(result, sort_keys=True))

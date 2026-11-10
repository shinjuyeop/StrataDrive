"""Retain every isolated capture attempt and all consumed RGB, including failures."""
from pathlib import Path
import hashlib
import json
import numpy as np

root = Path(__file__).parent

def read(p):
    return json.loads(p.read_text())

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def write(p, value):
    with p.open('x') as f:
        json.dump(value, f, indent=2)
        f.write('\n')

prior = set(read(Path('profiles/perception-quality-exclusion-v9.json'))['rgb_sha256'])
future = set(prior)
rows = []
for path in sorted(root.glob('*/server.json')):
    server = read(path)
    capture = path.parent / 'dataset/capture.json'
    hashes = []
    if capture.exists():
        for pair in read(capture)['frames']:
            for kind in ('rgb', 'instance'):
                assert sha(capture.parent / pair[kind]['path']) == pair[kind]['sha256']
            bgra = np.frombuffer((capture.parent / pair['rgb']['path']).read_bytes(), np.uint8).reshape(384, 640, 4)
            hashes.append(hashlib.sha256(bgra[:, :, 2::-1].copy().tobytes()).hexdigest())
    future.update(hashes)
    rows.append(dict(run=path.parent.name, status=server['status'], server_exit=server.get('server_exit'),
                     server_sha256=sha(path), frames=len(hashes),
                     capture=str(capture.relative_to(root)) if capture.exists() else None,
                     capture_sha256=sha(capture) if capture.exists() else None, rgb_sha256=hashes))
write(root / 'capture-attempts.json', rows)
write(root / 'future-evaluation-exclusion.json', dict(schema='m10-future-quality-exclusion-v9',
    scope='All previously consumed RGB and every V9 preparation/evaluation attempt including failures; never reuse as fresh holdout',
    rgb_sha256=sorted(future)))
write(root / 'inventory-summary.json', dict(prior_rgb=len(prior), future_rgb=len(future),
    raw_pairs=sum(r['frames'] for r in rows), attempts=len(rows)))
print(read(root / 'inventory-summary.json'))

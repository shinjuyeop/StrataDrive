"""Retain a checked review subset; full run/raw archives remain local."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

p = argparse.ArgumentParser()
p.add_argument('--run', type=Path, required=True)
p.add_argument('--bundle', type=Path, required=True)
a = p.parse_args()
manifest = json.loads((a.bundle/'run-manifest.json').read_text())
fault = json.loads((a.bundle/'fault-analysis.json').read_text())['first_protection_wall_ns']
excluded = {'capture/events.json', 'capture/paired/source.json', 'capture/perception.json',
            'capture/sensors.json', 'capture/trace.jsonl.gz'}
names = [name for name in manifest['members'] if name not in excluded and
         (Path(name).suffix in ('.json', '.csv', '.jsonl', '.log', '.stderr') or name == 'host-profile.jsonl.gz')]
def digest(data):
    return dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
selected = []
with gzip.open(a.run/'capture/trace.jsonl.gz', 'rb') as stream:
    for line in stream:
        row = json.loads(line)
        end = int(row['receipt']['physics_acquisition_end_ns'])
        if end > fault+250_000_000:
            break
        if end >= fault-250_000_000:
            selected.append(line)
window = gzip.compress(b''.join(selected), compresslevel=6, mtime=0)
derived_name = 'derived/first-fault-trace.jsonl.gz'
review = dict(schema='m10-retained-review-v1',
    scope='Selected original metadata and a first-fault trace window; not full replay or raw backup',
    original_archive=manifest['archive'], original_archive_sha256=manifest['sha256'],
    original_members={name: manifest['members'][name] for name in names},
    derived={derived_name: dict(**digest(window), original='capture/trace.jsonl.gz',
        original_identity=manifest['members']['capture/trace.jsonl.gz'],
        selection='original acquisition end within +/-250ms of first native protection',
        first_protection_wall_ns=fault, rows=len(selected))})
target = a.bundle/'retained-metadata.tar.gz'
assert not target.exists(), 'immutable review subset'
def add_bytes(tar, name, data):
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = 0o644
    tar.addfile(info, io.BytesIO(data))
with tarfile.open(target, 'w:gz') as tar:
    for name in names:
        data = (a.run/name).read_bytes()
        assert digest(data) == manifest['members'][name]
        add_bytes(tar, name, data)
    add_bytes(tar, derived_name, window)
    add_bytes(tar, 'MANIFEST.json', (json.dumps(review, indent=2)+'\n').encode())
with tarfile.open(target, 'r:gz') as tar:
    expected = dict(review['original_members'], **{derived_name: digest(window)})
    assert set(tar.getnames()) == set(expected)|{'MANIFEST.json'}
    for name, identity in expected.items():
        assert digest(tar.extractfile(name).read()) == identity
result = dict(status='PASS', archive=target.name, **digest(target.read_bytes()),
              original_members=len(names), derived_fault_rows=len(selected), full_run_preserved_locally=True)
(a.bundle/'retained-metadata.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result))

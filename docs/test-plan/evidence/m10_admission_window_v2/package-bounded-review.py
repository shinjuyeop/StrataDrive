"""Derive a smaller review subset without modifying any original evidence."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile

p = argparse.ArgumentParser()
p.add_argument('--bundle', type=Path, required=True)
a = p.parse_args()
read = lambda name: json.loads((a.bundle/name).read_text())
def identity(data):
    return dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())

original = read('retained-metadata.json')
source = a.bundle/original['archive']
assert identity(source.read_bytes()) == {k: original[k] for k in ('bytes', 'sha256')}
path = read('path-analysis.json')
anchors = {int(path['anchor_ns'])}
if (a.bundle/'first-fault-analysis.json').exists():
    fault = read('first-fault-analysis.json')
    anchors.add(int(fault['original_first_fault']['observed_ns']))
    for pause in fault.get('periodic_pauses', [])+fault.get('other_large_outside_pauses', []):
        anchors.update((int(pause['begin']['wall_ns']), int(pause['end']['wall_ns'])))
if (a.bundle/'native-gap-analysis.json').exists():
    for row in read('native-gap-analysis.json')['missing']:
        anchors.add(int(row['release_ns']))
windows = [(v-250_000_000, v+250_000_000) for v in sorted(anchors)]
columns = {'capture/native-wall.csv': 'release_ns', 'capture/native-monitor.csv': 'release_ns',
           'capture/native-state-path.csv': 'wake_ns', 'capture/native.csv': 'now'}
omitted = {'capture/ingress.json', 'capture/paired/renderer/result.json',
           'capture/native-perception.jsonl'}
target = a.bundle/'bounded-review.tar.gz'
assert not target.exists(), 'immutable derived review subset'
members = {}; derived = {}; excluded = {}; payload = {}
with tarfile.open(source, 'r:gz') as tar:
    prior = json.load(tar.extractfile('MANIFEST.json'))
    for item in tar.getmembers():
        name = item.name
        if name == 'MANIFEST.json':
            continue
        data = tar.extractfile(item).read()
        expected = prior['original_members'].get(name, prior['derived'].get(name))
        assert identity(data) == {k: expected[k] for k in ('bytes', 'sha256')}
        if name in omitted:
            excluded[name] = identity(data)
        elif name in columns:
            lines = data.splitlines(keepends=True)
            index = lines[0].decode().strip().split(',').index(columns[name])
            selected = [line for line in lines[1:] if any(
                low <= int(line.split(b',')[index]) <= high for low, high in windows)]
            output = 'derived/windows-'+Path(name).name
            payload[output] = lines[0]+b''.join(selected)
            derived[output] = dict(**identity(payload[output]), original=name,
                original_identity=identity(data), selection_column=columns[name],
                windows_ns=windows, rows=len(selected),
                selection='Original header and complete byte-unchanged lines, inclusive timestamp windows')
        else:
            payload[name] = data
            if name in prior['original_members']:
                members[name] = identity(data)
            else:
                derived[name] = prior['derived'][name]
review = dict(schema='m10-bounded-review-v1',
    scope='Partial review only; full original run and larger metadata subset remain local, not a replay backup',
    original_archive=prior['original_archive'], original_archive_sha256=prior['original_archive_sha256'],
    parent_review=original, original_members=members, derived=derived,
    omitted_large_original_members=excluded)
payload['MANIFEST.json'] = (json.dumps(review, indent=2)+'\n').encode()
with tarfile.open(target, 'w:gz') as tar:
    for name, data in payload.items():
        info = tarfile.TarInfo(name); info.size = len(data); info.mode = 0o644
        tar.addfile(info, io.BytesIO(data))
with tarfile.open(target, 'r:gz') as tar:
    assert set(tar.getnames()) == set(payload)
    for name, data in payload.items():
        assert tar.extractfile(name).read() == data
result = dict(status='PASS_PARTIAL_REVIEW_ONLY', archive=target.name,
    **identity(target.read_bytes()), parent_review=original,
    original_members=len(members), derived_members=len(derived), full_run_preserved_locally=True)
(a.bundle/'bounded-review.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result))

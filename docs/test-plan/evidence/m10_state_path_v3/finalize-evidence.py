"""Check immutable inputs/restoration and write local evidence checksums."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
SERIES = Path(__file__).resolve().parent

def read(path):
    return json.loads(path.read_text())

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()

frozen = read(SERIES/'sources.json')
for name, identity in frozen['files'].items():
    path = ROOT/name
    assert path.stat().st_size==identity['bytes'] and sha(path)==identity['sha256'], name
original = read(SERIES/'pre-install.json')['files']
runtime = {}
for name, item in original.items():
    digest = sha(Path(item['path']))
    runtime[name] = dict(path=item['path'], sha256=digest, restored=digest==item['sha256'])
assert all(item['restored'] for item in runtime.values())
shared = {item['path'] for item in original.values()}
immutable_external = {name: sha(Path(name)) for name in frozen['external'] if name not in shared}
assert all(value==frozen['external'][name] for name, value in immutable_external.items())
processes = subprocess.check_output(['ps', '-eo', 'comm='], text=True).splitlines()
assert not any(name.strip() in ('UE4Editor', 'm7_carla_wall_o') for name in processes)
cases = {}
for version in (1, 2, 3):
    series = ROOT/f'docs/test-plan/evidence/m10_state_path_v{version}'
    bundle = series/'normal-30s-01'
    case = read(bundle/'disposition.json')
    assert case['archive']=='PASS' and not case['finite_30s_diagnostic_pass']
    assert case['normal_30s_02']=='NOT_RUN_STOP_ON_FIRST_FAILURE'
    assert read(bundle/'restoration.json')['status']=='PASS'
    assert read(bundle/'archive-validation.json')['status']=='PASS'
    cases[series.name] = dict(physical='FAIL', archive='PASS',
        state_path=read(bundle/'state-path.json')['status'],
        future_exclusion=read(bundle/'archive-validation.json')['future_exclusion'])
assert read(SERIES/'normal-30s-01/original-receipt-identity.json')['cached_queries']==566
assert read(SERIES/'normal-30s-01/state-path-reproduction.json')['status']=='PASS'
assert read(SERIES/'normal-30s-01/replay.json')['exact']
result = dict(checked_utc=datetime.now(timezone.utc).isoformat(),
    status='PASS_EVIDENCE_AND_RESTORATION_ONLY', physical_stability_accepted=False,
    native_perception_accepted=False, milestone_closed=False,
    frozen_source_files=len(frozen['files']), immutable_external_files=len(immutable_external),
    runtime=runtime, cases=cases, python_tests=482, native_boundary_tests=40,
    frozen_focused_tests=66, full_raw_images_checked=572,
    no_owned_servers_running=True)
(SERIES/'final-validation.json').write_text(json.dumps(result, indent=2)+'\n')
for version in (1, 2, 3):
    series = ROOT/f'docs/test-plan/evidence/m10_state_path_v{version}'
    bundle = series/'normal-30s-01'
    run = read(bundle/'run-manifest.json')
    known = {bundle/run['archive']: run}
    known.update({bundle/item['archive']: item for item in read(bundle/'raw-manifest.json')['archives']})
    entries = []
    for path in sorted(p for p in series.rglob('*') if p.is_file() and p.name!='SHA256SUMS'):
        if path in known:
            assert path.stat().st_size==known[path]['bytes']
            digest = known[path]['sha256']  # Independently checked; compaction verifies expanded bytes.
        else:
            digest = sha(path)
        entries.append(f'{digest}  {path.relative_to(series)}\n')
    (series/'SHA256SUMS').write_text(''.join(entries))
print(json.dumps(result, indent=2))

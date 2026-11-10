from pathlib import Path
import sys, json, hashlib, tempfile
from datetime import datetime

sys.path[:0] = ['.', 'tests/integration/perception']
from prepare_road_v8 import prepare
root = Path(__file__).parent
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
frozen = read(root / 'initial-preparation-freeze.json')
for name, digest in frozen['sources'].items():
    assert sha(name) == sha(root / 'initial-preparation-source' / name) == digest
results = {}
for part in ('development', 'holdout'):
    original = root / f'initial-preparation-{part}-data'
    saved = read(original / 'acceptance.json')
    with tempfile.TemporaryDirectory() as temporary:
        output = Path(temporary) / 'data'
        rebuilt = prepare(root / f'preparation-{part}-01/dataset/capture.json',
                          Path('profiles/perception-road-preparation-v8.json'),
                          Path('profiles/perception-quality-exclusion-v8.json'), output)
        assert all(rebuilt[k] == saved[k] for k in saved if k != 'completed_utc')
        for name in ('rgb.json', 'evaluation-only-gt.json', 'preparation-data.json'):
            assert sha(output / name) == sha(original / name)
    results[part] = dict(status=saved['status'], gates=saved['gates'],
                         capture_sha256=sha(root / f'preparation-{part}-01/dataset/capture.json'),
                         rgb_manifest_sha256=sha(original / 'rgb.json'),
                         acceptance_sha256=sha(original / 'acceptance.json'),
                         occlusion_checks=saved['occlusion_checks'])
assert results['development']['status'] == 'PASS'
assert results['holdout']['status'] == 'FAIL'
bad = [r for r in results['holdout']['occlusion_checks'] if not r['passed']]
assert len(bad) == 3 and all(r['visible_ratio'] == 1 for r in bad)
revision = read(root / 'preparation-revision-before-recapture.json')
assert revision['original_freeze_sha256'] == sha(root / 'initial-preparation-freeze.json')
assert revision['annex_sha256'] == sha('docs/test-plan/perception-quality-v8-preparation-revision.md')
for part in ('development', 'holdout'):
    before = datetime.fromisoformat(read(root / f'preparation-{part}-01/server.json')['started_utc'])
    after = datetime.fromisoformat(read(root / f'preparation-{part}-02/server.json')['started_utc'])
    assert before < datetime.fromisoformat(revision['created_utc']) < after
report = dict(status='PASS', scope='Initial preparation PASS/FAIL retained; model-free revision before quality inference',
              helper_sha256=sha(__file__),
              frozen_sources=len(frozen['sources']), initial_raw_pairs=198, initial=results,
              original_freeze_sha256=sha(root / 'initial-preparation-freeze.json'),
              revision_record_sha256=sha(root / 'preparation-revision-before-recapture.json'))
with (root / 'initial-preparation-audit.json').open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print('PASS: initial198 raw pairs and original held occlusion FAIL replayed')

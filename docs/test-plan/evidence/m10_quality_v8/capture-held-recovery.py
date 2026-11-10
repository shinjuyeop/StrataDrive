from pathlib import Path
from datetime import datetime, timezone
import json, hashlib, subprocess, sys

sys.path[:0] = ['.', 'tests/integration/perception']
from prepare_road_v8 import prepare
from review_quality_road_v4 import review
root = Path(__file__).parent
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
frozen = read(root / 'preparation-freeze.json')
for name, digest in frozen['sources'].items():
    assert sha(name) == sha(root / 'preparation-source' / name) == digest
old = read(root / 'preparation-holdout-02/server.json')
capture = root / 'preparation-holdout-02/dataset/capture.json'
assert old['status'] == 'FAIL' and old['forced_stop'] and old['server_exit'] == -9
assert read(capture)['status'] == 'PASS' and len(read(capture)['frames']) == 99
record = dict(created_utc=datetime.now(timezone.utc).isoformat(),
              annex_sha256=sha('docs/test-plan/perception-quality-v8-recovery.md'),
              preparation_freeze_sha256=sha(root / 'preparation-freeze.json'),
              plan_sha256=sha('profiles/perception-road-preparation-v8b.json'),
              original_failed_server_sha256=sha(root / 'preparation-holdout-02/server.json'),
              original_capture_sha256=sha(capture), original_failed_raw_pairs=99,
              limits=[180, 900, 30], extra_holdout_preparation_attempts=1,
              original_automatic_retry_rule_applies=False, model_plan_gate_changes=False)
with (root / 'recovery-before-launch.json').open('x') as stream:
    json.dump(record, stream, indent=2)
    stream.write('\n')
run = root / 'preparation-holdout-03'
args = ['python3', 'tests/integration/perception/run_road_server_v8.py',
        '--engine', '/d/shin/stratadrive-tools/UnrealEngine_4.26',
        '--source', '/d/shin/stratadrive-tools/m7-source/carla-0.9.16',
        '--python', '/d/shin/stratadrive-tools/m7-source/m7-nodrive-venv/bin/python',
        '--output', str(run), '--stage', 'preparation', '--plan',
        'profiles/perception-road-preparation-v8b.json', '--partition', 'holdout']
with (root / 'preparation-holdout-03-capture.log').open('x') as log:
    result = subprocess.run(args, stdout=log, stderr=subprocess.STDOUT)
server = read(run / 'server.json')
print(server['status'], server.get('server_exit'), flush=True)
assert result.returncode == 0 and server['status'] == 'PASS', 'separate recovery exhausted; original failure retained'
runs = read(root / 'preparation-runs.json')
runs['holdout'] = run.name
(root / 'preparation-runs.json').write_text(json.dumps(runs, indent=2) + '\n')
result = prepare(run / 'dataset/capture.json', Path('profiles/perception-road-preparation-v8b.json'),
                 Path('profiles/perception-quality-exclusion-v8.json'), root / 'preparation-holdout-data')
print(result['status'], result['gates'], flush=True)
print(review(root / 'preparation-holdout-data', root, 'preparation-holdout'), flush=True)
assert result['status'] == 'PASS'

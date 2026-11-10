from pathlib import Path
from datetime import datetime, timezone
import json, hashlib, shutil, tarfile, subprocess

root = Path(__file__).parent.resolve()
repo = Path.cwd()
out = repo / 'docs/test-plan/evidence/m10_quality_v8'
read = lambda p: json.loads(Path(p).read_text())

def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()

def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')

audit = read(root / 'experiment-audit.json')
summary = read(root / 'summary.json')
frozen = read(root / 'experiment-freeze.json')
assert audit['audit'] == 'PASS' and not audit['eligible_for_runtime_review']
for filename, snapshot in [('experiment-freeze.json', 'frozen-source'),
                           ('preparation-freeze.json', 'preparation-source'),
                           ('initial-preparation-freeze.json', 'initial-preparation-source'),
                           ('survey-freeze.json', 'survey-source')]:
    for name, digest in read(root / filename)['sources'].items():
        assert sha(repo / name) == sha(root / snapshot / name) == digest, name
assert 'Ran 174 tests' in (root / 'python-before-freeze.log').read_text()
for config in ('debug', 'release', 'asan'):
    assert '100% tests passed, 0 tests failed out of 13' in (root / f'ctest-{config}.log').read_text()
assert 'All checks passed!' in (root / 'ruff-final.log').read_text()
assert read(root / 'document-checks.json')['status'] == 'PASS'
for part in ('development', 'holdout'):
    for prefix in ('', 'preparation-'):
        assert read(root / f'{prefix}{part}-visual-review.json')['status'] == 'PASS'

for path in sorted(root.iterdir()):
    if path.is_file() and path.suffix in ('.json', '.log', '.txt', '.png', '.py'):
        shutil.copy2(path, out / path.name)
for part in ('development', 'holdout'):
    shutil.copy2(root / f'{part}-data/visibility.json', out / f'{part}-visibility.json')
    shutil.copy2(root / f'preparation-{part}-data/acceptance.json', out / f'preparation-{part}-acceptance.json')

write(out / 'acceptance.json', dict(
    schema='m10-quality-v8-evidence', recorded_utc=datetime.now(timezone.utc).isoformat(),
    technical_audit='PASS', model_quality='FAIL', eligible_for_runtime_review=False,
    milestone_acceptance='M10 OPEN', default_model='YOLOX-S', runtime_promotion=False,
    official_pretrained_model_sha256='7860ae79de6c89a3c1eb72ae9a2756c0ccfbe04b7791bb5880afabd97855a411',
    final_evaluation_frames=162, accepted_preparation_frames=198,
    total_raw_pairs=summary['new_raw_pairs'], all_preparation_raw_pairs=495,
    raw_gt_reconstruction_pairs=558, failed_shutdown_pairs_rehashed=99,
    prior_rgb=4333, evaluation_excluded=4828, future_rgb=summary['future_rgb'],
    initial_preparation_visibility_failure_retained=True, shutdown_failure_retained=True,
    bounded_separate_recovery=True, setup_failure_before_server_launch_retained=True,
    validation=dict(python=174, ctest={c: 13 for c in ('debug', 'release', 'asan')},
                    numeric_candidate_probes=6, source_freeze_files=237,
                    raw_gt_score_order_replay='PASS', full_core_or_live20hz_rerun=False),
    additional_training=False, board_optimization=False, jetson_execution=False,
    summary=audit,
))

files = {repo / name for name in frozen['sources']}
for file in ('preparation-freeze.json', 'initial-preparation-freeze.json', 'survey-freeze.json'):
    files.update(repo / name for name in read(root / file)['sources'])
for base in ('third_party/opencv-zoo-yolox', 'third_party/megvii-yolox-large'):
    files.update(p for p in (repo / base).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
files.update(repo / name for name in (
    '.gitattributes', 'physical_ai/__init__.py', 'physical_ai/requirements-host.txt',
    'physical_ai/requirements-cuda-host.txt', 'docs/interfaces/perception.md',
    'docs/perception-model-selection.md', 'docs/perception-guide.md', 'docs/project-status.md',
    'docs/roadmap.md', 'docs/test-plan/perception-protocol.md',
    'docs/test-plan/component-traceability.csv', 'profiles/README.md',
    'docs/test-plan/evidence/m10_quality_v7/future-evaluation-exclusion.json',
    'docs/test-plan/evidence/m10_quality_v8/README.md',
    'docs/test-plan/evidence/m10_quality_v8/check-archive.py',
))
files = sorted(files)
write(out / 'sources.json', dict(
    baseline=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    files={str(p.relative_to(repo)): sha(p) for p in files},
    frozen_quality_sources=237, survey_sources=5, initial_preparation_sources=18,
    revised_preparation_sources=20,
    note='Current/frozen code and explicit map/recipe provenance; unchanged historical source paths included; official model bytes excluded',
))
with tarfile.open(out / 'sources.tar.gz', 'w:gz', compresslevel=6) as archive:
    for path in files:
        archive.add(path, arcname=str(path.relative_to(repo)), recursive=False)
with tarfile.open(out / 'experiment.tar.gz', 'w:gz', compresslevel=6) as archive:
    for path in sorted(root.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            assert path.suffix not in ('.onnx', '.pth', '.pt', '.engine')
            archive.add(path, arcname=str(path.relative_to(repo)), recursive=False)
with (out / 'SHA256SUMS').open('x') as stream:
    for path in sorted(out.rglob('*')):
        if path.is_file() and path.name != 'SHA256SUMS':
            stream.write(sha(path) + '  ' + str(path.relative_to(out)) + '\n')
print(json.dumps(dict(source_files=len(files), experiment_bytes=(out / 'experiment.tar.gz').stat().st_size)), flush=True)

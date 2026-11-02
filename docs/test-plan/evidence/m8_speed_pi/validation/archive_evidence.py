import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

root = Path.cwd()
work = root / 'build/m8-speed-pi'
archive = root / 'docs/test-plan/evidence/m8_speed_pi'
archive_map = []
def sha(data):
    return hashlib.sha256(data).hexdigest()
def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')
def copy(source, destination, compress=False):
    data = source.read_bytes()
    target = archive / destination
    if compress:
        target = target.with_name(target.name + '.gz')
    if target.exists():
        raise RuntimeError(f'Refusing to overwrite {target}')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(gzip.compress(data, mtime=0) if compress else data)
    archive_map.append(dict(source=str(source.relative_to(root)), archive=str(target.relative_to(archive)),
                            gzip=compress, original_size=len(data), original_sha256=sha(data)))

runs = {}
initial_hash = '2acb17d8572fc90f1e9b50a0bc3d8f1a1f83af3b9ecfc90a249e996337e04a8f'
for config in ('normal','release','sanitized'):
    for folder in sorted((work/config/'longitudinal-equivalence').iterdir()):
        plan = json.loads((folder/'plan.json').read_text())
        label = 'normal-initial' if plan['input_sha256'] == initial_hash else config
        if label in runs:
            raise RuntimeError('Duplicate run label')
        result = json.loads((folder/'result.json').read_text())
        runs[label] = dict(folder=folder, plan=plan, result=result)
        for source in sorted(folder.iterdir()):
            copy(source, Path(label)/source.name, source.name in ('inputs.txt','python.jsonl','cpp.jsonl'))

source_hashes = runs['normal']['plan']['sources']
for name, expected in source_hashes.items():
    source = root/name
    if sha(source.read_bytes()) != expected:
        raise RuntimeError(f'Source changed after final replay: {name}')
    copy(source, Path('sources')/name)

# Recover only the initial generator bytes whose hash was recorded before replay.
name = 'tests/integration/longitudinal/speed_pi_vectors.py'
initial_generator = (root/name).read_text().replace(
    'v.step(tick * PERIOD, error, 0., sequence=tick)',
    'v.step(tick * PERIOD, 6., 6. - error, sequence=tick)').replace(
    'v.step(tick * PERIOD, 0., error, sequence=tick)',
    'v.step(tick * PERIOD, 1., 1. + error, sequence=tick)')
if sha(initial_generator.encode()) != runs['normal-initial']['plan']['sources'][name]:
    raise RuntimeError('Initial generator reconstruction hash mismatch')
p = archive/'sources-initial'/name
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(initial_generator)

for source in sorted((work/'validation').iterdir()):
    copy(source, Path('validation')/source.name, source.stat().st_size > 65536)
copy(work/'run_validation.py', Path('validation/run_validation.py'))
copy(Path(__file__).resolve(), Path('validation/archive_evidence.py'))

builds = {}
for config in ('normal','release','sanitized','production'):
    folder = work/config
    options = [line for line in (folder/'CMakeCache.txt').read_text().splitlines()
               if re.match(r'(CMAKE_(BUILD_TYPE|CXX_COMPILER|CXX_FLAGS[^:]*|GENERATOR)|BUILD_TESTING|STRATADRIVE_[^:]+):',line)]
    names = ['libspeed_pi.a'] if config == 'production' else ['speed_pi_test','speed_pi_replay','libspeed_pi.a']
    builds[config] = dict(options=options, binaries={name:dict(sha256=sha((folder/name).read_bytes()),
        size=(folder/name).stat().st_size) for name in names})
    copy(folder/'CMakeCache.txt', Path('builds')/config/'CMakeCache.txt')
    entries = [entry for entry in json.loads((folder/'compile_commands.json').read_text())
               if Path(entry['file']).name in ('speed_pi.cpp','speed_pi_test.cpp','speed_pi_replay.cpp')]
    save(archive/'builds'/config/'compile_commands.json', entries)

results = {}
for label, run in runs.items():
    r = run['result']
    results[label] = dict(passed=r['pass'], cases=len(r['cases']), events=r['events'],
        steps=sum(case['steps'] for case in r['cases'].values()),
        max_absolute_error=max(r['max_absolute_errors'].values()), input_sha256=run['plan']['input_sha256'],
        reasons=r['reasons'], malformed_rejected=r['malformed_rejected'], malformed_total=r['malformed_total'])
checks = {}
for source in sorted((work/'validation').glob('*.json')):
    meta = json.loads(source.read_text())
    text = source.with_suffix('.txt').read_text()
    count = re.search(r'0 tests failed out of (\d+)',text)
    python_count = re.search(r'Ran (\d+) tests',text)
    checks[source.stem] = dict(returncode=meta['returncode'])
    if count: checks[source.stem]['ctest_passed'] = int(count[1])
    if python_count: checks[source.stem]['python_tests'] = int(python_count[1])
save(archive/'results-summary.json', dict(scope='M8 SpeedPI component equivalence only',
    vehicle_closed_loop='NOT RUN', carla='NOT RUN', tsan='not applicable: single-owner pure component',
    final_runs=['normal','release','sanitized'], equivalence=results, validation=checks))
commands = {'compiler':['c++','--version'], 'cmake':['cmake','--version'],
            'clang_tidy':['clang-tidy','--version'], 'cppcheck':['cppcheck','--version']}
versions = {name:subprocess.check_output(command,text=True).strip() for name,command in commands.items()}
save(archive/'build-manifest.json', dict(baseline_commit='f9cef7d98ef733de9f09da437c6b9c290572c4da',
    source_state='uncommitted working tree; exact tested sources preserved in sources/',
    sources=source_hashes, builds=builds, tools=versions, archive_python=sys.version,
    replay_python=runs['normal']['plan']['python'],
    note='Initial generator recovered by the documented two-line reversal and verified against its pre-run SHA256.'))
save(archive/'archive-map.json', archive_map)
print(json.dumps(dict(archive=str(archive),files=len(list(archive.rglob('*'))),
                     final={key:results[key] for key in ('normal','release','sanitized')}),indent=2))

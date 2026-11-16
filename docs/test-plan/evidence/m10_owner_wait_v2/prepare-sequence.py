"""Freeze and verify the declared owner-wait diagnostic before any privileged host action."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from runtime_restore import restore

ROOT = Path(__file__).resolve().parents[4]
SERIES = Path(__file__).resolve().parent
WORK = ROOT/'build/m10-owner-wait-v2'
PRIOR = SERIES.with_name('m10_owner_wait_v1')
PYTHON = ROOT/'build/m10-perception/cuda-venv/bin/python'
def read(path): return json.loads(path.read_text())
def write(path, value): path.write_text(json.dumps(value, indent=2)+'\n')
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def call(argv, log):
    with log.open('w') as stream:
        subprocess.run(list(map(str, argv)), stdout=stream, stderr=subprocess.STDOUT, check=True)

assert not (SERIES/'sources.json').exists()
assert (ROOT/'build/m10-owner-wait-v1/server-build-01/manifest.json').exists()
assert 'Ran 505 tests' in (SERIES/'python-tests.txt').read_text()
assert (SERIES/'python-tests.txt').read_text().rstrip().endswith('OK')
assert read(SERIES/'stamp-cost.json')['p95_ns']<5000
assert read(SERIES/'stamp-cost.json')['owner_path_bytes']*60000<=128*1024**2
assert read(PRIOR/'restoration-confirmation.json')['status'] == 'PASS'
prior = read(PRIOR/'sources.json')
for path in [*SERIES.glob('*.py'),*SERIES.glob('*.cpp')]:
    prior['files'][str(path.relative_to(ROOT))] = dict(bytes=path.stat().st_size, sha256=sha(path))
prior['files']['docs/test-plan/perception-owner-wait-v2-protocol.md'] = {}
write(WORK/'freeze-prior.json', prior)
restore(ROOT, SERIES, WORK, SERIES/'pre-freeze-restoration.json')
engine='/d/shin/stratadrive-tools/UnrealEngine_4.26'
carla='/d/shin/stratadrive-tools/m7-source/carla-0.9.16'
try:
    call(['python3', ROOT/'tools/carla/m7_nodrive/build_endurance.py', '--engine', engine,
        '--source', carla, '--output', ROOT/'build/m10-owner-wait-v1/server-build-01', '--install'], WORK/'install-module.log')
    call(['python3', ROOT/'tools/carla/m7_nodrive/build_dxc_lifetime.py', '--engine', engine,
        '--output', ROOT/'build/m10-dxc-lifetime-v1', '--install'], WORK/'install-dxc.log')
    call([PYTHON, ROOT/'tests/integration/perception/freeze_owner_split_v1.py', '--output', SERIES,
        '--prior', WORK/'freeze-prior.json', '--protocol', 'docs/test-plan/perception-owner-wait-v2-protocol.md', '--external', ROOT/'build/m10-owner-wait-v1/server-build-01/manifest.json', '--external', ROOT/'build/m10-owner-wait-v1/server-build-01/libUE4Editor-Carla.so'], WORK/'freeze.log')
finally:
    restore(ROOT, SERIES, WORK, SERIES/'post-freeze-restoration.json')
call([PYTHON, SERIES/'check-evidence.py', '--work', WORK/'frozen-tests'], WORK/'frozen-tests.log')
shutil.copy2(WORK/'frozen-tests/validation.json', SERIES/'frozen-tests.json')
assert read(SERIES/'frozen-tests.json')['focused_tests'] == 93
frozen = read(SERIES/'sources.json')
write(SERIES/'prepared.json', dict(status='READY_FOR_EXPLICIT_HOST_LEASE', source_files=len(frozen['files']),
    source_archive_sha256=frozen['archive_sha256'], helper_sha256=sha(ROOT/'tools/m10_boost_lease.py'),
    python_tests=505, frozen_tests=93, unchanged_native_cpp_tests=207,
    native_preflight='REUSED_IDENTICAL_BINARY_30_AND300_ALLOCATION_ONLY',
    model_preparation='WORKSPACE_OPT_IN; QUIET40_PASS; LIVE_TAIL_NOT_YET_VALIDATED',
    owner_stamp_cost=read(SERIES/'stamp-cost.json'), candidate_module_sha256=read(ROOT/'build/m10-owner-wait-v1/server-build-01/manifest.json')['module_sha256'],
    runtime_restored=True, host_max_perf_pct=int(Path('/sys/devices/system/cpu/intel_pstate/max_perf_pct').read_text()),
    live_status='NOT_STARTED', privileged_step='operator invocation with fresh owner PID; no stored credentials'))
print(json.dumps(read(SERIES/'prepared.json')))

"""Seal the explicit native service candidate before its first execution."""
import hashlib,json,re,shutil,subprocess,sys
from pathlib import Path
from runtime_restore import restore
ROOT=Path(__file__).resolve().parents[4];SERIES=Path(__file__).resolve().parent
WORK=ROOT/'build/m10-cuda-resize-v1';PRIOR=SERIES.with_name('m10_service_half_v1')
PYTHON=ROOT/'build/m10-perception/cuda-venv/bin/python'
BUILD=ROOT/'build/m10-gc-feedback-v1/visual-tags-build-01'
read=lambda p:json.loads(p.read_text())
write=lambda p,v:p.write_text(json.dumps(v,indent=2)+'\n')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def call(argv,log):
    with log.open('w') as stream:subprocess.run(list(map(str,argv)),stdout=stream,stderr=subprocess.STDOUT,check=True)
assert not (SERIES/'sources.json').exists()
assert read(PRIOR/'cache-execution.json')['restoration']['status']=='PASS_ORIGINALS_RESTORED'
assert read(PRIOR/'sequence-restoration.json')['status']=='PASS'
text=(WORK/'python-tests.log').read_text();assert 'Ran 607 tests' in text and '\nOK\n' in text
assert read(PRIOR/'prepared.json')['native_tests']==42
assert read(SERIES/'component/model-paths-03.json')['status']=='PASS_ACTUAL_MODEL_SETUP_ONLY'
assert read(PRIOR/'normal-300s-01/disposition.json')['finite_diagnostic_pass']
shutil.copy2(PRIOR/'normal-300s-01/future-exclusion.json',SERIES/'preparation-future-exclusion.json')
assert read(PRIOR/'default30-replay.json')['status']=='PASS_EXACT_DEFAULT30_REPLAY'
call([PYTHON,SERIES/'check-runner-wiring.py'],WORK/'runner-wiring.log')
prior=read(PRIOR/'sources.json')
for p in SERIES.iterdir():
    if p.is_file() and '.tar' not in p.name:prior['files'][str(p.relative_to(ROOT))]={}
write(WORK/'freeze-prior.json',prior)
restore(ROOT,SERIES,WORK,SERIES/'pre-freeze-restoration.json')
engine='/d/shin/stratadrive-tools/UnrealEngine_4.26';carla='/d/shin/stratadrive-tools/m7-source/carla-0.9.16'
try:
    call(['python3',ROOT/'tools/carla/m7_nodrive/build_endurance.py','--engine',engine,'--source',carla,'--output',BUILD,'--install'],WORK/'install-module.log')
    call(['python3',ROOT/'tools/carla/m7_nodrive/build_dxc_lifetime.py','--engine',engine,'--output',ROOT/'build/m10-dxc-lifetime-v1','--install'],WORK/'install-dxc.log')
    argv=[PYTHON,ROOT/'tests/integration/perception/freeze_owner_split_v1.py','--output',SERIES,'--prior',WORK/'freeze-prior.json','--protocol','docs/test-plan/perception-cuda-resize-v1-protocol.md']
    for name in ('m7_carla_wall_owner','m7_wall_startup_replay'):argv+=['--external',ROOT/'build/m10-service-half-v1/native/tests/integration/carla/m7_1g'/name]
    argv+=['--external',WORK/'release/libresize-cuda.so']
    call(argv,WORK/'freeze.log')
finally:restore(ROOT,SERIES,WORK,SERIES/'post-freeze-restoration.json')
call([PYTHON,SERIES/'check-evidence.py','--work',WORK/'frozen-tests'],WORK/'frozen-tests.log')
shutil.copy2(WORK/'frozen-tests/validation.json',SERIES/'frozen-tests.json')
assert read(SERIES/'frozen-tests.json')['focused_tests']==190
write(SERIES/'prepared.json',dict(status='READY_FOR_EXPLICIT_HOST_LEASE',python_tests=607,archive_compatibility_tests=20,frozen_tests=190,native_tests=42,standalone_auditors=8,physical_started=False,storage_wrapper='tools/m10_with_asset_cache.py',policy='wall5-hv50-v1',native_service_us=500,renderer='source-editor',sequence=['normal-30s-01','normal-300s-01']))
print(json.dumps(read(SERIES/'prepared.json')))

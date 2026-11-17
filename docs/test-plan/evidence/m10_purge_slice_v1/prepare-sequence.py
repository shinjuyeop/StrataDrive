"""Freeze the prepared incremental-purge candidate before its host lease."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
from runtime_restore import restore
ROOT=Path(__file__).resolve().parents[4];SERIES=Path(__file__).resolve().parent
WORK=ROOT/'build/m10-purge-slice-v1';PRIOR=SERIES.with_name('m10_parallel_gc_v1')
PYTHON=ROOT/'build/m10-perception/cuda-venv/bin/python'
read=lambda p:json.loads(p.read_text())
write=lambda p,v:p.write_text(json.dumps(v,indent=2)+'\n')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def call(argv,log):
 with log.open('w') as stream:subprocess.run(list(map(str,argv)),stdout=stream,stderr=subprocess.STDOUT,check=True)
assert not (SERIES/'sources.json').exists()
assert not Path('/proc/3072242').exists()
assert read(PRIOR/'restoration-confirmation.json')['status']=='PASS'
assert 'Ran 522 tests' in (SERIES/'python-tests.txt').read_text() and (SERIES/'python-tests.txt').read_text().rstrip().endswith('OK')
assert '[  PASSED  ] 28 tests.' in (SERIES/'native-admission-tests.txt').read_text()
validations=[read(p) for p in (SERIES/'preparations').glob('validation-*/result.json')]
assert len(validations)==1 and validations[0]['status']=='PREPARED_NOT_PHYSICAL_ACCEPTANCE'
assert validations[0]['restoration']['status']=='PASS'
layout=read(SERIES/'layout.json');assert layout['purge_profile_bytes']<32768 and layout['owner_path_bytes']==1688
assert layout['purge_profile_bytes']+layout['gc_profile_bytes']<65536
assert read(SERIES/'code-equivalence.json')['status']=='PASS_UNCHANGED_COMPUTATION_AND_LAYOUT'
prior=read(PRIOR/'sources.json')
for p in [*SERIES.glob('*.py'),*SERIES.glob('*.cpp'),SERIES/'renderer-argv.json']:
 prior['files'][str(p.relative_to(ROOT))]=dict(bytes=p.stat().st_size,sha256=sha(p))
prior['files']['docs/test-plan/perception-purge-slice-v1-protocol.md']={}
write(WORK/'freeze-prior.json',prior)
restore(ROOT,SERIES,WORK,SERIES/'pre-freeze-restoration.json')
engine='/d/shin/stratadrive-tools/UnrealEngine_4.26';carla='/d/shin/stratadrive-tools/m7-source/carla-0.9.16'
try:
 call(['python3',ROOT/'tools/carla/m7_nodrive/build_endurance.py','--engine',engine,'--source',carla,'--output',WORK/'server-build-01','--install'],WORK/'install-module.log')
 call(['python3',ROOT/'tools/carla/m7_nodrive/build_dxc_lifetime.py','--engine',engine,'--output',ROOT/'build/m10-dxc-lifetime-v1','--install'],WORK/'install-dxc.log')
 external=[WORK/'server-build-01/manifest.json',WORK/'server-build-01/libUE4Editor-Carla.so',*read(SERIES/'code-equivalence.json')['engine_source_and_binary_hashes']]
 argv=[PYTHON,ROOT/'tests/integration/perception/freeze_owner_split_v1.py','--output',SERIES,'--prior',WORK/'freeze-prior.json','--protocol','docs/test-plan/perception-purge-slice-v1-protocol.md']
 for p in external:argv+=['--external',p]
 call(argv,WORK/'freeze.log')
finally:restore(ROOT,SERIES,WORK,SERIES/'post-freeze-restoration.json')
call([PYTHON,SERIES/'check-evidence.py','--work',WORK/'frozen-tests'],WORK/'frozen-tests.log')
shutil.copy2(WORK/'frozen-tests/validation.json',SERIES/'frozen-tests.json')
assert read(SERIES/'frozen-tests.json')['focused_tests']==110
frozen=read(SERIES/'sources.json')
write(SERIES/'prepared.json',dict(status='READY_FOR_EXPLICIT_HOST_LEASE',source_files=len(frozen['files']),source_archive_sha256=frozen['archive_sha256'],helper_sha256=sha(ROOT/'tools/m10_boost_lease.py'),python_tests=522,frozen_tests=110,native_admission_cpp_tests=28,admission_preview_reserve_ns=1000000,original_physics_interval_ns=5000000,original_hv_age_ns=30000000,gc_policy=dict(owner_parallel=True,period_seconds=61.1,requested_purge_slice_ns=100000,renderer_unchanged=True),gc_layout=layout,candidate_module_sha256=read(WORK/'server-build-01/manifest.json')['module_sha256'],preparation_validation=validations[0],runtime_restored=True,host_max_perf_pct=int(Path('/sys/devices/system/cpu/intel_pstate/max_perf_pct').read_text()),live_status='NOT_STARTED',privileged_step='operator authentication; unchanged bounded helper and fresh PID'))
print(json.dumps(read(SERIES/'prepared.json')))

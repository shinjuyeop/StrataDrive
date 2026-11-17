"""Freeze the prepared incremental-purge candidate before its host lease."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
from runtime_restore import restore
ROOT=Path(__file__).resolve().parents[4];SERIES=Path(__file__).resolve().parent
WORK=ROOT/'build/m10-gc-owner4-v1';PRIOR=SERIES.with_name('m10_gc_recovery_v3')
PYTHON=ROOT/'build/m10-perception/cuda-venv/bin/python'
BUILD=ROOT/'build/m10-gc-recovery-v1/server-build-02'
read=lambda p:json.loads(p.read_text())
write=lambda p,v:p.write_text(json.dumps(v,indent=2)+'\n')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def call(argv,log):
 with log.open('w') as stream:subprocess.run(list(map(str,argv)),stdout=stream,stderr=subprocess.STDOUT,check=True)
assert not (SERIES/'sources.json').exists()
assert not Path('/proc/3483497').exists()
assert read(PRIOR/'restoration-confirmation.json')['status']=='PASS'
assert 'Ran 545 tests' in (SERIES/'python-tests.txt').read_text() and (SERIES/'python-tests.txt').read_text().rstrip().endswith('OK')
assert '[  PASSED  ] 29 tests.' in (SERIES/'native-admission-tests.txt').read_text()
assert read(SERIES/'model-paths-01/validation.json')['status']=='PASS_ACTUAL_MODEL_SETUP_ONLY'
validations=[read(p) for p in sorted((SERIES/'preparations').glob('validation-*/result.json'))]
assert all(v['validation_only'] is True for v in validations)
assert sha(SERIES/'renderer-argv.json')==sha(PRIOR/'renderer-argv.json')
assert validations[0]['module_sha256']==read(BUILD/'manifest.json')['module_sha256']
assert len(validations)==1 and validations[0]['status']=='PREPARED_NOT_PHYSICAL_ACCEPTANCE'
assert validations[0]['restoration']['status']=='PASS'
assert validations[0]['argv']==['taskset','-c','6-7,14-15',*read(SERIES/'renderer-argv.json')]
model=read(SERIES/'model-paths-01/validation.json')
assert model['owner_worker_cpus']==model['renderer_worker_cpus']==[6,7,14,15]
assert read(SERIES/'model-paths-01/perception.json')['preparation_thread_overrides']==dict(cv=4,resize=4)
assert read(SERIES/'model-paths-01/renderer.json')['host_pipeline']['cv_threads']==4
assert read(SERIES/'model-paths-01/renderer.json')['host_pipeline']['resize_threads']==4
assert sha(SERIES/'check-model-paths.py')==read(SERIES/'model-paths-01/invocation.json')['script_sha256']
layout=read(SERIES/'layout.json');assert layout['purge_profile_bytes']<32768 and layout['owner_path_bytes']==1688
assert layout['purge_profile_bytes']+layout['gc_profile_bytes']<65536
assert read(SERIES/'code-equivalence.json')['status']=='PASS_UNCHANGED_RUNTIME_OWNER_FOUR_LAYOUT'
call([PYTHON,SERIES/'check-runner-wiring.py'],WORK/'runner-wiring.log')
prior=read(PRIOR/'sources.json')
for p in [*SERIES.glob('*.py'),*SERIES.glob('*.cpp'),SERIES/'renderer-argv.json']:
 prior['files'][str(p.relative_to(ROOT))]=dict(bytes=p.stat().st_size,sha256=sha(p))
prior['files']['docs/test-plan/perception-gc-owner4-v1-protocol.md']={}
write(WORK/'freeze-prior.json',prior)
restore(ROOT,SERIES,WORK,SERIES/'pre-freeze-restoration.json')
engine='/d/shin/stratadrive-tools/UnrealEngine_4.26';carla='/d/shin/stratadrive-tools/m7-source/carla-0.9.16'
try:
 call(['python3',ROOT/'tools/carla/m7_nodrive/build_endurance.py','--engine',engine,'--source',carla,'--output',BUILD,'--install'],WORK/'install-module.log')
 call(['python3',ROOT/'tools/carla/m7_nodrive/build_dxc_lifetime.py','--engine',engine,'--output',ROOT/'build/m10-dxc-lifetime-v1','--install'],WORK/'install-dxc.log')
 external=[BUILD/'manifest.json',BUILD/'libUE4Editor-Carla.so',*read(SERIES/'code-equivalence.json')['engine_source_and_binary_hashes'],*[ROOT/x['path'] for x in read(ROOT/'profiles/perception-inference-libraries-host-v1.json')['files']]]
 argv=[PYTHON,ROOT/'tests/integration/perception/freeze_owner_split_v1.py','--output',SERIES,'--prior',WORK/'freeze-prior.json','--protocol','docs/test-plan/perception-gc-owner4-v1-protocol.md']
 for p in external:argv+=['--external',p]
 call(argv,WORK/'freeze.log')
finally:restore(ROOT,SERIES,WORK,SERIES/'post-freeze-restoration.json')
call([PYTHON,SERIES/'check-evidence.py','--work',WORK/'frozen-tests'],WORK/'frozen-tests.log')
shutil.copy2(WORK/'frozen-tests/validation.json',SERIES/'frozen-tests.json')
assert read(SERIES/'frozen-tests.json')['focused_tests']==133
frozen=read(SERIES/'sources.json')
write(SERIES/'prepared.json',dict(status='READY_FOR_EXPLICIT_HOST_LEASE',source_files=len(frozen['files']),source_archive_sha256=frozen['archive_sha256'],helper_sha256=sha(ROOT/'tools/m10_boost_lease.py'),python_tests=545,frozen_tests=133,native_admission_cpp_tests=29,native_admission_test_basis="REUSED_IDENTICAL_RECOVERY_MODULE_AND_CPP_TEST_INPUTS",admission_preview_reserve_ns=300000,original_physics_interval_ns=5000000,original_hv_age_ns=30000000,gc_policy=dict(owner_parallel=True,period_seconds=61.1,requested_purge_slice_ns=100000,renderer_gc_unchanged=True),gc_layout=layout,model_setup_validation_basis='ACTUAL_TWO_IMAGE_CORE_SETUP_AT_100_PERCENT',module_basis='REUSED_IDENTICAL_RECOVERY_MODULE',preparation_validation_basis='ACTUAL_TWO_IMAGE_CORE_EMPTY_RENDERER_AT_100_PERCENT',candidate_module_sha256=read(BUILD/'manifest.json')['module_sha256'],cpu_plan=read(ROOT/'profiles/perception-endurance-host-v5.json')['cpus'],preparation_validation=validations[0],runtime_restored=True,host_max_perf_pct=int(Path('/sys/devices/system/cpu/intel_pstate/max_perf_pct').read_text()),live_status='NOT_STARTED',privileged_step='operator authentication; unchanged bounded helper and fresh PID'))
print(json.dumps(read(SERIES/'prepared.json')))

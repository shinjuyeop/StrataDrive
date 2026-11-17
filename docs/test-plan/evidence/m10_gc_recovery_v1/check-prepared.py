"""Recheck frozen runtime, inputs, tests and restoration before operator launch."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];SERIES=Path(__file__).resolve().parent
read=lambda p:json.loads(p.read_text())
subprocess.run([sys.executable,str(SERIES/'check-runner-wiring.py')],check=True)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as stream:
  for b in iter(lambda:stream.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
build=ROOT/'build/m10-gc-recovery-v1/server-build-02';manifest=read(build/'manifest.json')
for name,expected in manifest['inputs'].items():assert sha(name)==expected,name
for name,expected in manifest['generated'].items():assert sha(build/name)==expected,name
frozen=read(SERIES/'sources.json');assert sha(SERIES/'sources.tar.gz')==frozen['archive_sha256']
for name,item in frozen['files'].items():assert sha(ROOT/name)==item['sha256'],name
original=read(SERIES/'pre-install.json')['files'];installed_module=manifest['module_path']
# Freeze observes installed candidates. Restored files must match the declared
# baseline; all other external binaries/engine inputs remain exact.
restored={item['path']:item['sha256'] for item in original.values()}
for name,expected in frozen['external'].items():assert sha(name)==restored.get(name,expected),name
for name,expected in read(SERIES/'code-equivalence.json')['engine_source_and_binary_hashes'].items():assert sha(name)==expected,name
assert read(SERIES/'frozen-tests.json')['focused_tests']==117
assert 'Ran 529 tests' in (SERIES/'python-tests.txt').read_text()
assert '[  PASSED  ] 29 tests.' in (SERIES/'native-admission-tests.txt').read_text()
assert '--owner-purge-slice' in (SERIES/'prospective-runner.py').read_text()
assert '--owner-recovery-preview' in (SERIES/'prospective-runner.py').read_text()
assert 'perception-endurance-host-v4.json' in (SERIES/'prospective-runner.py').read_text()
for item in original.values():assert sha(item['path'])==item['sha256']
assert int(Path('/sys/devices/system/cpu/intel_pstate/max_perf_pct').read_text())==100
future=read(SERIES.with_name('m10_gc_owner3_v1')/'normal-300s-01/archive-validation.json')['future_exclusion']
result=dict(status='PASS_PREPARED_NOT_LIVE',source_files=len(frozen['files']),archive_sha256=frozen['archive_sha256'],module_basis='BUILT_RECOVERY_PREVIEW_ONLY',candidate_module_sha256=manifest['module_sha256'],preview_reserve_ns=300000,cpu_plan=read(ROOT/'profiles/perception-endurance-host-v4.json')['cpus'],build_input_files=len(manifest['inputs']),build_generated_files=len(manifest['generated']),python_tests=529,frozen_tests=117,native_admission_tests=29,future_exclusion=future,shared_runtime_files_restored=len(original),host_max_perf_pct=100,live_status='NOT_STARTED')
(SERIES/'readiness-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

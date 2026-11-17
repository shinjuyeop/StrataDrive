"""Verify unchanged runtime artifacts and the separately frozen parallel trial."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4];SERIES=Path(__file__).resolve().parent
read=lambda p:json.loads(p.read_text())
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
build=ROOT/'build/m10-admission-window-v1/server-build-01'
manifest=read(build/'manifest.json')
for name,expected in manifest['inputs'].items():assert sha(Path(name))==expected,name
for name,expected in manifest['generated'].items():assert sha(build/name)==expected,name
prior=read(SERIES.with_name('m10_admission_window_v2')/'sources.json')
frozen=read(SERIES/'sources.json')
assert frozen['external']==prior['external']
assert sha(SERIES/'sources.tar.gz')==frozen['archive_sha256']
for name,item in frozen['files'].items():assert sha(ROOT/name)==item['sha256'],name
assert '--owner-serial-gc' not in (SERIES/'prospective-runner.py').read_text()
assert read(SERIES/'prepared.json')['gc_policy']['owner_parallel'] is True
assert read(SERIES/'frozen-tests.json')['focused_tests']==106
assert 'Ran 518 tests' in (SERIES/'python-tests.txt').read_text()
files=read(SERIES/'pre-install.json')['files']
for item in files.values():assert sha(Path(item['path']))==item['sha256']
cap=int(Path('/sys/devices/system/cpu/intel_pstate/max_perf_pct').read_text());assert cap==100
future=read(SERIES.with_name('m10_admission_window_v2')/'normal-300s-01/archive-validation.json')['future_exclusion']
result=dict(status='PASS_PREPARED_NOT_LIVE',source_files=len(frozen['files']),archive_sha256=frozen['archive_sha256'],
    module_reused_from='m10_admission_window_v1',candidate_module_sha256=manifest['module_sha256'],
    all_external_runtime_hashes_unchanged=True,build_input_files=len(manifest['inputs']),
    build_generated_files=len(manifest['generated']),python_tests=518,frozen_tests=106,reused_native_admission_tests=27,
    gc_policy=dict(owner_parallel=True,period_seconds=61.1,live_readback_required=True),
    future_exclusion=future,shared_runtime_files_restored=len(files),host_max_perf_pct=cap,live_status='NOT_STARTED')
(SERIES/'readiness-validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))

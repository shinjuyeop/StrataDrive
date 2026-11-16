"""Post-live completion; retain the original preparation and orchestration FAILs."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
SERIES = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'tests/integration/perception'))
from evidence_reproduction_v1 import require_reproduction
from runtime_restoration_v1 import sha

def read(p): return json.loads(p.read_text())
def write(p, v):
    assert not p.exists(), 'immutable completion evidence'
    p.write_text(json.dumps(v, indent=2)+'\n')

name = 'normal-30s-02'
bundle = SERIES/name
work = ROOT/'build/m10-host-clock-v1'/name
run = work/'archive-check/run'
original = Path(read(bundle/'case.json')['run'])
assert read(bundle/'archive-validation.json')['status'] == 'PASS'
results = {}
for script, filename in [('audit_watch_timing_v1.py', 'monitor-timing'),
                         ('audit_host_clock_v1.py', 'host-clock-audit')]:
    target = work/(filename+'-posthoc.json')
    code = subprocess.run([str(ROOT/'build/m10-perception/cuda-venv/bin/python'),
        str(work/'archive-check/source/tests/integration/perception'/script),
        '--run', str(run), '--output', str(target)], capture_output=True).returncode
    before, after = read(bundle/(filename+'.json')), read(target)
    require_reproduction(before, after, original, run)
    results[filename] = dict(status='PASS_REPRODUCED_ORIGINAL_FAILURE', exit=code,
        original=before, reproduced=after)
write(bundle/'posthoc-reproduction.json', dict(status='PASS', results=results,
    scope='Only exact quoted run-root relocation; original FAIL verdicts unchanged'))

physical = read(run/'capture/result.json')
perception = read(run/'capture/perception.json')
prep = perception['preparation_final']
stages = perception['backend_stages']
assert physical['status'] == 'FAIL' and physical['receipts'] == 0
assert prep['state'] == 'FAILED' and prep['error'] == 'settled probe deadline'
assert len(prep['calls']) == 2 and not (run/'capture/native.json').exists()
write(bundle/'preparation-failure-analysis.json', dict(status='ORIGINAL_FAIL_PRESERVED',
    error=physical['error'], physical_receipts=0, native_started=False, raw_images=0,
    preparation=prep, stage_durations_ms=[dict(
        gray=(r['gray']-r['begin'])/1e6, health=(r['health']-r['gray'])/1e6,
        resize=(r['resize']-r['health'])/1e6, tensor=(r['tensor']-r['resize'])/1e6,
        inference=(r['inference']-r['tensor'])/1e6, decode=(r['decode']-r['inference'])/1e6
        ) for r in stages],
    interpretation='Second synthetic call 131.98ms exceeded unchanged 100ms settled-probe gate. Model setup inherited observer CPUs 0,8; declared CV override was not applied to this owner. Stage wall times do not distinguish computation from descheduling.',
    next_candidate='Place model construction and inference worker on declared pipeline CPUs; apply existing CV/resize settings; keep 10s/3-call/last-two<100ms gate. No retry of this original case.'))

manifest = read(bundle/'run-manifest.json')
assert not read(bundle/'raw-manifest.json')['archives']
assert sha(bundle/manifest['archive']) == manifest['sha256']
files = {str(p.relative_to(original)): p for p in original.rglob('*') if p.is_file()}
assert set(files) == set(manifest['members'])
for name, item in manifest['members'].items():
    assert not files[name].is_symlink()
    assert files[name].stat().st_size == item['bytes'] and sha(files[name]) == item['sha256']
shutil.rmtree(original)
write(bundle/'posthoc-disposition.json', dict(status='COMPLETED_ORIGINAL_FAILURE_EVIDENCE',
    original_sequence_disposition_unchanged=True, finite_diagnostic_pass=False,
    archive='PASS', removed_verified_spool=str(original),
    removed_bytes=sum(v['bytes'] for v in manifest['members'].values()),
    native_perception_accepted=False, milestone_closed=False))

files = read(SERIES/'pre-install.json')['files']
for item in files.values():
    item['checked_sha256'] = sha(item['path'])
    assert item['checked_sha256'] == item['sha256']
policy = {n: Path('/sys/devices/system/cpu/intel_pstate', n).read_text().strip()
          for n in ('min_perf_pct', 'max_perf_pct', 'no_turbo')}
assert policy == dict(min_perf_pct='16', max_perf_pct='100', no_turbo='0')
shutil.copy2(ROOT/'build/m10-host-clock-v1/power-lease.jsonl', SERIES/'power-lease.jsonl')
write(SERIES/'restoration-confirmation.json', dict(status='PASS', wall_ns=time.monotonic_ns(),
    files=files, policy=policy,
    note='All bytes original after historical redundant restoration command failures; original sequence-disposition retained.'))
print('Original failure reproduced; duplicate spool verified and removed; runtime and host restored.')

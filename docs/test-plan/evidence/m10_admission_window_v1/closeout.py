"""Keep the original audit failure and separately validate the auditor correction."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[4];SERIES=Path(__file__).resolve().parent
WORK=ROOT/'build/m10-admission-window-v1';BUNDLE=SERIES/'normal-30s-01'
RUN=WORK/'normal-30s-01/archive-check/run'
read=lambda p:json.loads(p.read_text())
def write(p,v):
    assert not p.exists(), 'immutable closeout record'
    p.write_text(json.dumps(v,indent=2)+'\n')
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
archive=read(BUNDLE/'archive-validation.json')
assert archive==dict(status='PASS',case_verdict='PASS_DIAGNOSTIC_CASE_ONLY',source_files=1525,raw_packets=284,future_exclusion=20840)
original=read(BUNDLE/'admission-window.json');assert original['status']=='FAIL'
assert read(BUNDLE/'admission-window-reproduction.json')['original_status']=='FAIL'
disposition=read(BUNDLE/'disposition.json');assert not disposition['finite_diagnostic_pass']
assert disposition['admission_window']==1 and disposition['physical_audit']==0
assert read(BUNDLE/'replay.json')['exact'] and read(BUNDLE/'drive-fault-replay.json')['equal']
assert read(RUN/'capture/native-drive-fault.json') is None
correction=SERIES/'auditor-correction';correction.mkdir(exist_ok=False)
for name in ('audit_admission_window_v1.py','test_admission_window_v1.py'):
    shutil.copy2(ROOT/'tests/integration/perception'/name,correction/name)
shutil.copy2(WORK/'admission-auditor-regression.log',correction/'regression-tests.txt')
subprocess.run([str(ROOT/'build/m10-perception/cuda-venv/bin/python'),str(correction/'audit_admission_window_v1.py'),
    '--run',str(RUN),'--output',str(correction/'reproduced.json')],check=True)
corrected=read(BUNDLE/'admission-window-corrected.json')
assert corrected['status']=='PASS_ADMISSION_WINDOW_INTEGRITY' and corrected==read(correction/'reproduced.json')
write(correction/'validation.json',dict(status='PASS_POST_RUN_AUDITOR_CORRECTION_ONLY',original_failure_preserved=original,
    original_frozen_auditor_sha256=read(SERIES/'sources.json')['files']['tests/integration/perception/audit_admission_window_v1.py']['sha256'],
    corrected_auditor_sha256=sha(correction/'audit_admission_window_v1.py'),corrected_regression_sha256=sha(correction/'test_admission_window_v1.py'),
    original_capture_unchanged=True,regression_tests=4,corrected_receipts=6000,
    explanation='Server binding/final responses contain structured_state and wall_preview_reserve_ns; original receipts intentionally do not. Check both server responses and unchanged whole-interval receipt coverage separately.',
    changes_to_physics_or_authority=False,original_sequence_verdict_changed=False))
shutil.copy2(WORK/'power-lease.jsonl',SERIES/'power-lease.jsonl')
events=[json.loads(l) for l in (SERIES/'power-lease.jsonl').read_text().splitlines()]
assert [e['event'] for e in events]==['OWNER','APPLIED','RESTORED'] and events[-1]['reason']=='OWNER_EXIT'
server=read(RUN/'server.json');assert all(v['end_wall_ns']<events[-1]['wall_ns'] for v in server['shutdown'].values())
files=read(SERIES/'pre-install.json')['files']
for v in files.values():v['checked_sha256']=sha(Path(v['path']));assert v['checked_sha256']==v['sha256']
policy={n:Path('/sys/devices/system/cpu/intel_pstate',n).read_text().strip() for n in ('min_perf_pct','max_perf_pct','no_turbo')}
assert policy==dict(min_perf_pct='16',max_perf_pct='100',no_turbo='0')
assert 'UE4Editor' not in [v.strip() for v in subprocess.check_output(['ps','-eo','comm='],text=True).splitlines()]
write(SERIES/'restoration-confirmation.json',dict(status='PASS',checked_utc=datetime.now(timezone.utc).isoformat(),files=files,policy=policy,lease_restoration_reason='OWNER_EXIT'))
write(SERIES/'final-validation.json',dict(status='PASS_EVIDENCE_AND_RESTORATION_ONLY',original_sequence='STOPPED_AUDITOR_DEFECT',
    original_physical_audit='PASS_DIAGNOSTIC_CASE_ONLY',original_admission_audit=original,
    post_run_corrected_admission_audit=corrected,original_sequence_verdict_changed=False,
    following_cases='NOT_RUN',normal=5830,init=170,protected=0,raw_packets=284,future_exclusion=20840,
    gc_effect_measured=False,physical_stability_accepted=False,native_perception_accepted=False,milestone_closed=False))
print('Original physical PASS and composite failure retained; corrected audit separately reproduced; original runtime restored.')

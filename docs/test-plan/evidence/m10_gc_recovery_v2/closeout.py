"""Preserve the auditor-process failure separately from passing physical evidence."""
from datetime import datetime,timezone
import hashlib,json,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];S=Path(__file__).resolve().parent;W=ROOT/'build/m10-gc-recovery-v2';B=S/'normal-30s-01';R=W/'normal-30s-01/archive-check/run'
read=lambda p:json.loads(p.read_text())
def write(p,v):
 assert not p.exists(),'immutable closeout';p.write_text(json.dumps(v,indent=2)+'\n')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as stream:
  for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
sequence=read(S/'sequence-disposition.json');assert sequence['runtime_restoration']['status']=='PASS'
assert sequence['cases']['normal-30s-01']==dict(runner_exit=1,finite_diagnostic_pass=False)
identity=read(W/'experiment-owner.json');proc=Path('/proc')/str(identity['pid'])
assert not proc.exists() or int((proc/'stat').read_text().rsplit(')',1)[1].split()[19])!=identity['start_ticks']
shutil.copy2(W/'power-lease.jsonl',S/'power-lease.jsonl')
events=[json.loads(x) for x in (S/'power-lease.jsonl').read_text().splitlines()]
assert [e['event'] for e in events]==['OWNER','APPLIED','RESTORED']
assert events[1]['maximum_percent']==70 and events[-1]['maximum_percent']==100
assert read(B/'archive-validation.json')['status']=='PASS'
assert read(B/'replay.json')['exact'] and read(B/'drive-fault-replay.json')['equal']
for stem in ('state-path','structured-state','monitor-timing','host-clock','owner-wait','workspace','owner-gc'):
 assert read(B/(stem+'-reproduction.json'))['status']=='PASS'
assert not (B/'admission-window.json').exists() and not (B/'disposition.json').exists()
post=read(B/'posthoc-auditor/validation.json');assert post['status']=='PASS_POSTHOC_AUDITOR_REPAIR_ONLY' and post['same_audit_result']
analysis=read(B/'analysis.json');path=read(B/'path-analysis.json');server=read(R/'server.json')
assert events[1]['wall_ns']<path['initial_ns']<path['physical_end_ns']<events[-1]['wall_ns']
assert all(v['end_wall_ns']<events[-1]['wall_ns'] for v in server['shutdown'].values())
assert read(B/'audit.json')['status']=='PASS_DIAGNOSTIC_CASE_ONLY' and analysis['protection_intervals']==0
assert read(B/'owner-gc.json')['live_cycles']==0
owner=read(R/'capture/perception.json');renderer=read(R/'capture/paired/renderer/result.json')
write(B/'startup-summary.json',dict(scope='original actual 70% model setup records',owner={k:owner[k] for k in ('library_prefetch','preparation','closed','cleanup_errors')},renderer={k:renderer[k] for k in ('library_prefetch','preparation')}))
files=read(S/'pre-install.json')['files']
for value in files.values():value['checked_sha256']=sha(Path(value['path']));assert value['checked_sha256']==value['sha256']
policy={n:Path('/sys/devices/system/cpu/intel_pstate',n).read_text().strip() for n in ('min_perf_pct','max_perf_pct','no_turbo')}
assert policy==dict(min_perf_pct='16',max_perf_pct='100',no_turbo='0')
assert 'UE4Editor' not in subprocess.check_output(['ps','-eo','comm='],text=True).splitlines()
write(S/'restoration-confirmation.json',dict(status='PASS',checked_utc=datetime.now(timezone.utc).isoformat(),files=files,policy=policy,lease_restoration_reason=events[-1]['reason'],all_measured_work_and_server_shutdown_before_restoration=True))
write(S/'final-validation.json',dict(status='PASS_EVIDENCE_AND_RESTORATION_ONLY',original_sequence=sequence['cases'],original_verdicts_preserved=True,original_physical_audit='PASS_DIAGNOSTIC_CASE_ONLY',original_supplemental_auditor='FAILED_BEFORE_OUTPUT_IMPORT_ERROR',original_supplemental_reproductions=7,posthoc_eighth_auditor=post,all_declared_finite_cases_pass=False,receipts=analysis['physical_intervals'],normal=analysis['normal_intervals'],init=analysis['init_intervals'],protected=analysis['protection_intervals'],raw=analysis['raw'],inferences=analysis['inferences'],camera_hz=analysis['camera_hz_during_physical'],scene_result_ms=analysis['scene_result_ms'],over_100ms=analysis['over_100ms'],hottest_c=path['fast_clock']['hottest_c'],thermal_delta=path['fast_clock']['thermal_delta'],native_deadlines=read(B/'native-gap-analysis.json')['counts'],gc_recovery_measured=False,continuous_driving_accepted=False,native_perception_accepted=False,milestone_closed=False))
print('Original runner failure preserved; physical replay, posthoc audit and runtime/100% restoration verified.')

"""Close the pre-native failure, preserving original audit failures and bytes."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[4];S=Path(__file__).resolve().parent;W=ROOT/'build/m10-gc-recovery-v1';B=S/'normal-30s-01'
read=lambda p:json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as stream:
  for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
assert not (S/'final-validation.json').exists()
assert not Path('/proc/3439929').exists()
sequence=read(S/'sequence-disposition.json');assert not sequence['cases']['normal-30s-01']['finite_diagnostic_pass']
assert all(isinstance(sequence['cases'][n],str) and sequence['cases'][n].startswith('NOT_RUN') for n in ('normal-30s-02','normal-300s-01'))
assert read(S/'sequence-restoration.json')['status']=='PASS'
events=[json.loads(x) for x in (W/'power-lease.jsonl').read_text().splitlines()]
assert [x['event'] for x in events]==['OWNER','APPLIED','RESTORED']
assert events[0]['pid']==3439929 and events[1]['maximum_percent']==70 and events[2]['maximum_percent']==100 and events[2]['reason']=='OWNER_EXIT'
assert Path('/sys/devices/system/cpu/intel_pstate/max_perf_pct').read_text().strip()=='100'
files=read(S/'pre-install.json')['files'];checks={}
for name,item in files.items():
 digest=sha(item['path']);assert digest==item['sha256'];checks[name]=dict(path=item['path'],sha256=digest)
shutil.copy2(W/'power-lease.jsonl',S/'power-lease.jsonl')
(S/'restoration-confirmation.json').write_text(json.dumps(dict(status='PASS',owner_exited=True,host_max_perf_pct=100,lease_events=events,files=checks),indent=2)+'\n')
archive=read(B/'archive-validation.json');assert archive==dict(status='PASS',case_verdict='FAIL',source_files=1592,raw_packets=0,future_exclusion=34241)
reproductions={p.stem:read(p) for p in B.glob('*-reproduction.json')};assert len(reproductions)==8
assert all(x['status']=='PASS' and x['original_status']=='FAIL' for x in reproductions.values())
run=read(B/'run-manifest.json');assert sha(B/run['archive'])==run['sha256']
review=read(B/'bounded-review.json');assert sha(B/review['archive'])==run['sha256']
result=dict(status='PASS_EVIDENCE_AND_RESTORATION_ONLY',original_case_verdict='FAIL',receipts=0,camera_frames=0,native_started=False,gc_recovery_measured=False,raw_archive_validation=archive,reproduced_original_failed_audits=reproductions,later_cases='NOT_RUN_STOP_ON_FIRST_FAILURE',original_client_exit=-11,worker_cleanup_timeout_preserved=True,native_perception_accepted=False,milestone_closed=False)
(S/'final-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='reproduced_original_failed_audits'}))

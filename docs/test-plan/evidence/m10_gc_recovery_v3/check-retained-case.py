"""Post-freeze standalone CLI regression on the preserved V2 physical case."""
import hashlib,json,os,shutil,subprocess,sys,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];S=Path(__file__).resolve().parent;B=S.with_name('m10_gc_recovery_v2')/'normal-30s-01'
W=ROOT/'build/m10-gc-recovery-v3';SOURCE=W/'frozen-tests/source';RUN=W/'retained-case-run';OUT=S/'retained-case-audits-01'
sys.path.insert(0,str(ROOT/'tests/integration/perception'))
from evidence_reproduction_v1 import require_reproduction
read=lambda p:json.loads(p.read_text())
def identity(data):return dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
manifest=read(B/'run-manifest.json');assert identity((B/manifest['archive']).read_bytes())=={k:manifest[k] for k in ('bytes','sha256')}
RUN.mkdir(exist_ok=False);OUT.mkdir(exist_ok=False)
with tarfile.open(B/manifest['archive'],'r:gz') as tar:
 assert set(tar.getnames())==set(manifest['members'])
 for member in tar.getmembers():
  name=Path(member.name);assert member.isfile() and not name.is_absolute() and '..' not in name.parts
  data=tar.extractfile(member).read();assert identity(data)==manifest['members'][member.name]
  target=RUN/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
auditors=[('state-path','audit_state_path_v1.py','state-path.json'),('structured-state','audit_structured_state_v1.py','structured-state.json'),('monitor-timing','audit_watch_timing_v1.py','monitor-timing.json'),('host-clock','audit_host_clock_v1.py','host-clock-audit.json'),('owner-wait','audit_owner_wait_v1.py','owner-wait.json'),('workspace','audit-workspace.py','workspace.json'),('owner-gc','audit_owner_gc_v1.py','owner-gc.json'),('library-prefetch','audit_library_prefetch_v1.py','posthoc-auditor/corrected-standalone.json')]
results={};env={k:v for k,v in os.environ.items() if k!='PYTHONPATH'};env['PYTHONDONTWRITEBYTECODE']='1'
frozen=read(S/'sources.json')
for label,name,original in auditors:
 relative='tests/integration/perception/'+name if label!='workspace' else str((S/name).relative_to(ROOT))
 script=SOURCE/relative
 assert identity(script.read_bytes())==frozen['files'][relative]
 with (OUT/(label+'.txt')).open('w') as log:
  code=subprocess.run([sys.executable,str(script),'--run',str(RUN),'--output',str(OUT/(label+'.json'))],cwd='/tmp',env=env,stdout=log,stderr=subprocess.STDOUT,timeout=60).returncode
 assert code==0,(label,code)
 result=read(OUT/(label+'.json'));prior=read(B/original)
 prior_run=ROOT/'build/m10-gc-recovery-v2/normal-30s-01/archive-check/run' if label=='library-prefetch' else Path('/tmp/stratadrive-m10-gc-recovery-v2/normal-30s-01')
 require_reproduction(prior,result,prior_run,RUN)
 results[label]=dict(status=result['status'],equal_to_preserved_reference=True,frozen_script_sha256=frozen['files'][relative]['sha256'],reference=str((B/original).relative_to(ROOT)))
files={str(p.relative_to(RUN)):p for p in RUN.rglob('*') if p.is_file()}
assert set(files)==set(manifest['members'])
for name,p in files.items():assert identity(p.read_bytes())==manifest['members'][name]
shutil.rmtree(RUN)
report=dict(status='PASS_FROZEN_STANDALONE_AUDITORS_ON_RETAINED_CASE',auditors=results,physical_receipts=6000,source_archive_sha256=frozen['archive_sha256'],run_archive_sha256=manifest['sha256'],run_from='original V2 physical case; no new live work',original_sequence_verdict_changed=False,pythonpath_removed=True,cwd='/tmp',checked_duplicate_removed=True,removed_bytes=sum(x['bytes'] for x in manifest['members'].values()))
(OUT/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

"""Check frozen auditor compatibility and strict rejection of the prior CPU plan."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];S=Path(__file__).resolve().parent
SOURCE=ROOT/'build/m10-gc-owner4-v1/frozen-tests/source'
B=S.with_name('m10_gc_recovery_v3')/'normal-30s-01'
RUN=ROOT/'build/m10-gc-recovery-v3/normal-30s-01/archive-check/run';OUT=S/'prior-case-audits-01'
sys.path.insert(0,str(ROOT/'tests/integration/perception'))
from evidence_reproduction_v1 import require_reproduction
read=lambda p:json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as stream:
  for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
manifest=read(B/'run-manifest.json');assert read(B/'archive-validation.json')['status']=='PASS'
for name,item in manifest['members'].items():
 p=RUN/name;assert p.stat().st_size==item['bytes'] and sha(p)==item['sha256'],name
frozen=read(S/'sources.json');OUT.mkdir(exist_ok=False)
env={k:v for k,v in os.environ.items() if k!='PYTHONPATH'};env['PYTHONDONTWRITEBYTECODE']='1'
results={}
for name,reference in [('audit_library_prefetch_v1.py','admission-window.json'),('audit_owner_gc_v1.py','owner-gc.json'),('audit_owner_four_v1.py',None)]:
 relative='tests/integration/perception/'+name;script=SOURCE/relative
 assert sha(script)==frozen['files'][relative]['sha256']
 output=OUT/(script.stem+'.json')
 with (OUT/(script.stem+'.txt')).open('w') as log:
  code=subprocess.run([sys.executable,str(script),'--run',str(RUN),'--output',str(output)],cwd='/tmp',env=env,stdout=log,stderr=subprocess.STDOUT,timeout=60).returncode
 value=read(output)
 if reference:
  assert code==0,(name,value)
  require_reproduction(read(B/reference),value,Path('/tmp/stratadrive-m10-gc-recovery-v3/normal-30s-01'),RUN)
  results[name]=dict(status=value['status'],reference=reference,exact_normalized_result=True)
 else:
  assert code==1 and value==dict(status='FAIL',error='explicit owner/image physical-core plan'),value
  results[name]=dict(status='EXPECTED_REJECTION_OF_THREE_CORE_CASE',error=value['error'])
report=dict(status='PASS_PRIOR_THREE_CORE_GATES_AND_FOUR_CORE_REJECTION',results=results,source_archive_sha256=frozen['archive_sha256'],prior_run_archive_sha256=manifest['sha256'],checked_metadata_members=len(manifest['members']),physical_receipts=6000,scope='retained V3 metadata; no new live run or four-core acceptance',pythonpath_removed=True,cwd='/tmp')
(OUT/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

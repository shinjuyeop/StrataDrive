"""Verify unchanged runtime and narrowly extended CPU placement audits."""
import hashlib,json,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];S=Path(__file__).resolve().parent;P=S.with_name('m10_gc_recovery_v3')
read=lambda p:json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as stream:
  for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
f=read(P/'sources.json');assert sha(P/'sources.tar.gz')==f['archive_sha256']
allowed={'tests/integration/perception/audit_library_prefetch_v1.py','tests/integration/perception/audit_owner_three_v1.py','tests/integration/perception/audit_owner_gc_v1.py','tests/integration/perception/test_owner_gc_launcher.py','tools/m10_start_owner_gc.py'}
prefixes=('central/','cmake/','interfaces/','physical_ai/','profiles/','simulation/','tests/','tools/','vecu/','zone/')
checked=[]
for name,item in f['files'].items():
 if name.startswith(prefixes) and name not in allowed:
  assert sha(ROOT/name)==item['sha256'],name;checked.append(name)
with tarfile.open(P/'sources.tar.gz','r:gz') as tar:
 for name in allowed:
  before=tar.extractfile(name).read().decode();after=(ROOT/name).read_text()
  if name.endswith('audit_library_prefetch_v1.py'):
   after=after.replace('def audit(run,recovery_check=recovery_audit):','def audit(run):').replace('result=recovery_check(run)','result=recovery_audit(run)')
  elif name.endswith('audit_owner_three_v1.py'):
   after=after.replace('def validate_placement(server,initial,plan=PLAN):','def validate_placement(server,initial):')
   after=after.replace("!=plan or declared_owner_cpus(server)!=tuple(plan['owner'])","!=PLAN or declared_owner_cpus(server)!=tuple(PLAN['owner'])")
   after=after.replace('explicit owner/image physical-core plan','explicit three-owner/three-image physical-core plan').replace("expected=plan[","expected=PLAN[")
  elif name.endswith('audit_owner_gc_v1.py'):
   after=after.replace('Only the explicit, disjoint','Only the two explicit, disjoint')
   after=after.replace('    four=dict(common,owner=[2,3,4,5,10,11,12,13],renderer=[6,7,14,15])\n','')
   after=after.replace('(baseline,three,four)','(baseline,three)').replace('two/three/four-core','two/three-core').replace('(2,3,4,10,11,12),(2,3,4,5,10,11,12,13)','(2,3,4,10,11,12)')
  else:
   after=after.replace('m10_gc_owner4_v1','m10_gc_recovery_v3').replace('m10-gc-owner4-v1','m10-gc-recovery-v3')
  assert after==before,name
engine=read(P/'code-equivalence.json')['engine_source_and_binary_hashes']
for name,expected in engine.items():assert sha(name)==expected,name
build=read(ROOT/'build/m10-gc-recovery-v1/server-build-02/manifest.json')
assert sha(ROOT/'build/m10-gc-recovery-v1/server-build-02/libUE4Editor-Carla.so')==read(P/'prepared.json')['candidate_module_sha256']==build['module_sha256']
for name in ('build/m10-watch-timing-v1/native-postfix/tests/integration/carla/m7_1g/m7_carla_wall_owner','build/m10-watch-timing-v1/native-postfix/tests/integration/carla/m7_1g/m7_wall_startup_replay'):
 assert sha(ROOT/name)==f['external'][str(ROOT/name)]
profile=read(ROOT/'profiles/perception-inference-libraries-host-v1.json')
for x in profile['files']:assert sha(ROOT/x['path'])==x['sha256'] and (ROOT/x['path']).stat().st_size==x['bytes']
old=read(ROOT/'profiles/perception-endurance-host-v4.json')['cpus'];new=read(ROOT/'profiles/perception-endurance-host-v5.json')['cpus']
assert new['native']==old['native']==[1,9] and new['observer']==old['observer']==[0,8]
assert new['owner']==[2,3,4,5,10,11,12,13] and new['renderer']==[6,7,14,15]
assert set(new['owner'])-set(old['owner'])==set(old['renderer'])-set(new['renderer'])=={5,13}
result=dict(status='PASS_UNCHANGED_RUNTIME_OWNER_FOUR_LAYOUT',baseline_archive_sha256=f['archive_sha256'],unchanged_source_files=len(checked),changed_existing_sources=sorted(allowed),unchanged_module_sha256=build['module_sha256'],engine_source_and_binary_hashes=engine,library_files=len(profile['files']),library_bytes=sum(x['bytes'] for x in profile['files']),preview_reserve_ns=300000,original_preparation_ns=10000000000,original_settled_probe_ns=100000000,cpu_plan_before=old,cpu_plan_after=new,scope='transfer core5 and sibling13 from image to owner; strict explicit placement audits; identical runtime, library reads, clocks, GC cadence and final gates')
(S/'code-equivalence.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='engine_source_and_binary_hashes'}))

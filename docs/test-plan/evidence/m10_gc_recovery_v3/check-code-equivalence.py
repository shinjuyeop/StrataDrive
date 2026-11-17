"""Verify that only the auditor bootstrap and its regression/launch selection changed."""
import hashlib,json,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];S=Path(__file__).resolve().parent;P=S.with_name('m10_gc_recovery_v2')
read=lambda p:json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as stream:
  for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
f=read(P/'sources.json');assert sha(P/'sources.tar.gz')==f['archive_sha256']
allowed={'tests/integration/perception/audit_library_prefetch_v1.py','tests/integration/perception/test_library_prefetch_v1.py','tests/integration/perception/test_owner_gc_launcher.py','tools/m10_start_owner_gc.py'}
prefixes=('central/','cmake/','interfaces/','physical_ai/','profiles/','simulation/','tests/','tools/','vecu/','zone/')
checked=[]
for name,item in f['files'].items():
 if name.startswith(prefixes) and name not in allowed:
  assert sha(ROOT/name)==item['sha256'],name;checked.append(name)
with tarfile.open(P/'sources.tar.gz','r:gz') as tar:
 for name in allowed:
  before=tar.extractfile(name).read().decode();after=(ROOT/name).read_text()
  if name.endswith('audit_library_prefetch_v1.py'):
   bootstrap='import sys\n\n# Standalone execution and frozen archive replay must resolve their own tree.\nsys.path.insert(0, str(Path(__file__).resolve().parents[3]))\n'
   assert after.replace(bootstrap,'')==before
  elif name.endswith(('test_owner_gc_launcher.py','m10_start_owner_gc.py')):
   assert after.replace('m10_gc_recovery_v3','m10_gc_recovery_v2').replace('m10-gc-recovery-v3','m10-gc-recovery-v2')==before
  else:
   after=after.replace('import subprocess\nimport sys\n','')
   start=after.index('    def test_standalone_auditor_help_');end=after.index('    def fixture(',start)
   assert after[:start]+after[end:]==before
engine=read(P/'code-equivalence.json')['engine_source_and_binary_hashes']
for name,expected in engine.items():assert sha(name)==expected,name
build=read(ROOT/'build/m10-gc-recovery-v1/server-build-02/manifest.json')
assert sha(ROOT/'build/m10-gc-recovery-v1/server-build-02/libUE4Editor-Carla.so')==read(P/'prepared.json')['candidate_module_sha256']==build['module_sha256']
for name in ('build/m10-watch-timing-v1/native-postfix/tests/integration/carla/m7_1g/m7_carla_wall_owner','build/m10-watch-timing-v1/native-postfix/tests/integration/carla/m7_1g/m7_wall_startup_replay'):
 assert sha(ROOT/name)==f['external'][str(ROOT/name)]
profile=read(ROOT/'profiles/perception-inference-libraries-host-v1.json')
for x in profile['files']:assert sha(ROOT/x['path'])==x['sha256'] and (ROOT/x['path']).stat().st_size==x['bytes']
result=dict(status='PASS_UNCHANGED_RUNTIME_AUDITOR_IMPORT_ONLY',baseline_archive_sha256=f['archive_sha256'],unchanged_source_files=len(checked),changed_sources=sorted(allowed),unchanged_module_sha256=build['module_sha256'],engine_source_and_binary_hashes=engine,library_files=len(profile['files']),library_bytes=sum(x['bytes'] for x in profile['files']),preview_reserve_ns=300000,original_preparation_ns=10000000000,original_settled_probe_ns=100000000,scope='auditor import bootstrap plus two standalone regressions and launcher target; identical runtime, model, library reads, clocks and acceptance gates')
(S/'code-equivalence.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='engine_source_and_binary_hashes'}))

"""Preserve recovery/control/model code; permit explicit pinned startup reads."""
import hashlib,json,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];S=Path(__file__).resolve().parent;P=S.with_name('m10_gc_recovery_v1')
read=lambda p:json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as stream:
  for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
f=read(P/'sources.json');assert sha(P/'sources.tar.gz')==f['archive_sha256']
protected=('central/','interfaces/','simulation/','vecu/','zone/','tools/carla/m7_nodrive/','physical_ai/')
checked=[]
for name,item in f['files'].items():
 if name.startswith(protected):assert sha(ROOT/name)==item['sha256'],name;checked.append(name)
for name in ('tests/integration/carla/m7_1q/wall_admission_test.cpp','tests/integration/carla/m7_1g/carla_wall_owner.cpp','tests/integration/carla/m7_1g/wall_startup_replay.cpp'):
 assert sha(ROOT/name)==f['files'][name]['sha256'];checked.append(name)
base='tests/integration/perception/'
changed=[base+n for n in ('control_shadow_capture_v1.py','carla_paired_renderer_v1.py','run_carla_paired_v1.py','endurance_host_v1.py')]
with tarfile.open(P/'sources.tar.gz','r:gz') as tar:
 originals={n:tar.extractfile(n).read().decode() for n in changed}
for n in changed:
 text=(ROOT/n).read_text()
 if n.endswith('control_shadow_capture_v1.py'):
  text=text.replace(', prefetch_pipeline_libraries','').replace("        self.report['library_prefetch']={}\n        prefetch_pipeline_libraries(self.report['library_prefetch'])\n",'')
 elif n.endswith('carla_paired_renderer_v1.py'):
  text=text.replace(',prefetch_pipeline_libraries','').replace("            self.report['library_prefetch']={}\n            prefetch_pipeline_libraries(self.report['library_prefetch'])\n",'')
 elif n.endswith('run_carla_paired_v1.py'):
  text=text.replace(",\n                           ('prefetch_inference_libraries','STRATADRIVE_M10_PREFETCH_LIBRARIES')",'').replace("    p.add_argument('--prefetch-inference-libraries',action='store_true')\n",'')
 else:
  a=text.index('def prefetch_pipeline_libraries(');b=text.index('@contextmanager',a);text=text[:a]+text[b:]
 assert text==originals[n],n
engine=read(P/'code-equivalence.json')['engine_source_and_binary_hashes']
for n,expected in engine.items():assert sha(n)==expected,n
build=read(ROOT/'build/m10-gc-recovery-v1/server-build-02/manifest.json')
module=ROOT/'build/m10-gc-recovery-v1/server-build-02/libUE4Editor-Carla.so'
assert sha(module)==read(P/'prepared.json')['candidate_module_sha256']==build['module_sha256']
for n in ('build/m10-watch-timing-v1/native-postfix/tests/integration/carla/m7_1g/m7_carla_wall_owner','build/m10-watch-timing-v1/native-postfix/tests/integration/carla/m7_1g/m7_wall_startup_replay'):
 assert sha(ROOT/n)==f['external'][str(ROOT/n)]
profile=read(ROOT/'profiles/perception-inference-libraries-host-v1.json')
for x in profile['files']:assert sha(ROOT/x['path'])==x['sha256'] and (ROOT/x['path']).stat().st_size==x['bytes']
result=dict(status='PASS_UNCHANGED_RECOVERY_AND_PINNED_LIBRARY_READS',baseline_archive_sha256=f['archive_sha256'],unchanged_source_files=len(checked),unchanged_module_sha256=build['module_sha256'],native_admission_cpp_tests_basis='same test source, module and native binaries; reuse prior29PASS',engine_source_and_binary_hashes=engine,library_files=len(profile['files']),library_bytes=sum(x['bytes'] for x in profile['files']),preview_reserve_ns=300000,original_preparation_ns=10000000000,original_settled_probe_ns=100000000,changed_wrappers=changed,scope='opt-in recorded library reads only; loader, native/model computation, clocks and final gates unchanged')
(S/'code-equivalence.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ('engine_source_and_binary_hashes','changed_wrappers')}))

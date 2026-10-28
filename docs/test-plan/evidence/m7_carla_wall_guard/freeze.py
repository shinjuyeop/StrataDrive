from pathlib import Path
import gzip,hashlib,json,shutil,subprocess
root=Path('/d/shin/stratadrive-tools/m7-source/m7-wall-containment')
repo=Path('/d/shin/StrataDrive')
dest=repo/'docs/test-plan/evidence/m7_carla_wall_guard'
dest.mkdir(exist_ok=False)
archives=[]
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def copy(path,relative):
 out=dest/relative;out.parent.mkdir(parents=True,exist_ok=True)
 if path.suffix in ('.jsonl','.log'):
  out=Path(str(out)+'.gz')
  with path.open('rb') as f,out.open('wb') as raw,gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as z:shutil.copyfileobj(f,z)
  h=hashlib.sha256()
  with gzip.open(out,'rb') as f:
   for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
  original=sha(path);assert h.hexdigest()==original
  archives.append(dict(source=str(path),archive=str(out.relative_to(dest)),raw_sha256=original,archive_sha256=sha(out),raw_bytes=path.stat().st_size))
 else:shutil.copy2(path,out)
for p in sorted(root.iterdir()):
 if p.is_file():copy(p,p.name)
for suite in ('suite-a','suite-b'):
 for p in sorted((root/suite).rglob('*')):
  if p.is_file():copy(p,p.relative_to(root))
for runtime in ('runtime-a','runtime-b'):
 for p in sorted((root/runtime).rglob('*.log')):
  if 'probe' not in p.parts:copy(p,p.relative_to(root))
source_paths=['tests/integration/carla/m7_1f/wall_execution_watch.hpp','tests/integration/carla/m7_1f/functional_rig.hpp','tests/integration/carla/m7_1f/functional_rig.cpp','tests/integration/carla/m7_1g/wheel_main.cpp','tests/integration/carla/m7_1g/wheel_test.cpp','simulation/runtime/m4_execution_watch.hpp','simulation/runtime/m4_execution_watch.cpp','vecu/common/periodic_task.hpp','vecu/common/periodic_task.cpp']
for rel in source_paths:copy(repo/rel,Path('native-sources')/rel)
binaries=['build/m7-functional/tests/integration/carla/m7_1g/m7_wheel_shadow','build/m7-functional/tests/integration/carla/m7_1g/m7_wheel_test','build/m7-functional-asan/tests/integration/carla/m7_1g/m7_wheel_test','build/m7-wall-tsan/tests/integration/carla/m7_1g/m7_wheel_test']
metadata=dict(base_commit='355ed25f844aecd439cbfc2f63acffb4df9b260a',source_sha256={p:sha(repo/p) for p in source_paths},binary_sha256={p:sha(repo/p) for p in binaries},normal_tests=76,asan_ubsan_tests=76,tsan_tests=3,tsan_command="setarch x86_64 -R build/m7-wall-tsan/tests/integration/carla/m7_1g/m7_wheel_test --gtest_filter=M7WallWatch.*",tsan_initial_execution='FATAL unexpected memory mapping; no test executed',tsan_initial_build='M7 opt-in flag absent; target not generated; corrected using STRATADRIVE_M7_FUNCTIONAL_TESTS=ON',m6_source_unchanged=subprocess.run(['git','diff','--quiet','355ed25','--','interfaces','central','zone','vecu','simulation'],cwd=repo).returncode==0)
old=json.loads((repo/'docs/test-plan/evidence/m7_carla_recovery/causal-followup/server-protection.json').read_text())['executed_artifact_sha256']
new=json.loads((root/'suite-b/server-protection.json').read_text())['executed_artifact_sha256']
metadata['unchanged_server_modules']={p:new[p]==h for p,h in old.items() if p.endswith('.so')}
assert metadata['m6_source_unchanged'] and all(metadata['unchanged_server_modules'].values())
(dest/'source-and-validation.json').write_text(json.dumps(metadata,indent=2)+'\n')
(dest/'archive-manifest.json').write_text(json.dumps(archives,indent=2)+'\n')
print(json.dumps(dict(files=sum(p.is_file() for p in dest.rglob('*')),archives=len(archives),bytes=sum(p.stat().st_size for p in dest.rglob('*') if p.is_file()))))

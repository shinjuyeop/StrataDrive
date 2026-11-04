from pathlib import Path
import json,shutil,tarfile,subprocess,hashlib,platform,os
src=Path('build/m9-completion');dst=Path('docs/test-plan/evidence/m9_completion');dst.mkdir(parents=True,exist_ok=True)
def archive(source,target):
 with tarfile.open(dst/target,'w:gz') as t:t.add(source,arcname=Path(source).name)
# Every attempt directory is retained; generated giant physics traces use the existing LFS convention.
for p in sorted(src.iterdir()):
 if p.is_dir() and (p/'plan.json').exists():archive(p,p.name+'.tar.gz')
for name in ['capacity-normal','carla-campaign-source','carla-silent-loss-attempt-source']:
 archive(src/name,name+'.tar.gz')
shutil.copytree(src/'carla',dst/'carla',dirs_exist_ok=True)
archive(src/'logs','validation-logs.tar.gz')
for p in src.glob('*.json'):
 if p.is_file():shutil.copy2(p,dst/p.name)
for name in ['replay_final.py','package_evidence.py','source-final.tar.gz']:
 shutil.copy2(src/name,dst/name)
# Preserve the installed integration patch identity without duplicating external engine binaries.
shutil.copy2('/d/shin/stratadrive-tools/m7-source/m7-nodrive-install.json',dst/'carla-install-after.json')
shutil.copy2(src/'carla-load-build/install-before.json',dst/'carla-install-before.json')
with (dst/'implementation.diff').open('wb') as f:subprocess.run(['git','diff','--','.',':(exclude)docs/test-plan/evidence/**'],stdout=f,check=True)
artifacts={}
for name,path in [('core','build/m1-angle/vehicle_coordinator_test'),('asan','build/m1-angle-sanitized/vehicle_coordinator_test'),('carla','build/m7-functional/tests/integration/carla/m7_1g/m7_wheel_shadow'),('native-normal','build/m5-someip-normal/project/tests/integration/someip/someip_front_adapter'),('native-asan','build/m5-someip-asan/project/tests/integration/someip/someip_front_adapter'),('native-tsan','build/m5-someip-tsan/project/tests/integration/someip/someip_front_adapter')]:
 p=Path(path);artifacts[name]=dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
(dst/'artifacts.json').write_text(json.dumps(dict(platform=platform.platform(),artifacts=artifacts),indent=2)+'\n')
# Immutable previous evidence is checked independently; never regenerate its manifests.
old=[]
for name in ['m9_native_service','m8_stop30']:
 d=dst.parent/name;p=subprocess.run(['sha256sum','-c','SHA256SUMS'],cwd=d,text=True,capture_output=True,env=dict(os.environ,LC_ALL='C'))
 old.append(dict(bundle=name,exit=p.returncode,checked=sum(x.endswith(': OK') for x in p.stdout.splitlines()),errors=p.stderr))
(dst/'previous-integrity.json').write_text(json.dumps(old,indent=2)+'\n')
print('packaged',dst)

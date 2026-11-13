from datetime import datetime,timezone
import hashlib,json,subprocess,sys,time
from pathlib import Path
root=Path('/d/shin/StrataDrive');bundle=root/'docs/test-plan/evidence/m10_paired_v2'
sys.path.insert(0,str(root/'tests/integration/perception'))
from seal_paired_v1 import archive
preparation=root/'build/m10-paired-v2/original-profile-cache-check-01'
end=time.monotonic()+3600
while not (preparation/'result.json').exists():
 if time.monotonic()>end:raise TimeoutError('bounded preparation dependency')
 time.sleep(1)
result=json.loads((preparation/'result.json').read_text())
manifest=archive(preparation,sorted(p for p in preparation.rglob('*') if p.is_file()),bundle/'original-profile-cache-check-01.tar.gz')
(bundle/'original-profile-cache-manifest-01.json').write_text(json.dumps(manifest,indent=2)+'\n')
if result['status']!='ORIGINAL_PROFILE_CACHE_READY':raise RuntimeError('preparation did not qualify; paired attempt not started')
values=dict(engine='/d/shin/stratadrive-tools/UnrealEngine_4.26',source='/d/shin/stratadrive-tools/m7-source/carla-0.9.16',
 python=str(root/'build/m10-perception/cuda-venv/bin/python'),native=str(root/'build/m10-live-shadow-v1/normal/tests/integration/carla/m7_1g/m7_carla_wall_owner'),
 detector=str(root/'build/m10-resolution-v2/models/dfine-960.onnx'),models=str(root/'build/m10-resolution-v2/models.json'),
 library=str(root/'build/m10-source-compare-v1/native/libstrata_resize_2k_v1.so'),freeze=str(bundle/'sources.json'),
 output=str(root/'build/m10-paired-v2/normal-01'),condition='normal')
command=[values['python'],str(root/'tests/integration/perception/run_carla_paired_v1.py')]
for k,v in values.items():command.extend(['--'+k,v])
case=dict(schema='m10-paired-case-v1',declared_utc=datetime.now(timezone.utc).isoformat(),condition='normal',attempt=1,
 run='build/m10-paired-v2/normal-01',freeze_sha256=hashlib.sha256((bundle/'sources.json').read_bytes()).hexdigest(),
 protocol='docs/test-plan/perception-paired-v1-protocol.md',complete_visual_scene=False,holdout_access=False,
 preparation_sha256=hashlib.sha256((preparation/'result.json').read_bytes()).hexdigest(),argv=command)
with (bundle/'case.json').open('x') as f:f.write(json.dumps(case,indent=2)+'\n')
with (root/'build/m10-paired-v2/normal-01.log').open('x') as log:
 run=subprocess.run(command,cwd=root,stdout=log,stderr=subprocess.STDOUT)
print('paired runner exit',run.returncode,flush=True)

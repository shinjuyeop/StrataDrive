import json,os,sys,subprocess,time,resource,hashlib,traceback
from pathlib import Path
sys.path.insert(0,str(Path('/d/shin/StrataDrive/tests/integration/perception')))
from renderer_shutdown_v1 import shutdown,allow_shutdown_tracer
from run_carla_control_shadow_v1 import verify
root=Path('/d/shin/StrataDrive');out=root/'build/m10-paired-v2/cache-preparation-01';out.mkdir(parents=True,exist_ok=False)
freeze=root/'docs/test-plan/evidence/m10_paired_v2/sources.json'
report=dict(status='FAIL',purpose='cold derived-data cache preparation only; no sensor/ego/native control',startup_limit_seconds=900,raw_images=0)
p=None
ini=Path('/d/shin/stratadrive-tools/m7-source/carla-0.9.16/Unreal/CarlaUE4/Saved/Config/Linux/GameUserSettings.ini');original=ini.read_bytes()
try:
 report['freeze_sha256']=verify(freeze)
 previous=json.loads((root/'build/m10-paired-v1/normal-01/server.json').read_text())
 command=previous['argv']['renderer'];report['argv']=command
 env=dict(os.environ);env.pop('STRATADRIVE_M7_OWNER_KEY',None)
 def hook():
  resource.setrlimit(resource.RLIMIT_CORE,(0,0));allow_shutdown_tracer()
 with (out/'server.log').open('w') as log:
  p=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=hook)
  report['pid']=p.pid;report['begin_ns']=time.monotonic_ns();deadline=time.monotonic()+900
  import carla
  c=carla.Client('127.0.0.1',2300);c.set_timeout(2)
  while time.monotonic()<deadline:
   if p.poll() is not None:raise RuntimeError('cache server exited')
   try:
    w=c.get_world();s=w.get_snapshot()
    if s.frame>0:
     report['ready_ns']=time.monotonic_ns();report['world']=w.id;report['frame']=s.frame
     report['actors']=[a.type_id for a in w.get_actors() if a.type_id.startswith(('sensor.','vehicle.','walker.'))]
     if report['actors']:raise ValueError('unexpected dynamic actor')
     break
   except RuntimeError:pass
   time.sleep(.1)
  else:raise TimeoutError('bounded cold cache preparation')
  report['status']='CACHE_PREPARED_NO_MEASUREMENT'
except Exception:report['error']=traceback.format_exc()
finally:
 if p:
  report['shutdown']=shutdown(p,out/'shutdown',diagnostics=True)
  if report['shutdown']['server_exit']!=130 or report['shutdown'].get('forced_stop'):report['status']='FAIL'
 ini.write_bytes(original);report['restored_ini_sha256']=hashlib.sha256(ini.read_bytes()).hexdigest()
 (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))

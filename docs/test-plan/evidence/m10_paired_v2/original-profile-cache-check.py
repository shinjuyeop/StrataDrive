import hashlib,json,os,resource,signal,subprocess,sys,time,traceback
from pathlib import Path
sys.path.insert(0,'/d/shin/StrataDrive/tests/integration/perception')
from renderer_shutdown_v1 import allow_shutdown_tracer,shutdown
from run_carla_control_shadow_v1 import verify
root=Path('/d/shin/StrataDrive');out=root/'build/m10-paired-v2/original-profile-cache-check-01';out.mkdir(parents=True,exist_ok=False)
source=Path('/d/shin/stratadrive-tools/m7-source/carla-0.9.16')
ini=source/'Unreal/CarlaUE4/Saved/Config/Linux/GameUserSettings.ini';original=ini.read_bytes();p=None
report=dict(status='FAIL',purpose='original-profile cache-hit startup check after retained synchronous-build crash; no native owner or sensors',limit_seconds=300,raw_images=0,control=False,quiet_seconds=10)
def workers(pid):
 result={}
 for item in Path('/proc').iterdir():
  if not item.name.isdigit():continue
  try:
   line=(item/'stat').read_text();tail=line[line.rfind(')')+2:].split()
   if int(tail[1])==pid and b'ShaderCompileWorker' in (item/'cmdline').read_bytes():result[int(item.name)]=int(tail[11])+int(tail[12])
  except (OSError,ValueError):pass
 return result
try:
 report['freeze_sha256']=verify(root/'docs/test-plan/evidence/m10_paired_v2/sources.json')
 command=json.loads((root/'build/m10-paired-v1/normal-01/server.json').read_text())['argv']['renderer']
 report['argv']=command;(out/'declaration.json').write_text(json.dumps(report,indent=2)+'\n')
 env=dict(os.environ);env.pop('STRATADRIVE_M7_OWNER_KEY',None)
 def hook():resource.setrlimit(resource.RLIMIT_CORE,(0,0));allow_shutdown_tracer()
 with (out/'server.log').open('w') as log:
  p=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=hook)
  report['pid']=p.pid;report['begin_ns']=time.monotonic_ns();deadline=time.monotonic()+300
  Path(f'/proc/{p.pid}/oom_score_adj').write_text('1000')
  import carla
  c=carla.Client('127.0.0.1',2300);c.set_timeout(2)
  quiet=None;prior=None;minimum=2**63
  while time.monotonic()<deadline:
   if p.poll() is not None:raise RuntimeError('preparation server exited')
   available=next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
   minimum=min(minimum,available)
   if available<2*1024**3:raise MemoryError('cache preparation preserves2GiB host availability')
   if 'ready_ns' not in report:
    try:
     w=c.get_world();snapshot=w.get_snapshot()
     if snapshot.frame>0:
      report['ready_ns']=time.monotonic_ns();report['world']=w.id
      report['actors']=[x.type_id for x in w.get_actors() if x.type_id.startswith(('sensor.','vehicle.','walker.'))]
      if report['actors']:raise ValueError('unexpected preparation actors')
    except RuntimeError:pass
   else:
    current=workers(p.pid)
    if current==prior:
     if quiet is None:quiet=time.monotonic()
     if time.monotonic()-quiet>=10:
      text=(out/'server.log').read_text(errors='replace')
      report['quiet_ns']=time.monotonic_ns();report['idle_shader_workers']=current
      break
    else:quiet=None
    prior=current
   time.sleep(1)
  else:raise TimeoutError('bounded synchronous cache preparation')
  report['minimum_available_bytes']=minimum;report['status']='ORIGINAL_PROFILE_CACHE_READY'
except Exception:report['error']=traceback.format_exc()
finally:
 if p is not None:
  report['shutdown']=shutdown(p,out/'shutdown',diagnostics=True)
  if report['shutdown']['server_exit']!=130 or report['shutdown'].get('forced_stop'):report['status']='FAIL'
 ini.write_bytes(original);report['restored_ini_sha256']=hashlib.sha256(ini.read_bytes()).hexdigest()
 (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k in ('status','error','ready_ns','quiet_ns')}))

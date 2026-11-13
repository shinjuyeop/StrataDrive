import hashlib,json,os,resource,subprocess,sys,time,traceback
from pathlib import Path
root=Path('/d/shin/StrataDrive');sys.path.insert(0,str(root/'tests/integration/perception'))
from renderer_shutdown_v1 import allow_shutdown_tracer,shutdown
from carla_readiness_v1 import wait_ready
from run_carla_control_shadow_v1 import verify
out=root/'build/m10-paired-v3/cache-preparation-01';out.mkdir(parents=True,exist_ok=False)
ini=Path('/d/shin/stratadrive-tools/m7-source/carla-0.9.16/Unreal/CarlaUE4/Saved/Config/Linux/GameUserSettings.ini')
original=ini.read_bytes();p=None
report=dict(status='FAIL',purpose='original profile cache preparation; fresh bounded SDK probe; wait for distance-field and shader workers to finish',limit_seconds=1800,quiet_seconds=10,raw_images=0,native_control=False)
def active(pid):
 result=[]
 for t in Path(f'/proc/{pid}/task').iterdir():
  try:
   name=(t/'comm').read_text().strip()
   if name.startswith('BuildDi') and 'Field' in name:result.append(dict(kind='distance-field',tid=int(t.name),name=name))
  except FileNotFoundError:pass
 for item in Path('/proc').iterdir():
  if not item.name.isdigit():continue
  try:
   line=(item/'stat').read_text();tail=line[line.rfind(')')+2:].split()
   if int(tail[1])==pid and b'ShaderCompileWorker' in (item/'cmdline').read_bytes():result.append(dict(kind='shader',pid=int(item.name)))
  except (OSError,ValueError):pass
 return result
try:
 report['freeze_sha256']=verify(root/'docs/test-plan/evidence/m10_paired_v3/sources.json')
 command=json.loads((root/'build/m10-paired-v1/normal-01/server.json').read_text())['argv']['renderer']
 report['argv']=command;(out/'declaration.json').write_text(json.dumps(report,indent=2)+'\n')
 env=dict(os.environ);env.pop('STRATADRIVE_M7_OWNER_KEY',None)
 def hook():resource.setrlimit(resource.RLIMIT_CORE,(0,0));allow_shutdown_tracer()
 with (out/'server.log').open('w') as log:
  p=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=hook)
  report['pid']=p.pid;report['begin_ns']=time.monotonic_ns();deadline=time.monotonic()+1800
  Path(f'/proc/{p.pid}/oom_score_adj').write_text('1000')
  report['ready']=wait_ready(sys.executable,2300,out/'readiness.jsonl',env);report['ready_ns']=time.monotonic_ns()
  quiet=None;minimum=2**63;prior=None
  with (out/'build-workers.jsonl').open('w') as events:
   while time.monotonic()<deadline:
    if p.poll() is not None:raise RuntimeError('preparation server exited')
    available=next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
    minimum=min(minimum,available)
    if available<2*1024**3:raise MemoryError('preserve2GiB available host memory')
    current=active(p.pid)
    if current!=prior:events.write(json.dumps(dict(wall_ns=time.monotonic_ns(),workers=current))+'\n');events.flush();prior=current
    if not current:
     if quiet is None:quiet=time.monotonic()
     if time.monotonic()-quiet>=10:break
    else:quiet=None
    time.sleep(1)
   else:raise TimeoutError('finite1800s preparation horizon')
  report['quiet_ns']=time.monotonic_ns();report['minimum_available_bytes']=minimum
  probe="""import carla,json
c=carla.Client('127.0.0.1',2300);c.set_timeout(2);w=c.get_world();s=w.get_snapshot()
print(json.dumps(dict(world=w.id,frame=s.frame,actors=[a.type_id for a in w.get_actors() if a.type_id.startswith(('sensor.','vehicle.','walker.'))])))
"""
  final=subprocess.run([sys.executable,'-c',probe],env=env,capture_output=True,text=True,timeout=5,check=True)
  report['final']=json.loads(final.stdout)
  assert report['final']['world']==report['ready']['world'] and report['final']['frame']>report['ready']['frame'] and not report['final']['actors']
  report['status']='ORIGINAL_PROFILE_CACHE_READY'
except Exception:report['error']=traceback.format_exc()
finally:
 if p is not None:
  report['shutdown']=shutdown(p,out/'shutdown',diagnostics=True)
  if report['shutdown']['server_exit']!=130 or report['shutdown'].get('forced_stop'):report['status']='FAIL'
 ini.write_bytes(original);report['restored_ini_sha256']=hashlib.sha256(ini.read_bytes()).hexdigest()
 (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k in ('status','error','ready_ns','quiet_ns')}))

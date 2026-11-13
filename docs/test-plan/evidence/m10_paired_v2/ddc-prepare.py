import hashlib,json,os,resource,subprocess,sys,time,traceback
from pathlib import Path
sys.path.insert(0,'/d/shin/StrataDrive/tests/integration/perception')
from renderer_shutdown_v1 import allow_shutdown_tracer,shutdown
from run_carla_control_shadow_v1 import verify
root=Path('/d/shin/StrataDrive');source=Path('/d/shin/stratadrive-tools/m7-source/carla-0.9.16')
engine=Path('/d/shin/stratadrive-tools/UnrealEngine_4.26')
out=root/'build/m10-paired-v2/ddc-preparation-01';out.mkdir(parents=True,exist_ok=False)
maps=source/'Unreal/CarlaUE4/Content/Carla/Maps'
selected=[maps/'Town03_Opt.umap',*sorted((maps/'Sublevels/Town03_Opt').glob('*.umap'))]
command=[str(engine/'Engine/Binaries/Linux/UE4Editor'),str(source/'Unreal/CarlaUE4/CarlaUE4.uproject'),
 '-run=DerivedDataCache','-fill','-mapsonly','-projectonly','-TargetPlatform=Linux',
 '-Map='+('+'.join(str(p.with_suffix('')) for p in selected)),
 '-nullrhi','-unattended','-nosound','-nosplash','-stdout','-FullStdOutLogOutput',
 '-ini:EditorSettings:[/Script/UnrealEd.CrashReportsPrivacySettings]:bSendUnattendedBugReports=False',
 '-ini:Engine:[CrashReportClient]:bAgreeToCrashUpload=False,[CrashReportClient]:bImplicitSend=False']
report=dict(schema='m10-paired-ddc-preparation-v1',status='FAIL',limit_seconds=3600,argv=command,
 raw_images=0,native_control=False,rendering=False,maps=[str(p) for p in selected])
ini=source/'Unreal/CarlaUE4/Saved/Config/Linux/GameUserSettings.ini';original=ini.read_bytes();p=None
try:
 report['freeze_sha256']=verify(root/'docs/test-plan/evidence/m10_paired_v2/sources.json')
 report['map_sha256']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in selected}
 (out/'declaration.json').write_text(json.dumps(report,indent=2)+'\n')
 def hook():resource.setrlimit(resource.RLIMIT_CORE,(0,0));allow_shutdown_tracer()
 env=dict(os.environ);env.pop('STRATADRIVE_M7_OWNER_KEY',None)
 with (out/'commandlet.log').open('w') as log:
  report['begin_ns']=time.monotonic_ns()
  p=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=hook)
  report['pid']=p.pid;report['exit']=p.wait(timeout=3600);report['end_ns']=time.monotonic_ns()
  if report['exit']!=0:raise RuntimeError('cache commandlet failed')
  text=(out/'commandlet.log').read_text(errors='replace')
  if 'Done waiting for shaders to finish.' not in text:raise ValueError('missing cache completion')
  for file,digest in report['map_sha256'].items():
   if hashlib.sha256(Path(file).read_bytes()).hexdigest()!=digest:raise ValueError('map asset changed')
  report['status']='CACHE_BUILT_REQUIRES_SERVER_CHECK'
except Exception:report['error']=traceback.format_exc()
finally:
 if p is not None and p.poll() is None:report['shutdown']=shutdown(p,out/'shutdown',diagnostics=True)
 ini.write_bytes(original);report['restored_ini_sha256']=hashlib.sha256(ini.read_bytes()).hexdigest()
 (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k in ('status','error','exit')}))

"""Two empty-server lifecycle checks; no camera, inference or native actuation."""
import argparse
import json
import os
from pathlib import Path
import resource
import socket
import subprocess

from carla_readiness_v1 import wait_ready
from renderer_shutdown_v1 import shutdown,allow_shutdown_tracer
from run_carla_control_shadow_v1 import verify,sha


def main(a):
    a.output.mkdir(parents=True,exist_ok=False)
    report=dict(scope='empty renderer shutdown only; no camera or native session',cases=[],status='FAIL')
    ini=a.source/'Unreal/CarlaUE4/Saved/Config/Linux/GameUserSettings.ini';original=ini.read_bytes()
    installed=a.engine/'Engine/Binaries/ThirdParty/ShaderConductor/Linux/x86_64-unknown-linux-gnu/libdxcompiler.so'
    m=json.loads(a.manifest.read_text());assert sha(installed)==m['candidate_sha256']
    env=dict(os.environ);assert not env.get('LD_PRELOAD');env.pop('STRATADRIVE_M7_OWNER_KEY',None)
    def hook():resource.setrlimit(resource.RLIMIT_CORE,(0,0));allow_shutdown_tracer()
    try:
        report['freeze_sha256']=verify(a.freeze)
        frozen=json.loads(a.freeze.read_text())['external']
        assert frozen.get(str(a.manifest.resolve()))==sha(a.manifest),'frozen DXC build manifest'
        assert frozen.get(str(installed.resolve()))==m['candidate_sha256'],'frozen installed DXC'
        for index in range(1,3):
            case=a.output/f'exit-{index}';case.mkdir();item=dict(attempt=index);report['cases'].append(item)
            guards=[]
            try:
                for port in (2400,2401,2402):s=socket.socket();guards.append(s);s.bind(('127.0.0.1',port))
            finally:
                for s in guards:s.close()
            argv=[str(a.engine/'Engine/Binaries/Linux/UE4Editor'),str(a.source/'Unreal/CarlaUE4/CarlaUE4.uproject'),
                '/Game/Carla/Maps/Town03_Opt','-game','-FixedSeed','-RenderOffScreen','-nosound','-unattended','-nosplash',
                '-carla-server','-quality-level=Epic','-carla-rpc-port=2400','-ExecCmds=t.MaxFPS 20',
                '-ini:EditorSettings:[/Script/UnrealEd.CrashReportsPrivacySettings]:bSendUnattendedBugReports=False',
                '-ini:Engine:[CrashReportClient]:bAgreeToCrashUpload=False,[CrashReportClient]:bImplicitSend=False',
                '-log','-stdout','-FullStdOutLogOutput']
            item['argv']=argv
            with (case/'server.log').open('w') as log:
                process=subprocess.Popen(argv,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=hook)
                try:
                    item['readiness']=wait_ready(a.python,2400,case/'readiness.jsonl',env)
                    maps=Path(f'/proc/{process.pid}/maps').read_text();(case/'maps.txt').write_text(maps)
                    item['candidate_mapped']=any('libdxcompiler.so' in line and int(line.split()[4])==installed.stat().st_ino for line in maps.splitlines())
                    assert item['candidate_mapped'],'candidate DXC must actually be loaded'
                    script="import carla,json;c=carla.Client('127.0.0.1',2400);c.set_timeout(2);print(json.dumps([a.id for a in c.get_world().get_actors().filter('sensor.*')]))"
                    item['sensors']=json.loads(subprocess.check_output([str(a.python),'-c',script],env=env,text=True,timeout=5));assert not item['sensors']
                finally:item['shutdown']=shutdown(process,case,diagnostics=True)
            assert item['shutdown']['server_exit']==130 and not item['shutdown'].get('forced_stop')
        assert verify(a.freeze)==report['freeze_sha256']
        report['status']='PASS_EMPTY_RENDERER_LIFECYCLE_ONLY'
    except Exception as error:report['error']=repr(error)
    finally:
        ini.write_bytes(original);report['ini_sha256']=sha(ini)
        (a.output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report));return 0 if report['status'].startswith('PASS') else 1


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('engine','source','python','manifest','freeze','output'):p.add_argument('--'+name,type=Path,required=True)
    raise SystemExit(main(p.parse_args()))

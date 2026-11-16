"""One original-UE guard check before START; no native execution or camera."""
import hashlib
import json
import os
from pathlib import Path
import resource
import secrets
import socket
import subprocess
import sys
import tarfile
import time
import traceback

ROOT=Path(__file__).resolve().parents[4]
SERIES=Path(__file__).resolve().parent
OUT=SERIES/'nonfinite-guard-01'
BUILD=ROOT/'build/m10-structured-state-v1/server-build-04'
ENGINE=Path('/d/shin/stratadrive-tools/UnrealEngine_4.26')
CARLA=Path('/d/shin/stratadrive-tools/m7-source/carla-0.9.16')
PYTHON=ROOT/'build/m10-perception/cuda-venv/bin/python'
SCRIPTS=ROOT/'tests/integration/perception'
sys.path.insert(0,str(SCRIPTS))
from carla_readiness_v1 import wait_ready
from renderer_shutdown_v1 import shutdown,allow_shutdown_tracer
from profile_host_v1 import host


def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def client():
    import carla
    from audit_structured_state_v1 import validate_self_check
    report=dict(status='FAIL',native_started=False,images=0,scope='before-START nonfinite guard only')
    try:
        c=carla.Client('127.0.0.1',2200);c.set_timeout(10)
        report['versions']=[c.get_client_version(),c.get_server_version()]
        assert report['versions']==['294096e-dirty']*2
        world=c.get_world();assert world.get_map().name.endswith('/Town03_Opt')
        assert not any(list(world.get_actors().filter(k)) for k in ('vehicle.*','sensor.*','walker.*'))
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.005
        settings.no_rendering_mode=True;settings.substepping=True;settings.max_substep_delta_time=.01;settings.max_substeps=10
        world.apply_settings(settings);world.tick()
        bp=world.get_blueprint_library().find('vehicle.lincoln.mkz_2020');bp.set_attribute('role_name','m7_wall_actual')
        actor=world.spawn_actor(bp,world.get_map().get_spawn_points()[0]);world.tick()
        def rpc(op,**kwargs):
            return json.loads(c.m7_nodrive(json.dumps(dict(op=op,owner_key=os.environ['STRATADRIVE_M7_OWNER_KEY'],**kwargs))))
        bound=rpc('bind',actor=str(actor.id),application='42',model_sha256=sha(ROOT/'tools/carla/m7_nodrive/virtual_ev_v1.json'))
        report['binding']=bound;assert bound['ok'] and bound['structured_state']
        check=rpc('structured_json_check',session=bound['session'],run=bound['run'])
        report['check']=check;validate_self_check(check)
        report['final']=rpc('describe')
        assert int(report['final']['wall_frames'])==int(report['final']['structured_direct_requests'])==0
        report['status']='PASS_BEFORE_START_ONLY'
    except Exception:report['error']=traceback.format_exc()
    write(OUT/'client.json',report)
    return 0 if report['status']=='PASS_BEFORE_START_ONLY' else 1


def main():
    assert sorted(os.sched_getaffinity(0))==[0,8]
    OUT.mkdir(exist_ok=False)
    original=json.loads((SERIES/'pre-install.json').read_text())['files']
    assert all(sha(Path(v['path']))==v['sha256'] for v in original.values())
    files=[ROOT/'tools/carla/m7_nodrive/structured_json.hpp',ROOT/'tools/carla/m7_nodrive/M7NoDrivePort.cpp',
        SCRIPTS/'audit_structured_state_v1.py',SCRIPTS/'test_structured_state_v1.py',
        SCRIPTS/'profile_host_v1.py',SCRIPTS/'test_profile_host_v1.py',
        Path(__file__),SERIES/'nonfinite-guard-protocol.md',BUILD/'manifest.json']
    with tarfile.open(OUT/'changed-sources.tar.gz','w:gz') as tar:
        for path in files:tar.add(path,arcname=str(path.relative_to(ROOT)),recursive=False)
    freeze=dict(parent_archive_sha256=json.loads((SERIES/'sources.json').read_text())['archive_sha256'],
        files={str(path.relative_to(ROOT)):dict(bytes=path.stat().st_size,sha256=sha(path)) for path in files},
        archive_sha256=sha(OUT/'changed-sources.tar.gz'),candidate_manifest_sha256=sha(BUILD/'manifest.json'))
    write(OUT/'changed-sources.json',freeze)
    preflight=[];until=time.monotonic()+180
    while True:
        temperature=max(v/1000 for k,v in host().items() if '/temp' in k)
        preflight.append(dict(wall_ns=time.monotonic_ns(),max_cpu_c=temperature))
        if temperature<=70 or time.monotonic()>=until:break
        time.sleep(2)
    write(OUT/'preflight.json',dict(status='PASS' if temperature<=70 else 'NOT_RUN',samples=preflight))
    if temperature>70:return
    for port in (2200,2201,2202):
        with socket.socket() as guard:guard.bind(('127.0.0.1',port))
    with tarfile.open(SERIES/'normal-30s-01/run.tar.gz','r:gz') as tar:
        argv=json.load(tar.extractfile('server.json'))['argv']['owner']
    command=['taskset','-c','2,3,10,11',*argv];write(OUT/'command.json',command)
    env=dict(os.environ,OMP_WAIT_POLICY='PASSIVE',STRATADRIVE_M7_OWNER_KEY=secrets.token_hex(32))
    ini=Path(original['ini']['path']);original_ini=ini.read_bytes()
    install=['python3',str(ROOT/'tools/carla/m7_nodrive/build_endurance.py'),'--engine',str(ENGINE),
             '--source',str(CARLA),'--output',str(BUILD)]
    process=None;report=dict(status='FAIL',scope='no native START, physical receipt or image; guard check only')
    def hook():resource.setrlimit(resource.RLIMIT_CORE,(0,0));allow_shutdown_tracer()
    try:
        with (OUT/'install.log').open('w') as log:
            subprocess.run([*install,'--install'],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=30)
        with (OUT/'server.log').open('w') as log:
            process=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,
                start_new_session=True,preexec_fn=hook)
            report['readiness']=wait_ready(PYTHON,2200,OUT/'readiness.jsonl',env)
            with (OUT/'client.log').open('w') as client_log:
                completed=subprocess.run([str(PYTHON),str(Path(__file__)),'--client'],env=env,
                    stdout=client_log,stderr=subprocess.STDOUT,timeout=60)
            report['client_exit']=completed.returncode
            assert completed.returncode==0,'original UE guard self-check failed'
            report['status']='PASS_BEFORE_START_ONLY'
    except Exception:report['error']=traceback.format_exc()
    finally:
        try:
            if process:
                report['shutdown']=shutdown(process,OUT/'shutdown',diagnostics=True)
                if report['shutdown'].get('forced_stop') or report['shutdown']['server_exit']!=130:
                    report['status']='FAIL_SHUTDOWN'
        except Exception:
            report['shutdown_error']=traceback.format_exc();report['status']='FAIL_SHUTDOWN'
            if process and process.poll() is None:
                process.kill();process.wait(timeout=10)
        ini.write_bytes(original_ini)
        with (OUT/'restore.log').open('w') as log:
            restored=subprocess.run([*install,'--restore'],stdout=log,stderr=subprocess.STDOUT,timeout=30)
        report['restore_exit']=restored.returncode
        report['runtime']={name:dict(path=v['path'],sha256=sha(Path(v['path'])),restored=sha(Path(v['path']))==v['sha256'])
                           for name,v in original.items()}
        if restored.returncode or not all(v['restored'] for v in report['runtime'].values()):report['status']='FAIL_RESTORATION'
        write(OUT/'result.json',report)
    print(json.dumps(report))


if __name__=='__main__':
    if '--client' in sys.argv:raise SystemExit(client())
    main()

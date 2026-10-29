#!/usr/bin/env python3
"""Isolated stationary frame-throughput diagnostic, never a driving acceptance.

No actuation, synthetic feedback, StrataDrive binding, source build or retry of
an ambiguous tick. Raw timing stays in RAM until the measured loop is finished.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import traceback


def save(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n')


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def stats(values):
    values=sorted(values)
    return dict(count=len(values),mean_ms=sum(values)/len(values),
                p50_ms=values[math.ceil(.5*len(values))-1],
                p99_ms=values[math.ceil(.99*len(values))-1],max_ms=values[-1],
                over_10ms=sum(v>10 for v in values),over_20ms=sum(v>20 for v in values),
                over_30ms=sum(v>30 for v in values))


def probe(a):
    import carla
    report=dict(status='FAIL',scope='stationary diagnostic; no normal driving acceptance',
                backend=a.backend,cameras=a.cameras,render=a.render or a.cameras,
                warmup_ticks=a.warmup,ticks=a.ticks,actuation_calls=0)
    client=carla.Client('127.0.0.1',2300)
    world=original=ego=None;sensors=[];images={'rgb':[],'gt':[]};rows=[]
    fields=('synchronous_mode','fixed_delta_seconds','no_rendering_mode','substepping','max_substep_delta_time','max_substeps')
    try:
        deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            client.set_timeout(2)
            try:
                world=client.get_world()
                if world.get_snapshot().frame>0:break
            except RuntimeError:pass
            time.sleep(.2)
        else:raise TimeoutError('world readiness')
        client.set_timeout(10)
        print('world ready',flush=True)
        report['client_version']=client.get_client_version();report['server_version']=client.get_server_version()
        if report['client_version']!=report['server_version']:raise ValueError('version mismatch')
        if not world.get_map().name.endswith('/Town03_Opt'):raise ValueError('wrong map')
        if list(world.get_actors().filter('vehicle.*')):raise ValueError('world not isolated')
        if a.backend=='source':
            disabled=json.loads(client.m7_nodrive(json.dumps({'op':'describe'})))
            report['extension_describe']=disabled
            if disabled['reason']!='disabled' or disabled['locked']:raise ValueError('extension not disabled')
        original=world.get_settings();report['original_settings']={k:getattr(original,k) for k in fields}
        settings=world.get_settings()
        settings.synchronous_mode=True;settings.fixed_delta_seconds=.01
        settings.no_rendering_mode=not (a.render or a.cameras)
        settings.substepping=True;settings.max_substep_delta_time=.01;settings.max_substeps=10
        world.apply_settings(settings);world.tick(10)
        print('synchronous settings ready',flush=True)
        report['settings']={k:getattr(world.get_settings(),k) for k in fields}
        world.set_weather(carla.WeatherParameters.ClearNoon)
        blueprint=world.get_blueprint_library().find('vehicle.lincoln.mkz_2020')
        blueprint.set_attribute('role_name','m7_stationary_timing_diagnostic')
        spawn=world.get_map().get_spawn_points()[0]
        ego=world.spawn_actor(blueprint,spawn)
        print('ego spawned',flush=True)
        report['fixture']=dict(map=world.get_map().name,spawn_index=0,ego_id=ego.id,
                              opendrive_sha256=hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest(),
                              blueprint=ego.type_id,weather='ClearNoon',traffic=False,
                              vehicle_model='unmodified asset; no V1 or solver observer enabled')
        if a.cameras:
            for name,kind in (('rgb','sensor.camera.rgb'),('gt','sensor.camera.semantic_segmentation')):
                bp=world.get_blueprint_library().find(kind)
                for key,value in (('image_size_x','320'),('image_size_y','240'),('fov','90'),('sensor_tick','.05')):
                    bp.set_attribute(key,value)
                sensor=world.spawn_actor(bp,carla.Transform(carla.Location(x=1.6,z=1.7),carla.Rotation(pitch=-8)),attach_to=ego)
                sensors.append(sensor)
                def receive(img,name=name):
                    if len(images[name])<a.ticks+a.warmup+10:
                        images[name].append(dict(frame=img.frame,timestamp=img.timestamp,arrival_ns=time.monotonic_ns()))
                sensor.listen(receive)
        warmup=[]
        for i in range(a.warmup):
            begin=time.monotonic_ns();frame=world.tick(10);end=time.monotonic_ns()
            warmup.append(dict(frame=frame,begin_ns=begin,end_ns=end))
        save(a.output/'warmup.json',warmup)
        print('warmup complete',flush=True)
        previous=world.get_snapshot()
        report['start']=dict(frame=previous.frame,sim_seconds=previous.timestamp.elapsed_seconds,
                             platform_seconds=previous.timestamp.platform_timestamp)
        for i in range(a.ticks):
            begin=time.monotonic_ns();frame=world.tick(10);end=time.monotonic_ns()
            snap=world.get_snapshot();read_end=time.monotonic_ns()
            if frame!=previous.frame+1 or snap.frame!=frame:raise ValueError('frame skipped/mismatched')
            if abs(snap.timestamp.elapsed_seconds-previous.timestamp.elapsed_seconds-.01)>1e-6:
                raise ValueError('wrong original simulation step')
            state=snap.find(ego.id)
            if state is None:raise ValueError('ego snapshot missing')
            velocity=state.get_velocity()
            rows.append(dict(index=i,frame=frame,begin_ns=begin,end_ns=end,read_end_ns=read_end,
                             simulation_seconds=snap.timestamp.elapsed_seconds,
                             platform_seconds=snap.timestamp.platform_timestamp,
                             platform_gap_ms=(snap.timestamp.platform_timestamp-previous.timestamp.platform_timestamp)*1000,
                             velocity=[velocity.x,velocity.y,velocity.z]))
            previous=snap
        # Sensor delivery may lag physics. No extra tick to manufacture coverage.
        if sensors:time.sleep(1)
        print('measurement complete',flush=True)
        report['sensor_counts']={k:sum(report['start']['frame']<r['frame']<=rows[-1]['frame'] for r in v) for k,v in images.items()}
        report['tick_roundtrip']=stats([(r['end_ns']-r['begin_ns'])/1e6 for r in rows])
        report['server_platform_gap']=stats([r['platform_gap_ms'] for r in rows])
        report['client_arrival_gap']=stats([(r['end_ns']-p['end_ns'])/1e6 for p,r in zip(rows,rows[1:])])
        report['simulated_seconds']=rows[-1]['simulation_seconds']-report['start']['sim_seconds']
        report['wall_seconds']=(rows[-1]['read_end_ns']-rows[0]['begin_ns'])/1e9
        report['rtf']=report['simulated_seconds']/report['wall_seconds']
        report['status']='COMPLETE_DIAGNOSTIC'
    except Exception:report['error']=traceback.format_exc()
    finally:
        errors=[]
        for sensor in sensors:
            try:sensor.stop();sensor.destroy()
            except Exception as e:errors.append(str(e))
        if ego:
            try:report['ego_destroyed']=ego.destroy()
            except Exception as e:errors.append(str(e))
        if world and original:
            try:
                world.apply_settings(original)
                report['restored_settings']={k:getattr(world.get_settings(),k) for k in fields}
                report['remaining_owned_actors']=[v.id for v in world.get_actors() if v.id in [s.id for s in sensors]+([ego.id] if ego else [])]
            except Exception as e:errors.append(str(e))
        report['cleanup_errors']=errors
        if errors:report['status']='CLEANUP_FAIL'
        save(a.output/'samples.json',rows);save(a.output/'sensors.json',images);save(a.output/'result.json',report)
    print(json.dumps(report),flush=True)
    return int(report['status']!='COMPLETE_DIAGNOSTIC')


def supervise(a):
    for port in (2300,2301,2302):
        with socket.socket() as s:s.bind(('127.0.0.1',port))
    a.output.mkdir(parents=True,exist_ok=False)
    base=a.tools.resolve();report=dict(status='FAIL',backend=a.backend)
    if a.backend=='package':
        executable=base/'carla-0.9.16/server/CarlaUE4/Binaries/Linux/CarlaUE4-Linux-Shipping'
        python=base/'carla-0.9.16/venv-bundled/bin/python';argv=[str(executable)]
    else:
        executable=base/'UnrealEngine_4.26/Engine/Binaries/Linux/UE4Editor'
        python=base/'m7-source/m7-nodrive-venv/bin/python'
        argv=[str(executable),str(base/'m7-source/carla-0.9.16/Unreal/CarlaUE4/CarlaUE4.uproject')]
    argv+=['/Game/Carla/Maps/Town03_Opt','-game','-FixedSeed','-RenderOffScreen','-nosound','-unattended','-nosplash',
           '-carla-server','-carla-rpc-port=2300','-quality-level=Low',
           '-ini:EditorSettings:[/Script/UnrealEd.CrashReportsPrivacySettings]:bSendUnattendedBugReports=False',
           '-ini:Engine:[CrashReportClient]:bAgreeToCrashUpload=False,[CrashReportClient]:bImplicitSend=False',
           '-stdout','-FullStdOutLogOutput','-log']
    report.update(argv=argv,executable_sha256=sha(executable),probe_sha256=sha(Path(__file__)))
    if a.backend=='source':
        report['module_sha256']={str(p):sha(p) for p in (
            base/'UnrealEngine_4.26/Engine/Plugins/Runtime/PhysXVehicles/Binaries/Linux/libUE4Editor-PhysXVehicles.so',
            base/'m7-source/carla-0.9.16/Unreal/CarlaUE4/Plugins/Carla/Binaries/Linux/libUE4Editor-Carla.so')}
    env=dict(os.environ)
    icd=Path('/usr/share/vulkan/icd.d/nvidia_icd.json')
    if icd.exists():env['VK_ICD_FILENAMES']=str(icd)
    report['vulkan_icd']=env.get('VK_ICD_FILENAMES')
    server=None
    try:
        with (a.output/'server.log').open('w') as log:
            server=subprocess.Popen(argv,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        report['pid']=server.pid
        deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            if server.poll() is not None:raise RuntimeError('server exited before port readiness')
            try:
                with socket.create_connection(('127.0.0.1',2300),timeout=.5):break
            except OSError:time.sleep(.2)
        else:raise TimeoutError('port readiness')
        command=[str(python),str(Path(__file__).resolve()),'--probe','--backend',a.backend,
                 '--output',str(a.output.resolve()),'--ticks',str(a.ticks),'--warmup',str(a.warmup)]
        if a.cameras:command.append('--cameras')
        if a.render:command.append('--render')
        report['probe_argv']=command
        with (a.output/'client.log').open('w') as log:
            completed=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=300)
        report['probe_exit']=completed.returncode
        report['status']='COMPLETE_DIAGNOSTIC' if completed.returncode==0 else 'PROBE_FAIL'
    except Exception:report['error']=traceback.format_exc()
    finally:
        if server:
            if server.poll() is None:
                os.killpg(server.pid,signal.SIGINT)
                try:server.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    report['forced_stop']='SIGKILL after 30s';os.killpg(server.pid,signal.SIGKILL);server.wait(timeout=10)
            report['server_exit']=server.returncode
        save(a.output/'server.json',report)
    print(json.dumps(dict(output=str(a.output),status=report['status'],server_exit=report.get('server_exit'))),flush=True)
    return int(report['status']!='COMPLETE_DIAGNOSTIC' or 'forced_stop' in report)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backend',choices=('package','source'),required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--tools',type=Path,default=Path('/d/shin/stratadrive-tools'))
    p.add_argument('--ticks',type=int,default=1000);p.add_argument('--warmup',type=int,default=150)
    p.add_argument('--cameras',action='store_true');p.add_argument('--render',action='store_true')
    p.add_argument('--probe',action='store_true',help=argparse.SUPPRESS)
    a=p.parse_args()
    if not 100<=a.ticks<=2000 or not 0<=a.warmup<=300:p.error('bounded diagnostic only')
    return probe(a) if a.probe else supervise(a)


if __name__=='__main__':raise SystemExit(main())

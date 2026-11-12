#!/usr/bin/env python3
"""Finite actual-native CARLA shadow IPC attempt; no perception authority."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import time
import traceback
import sys
import carla
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "carla"))
from m7_1p_bridge import require
from control_shadow_capture_v1 import Capture
from owner_split_profile_v1 import PROFILES, validate_client


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--native',type=Path,required=True)
    p.add_argument('--model',type=Path,required=True)
    p.add_argument('--scenario',type=Path,required=True)
    p.add_argument('--ticks',type=int,default=400)
    p.add_argument('--fault',choices=('none','wall-gap','protection'),default='none')
    p.add_argument('--cameras',action='store_true')
    p.add_argument('--camera-absent-control',action='store_true')
    p.add_argument('--execution-profile',choices=PROFILES,default='shadow10ms')
    p.add_argument('--warmup-ticks',type=int,choices=(0,150),default=0)
    p.add_argument('--step-ms',type=int,choices=(5,10),default=10)
    p.add_argument('--hv-dependency-ms',type=int,choices=(30,50),default=30)
    for name in ("detector", "models", "library"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--wall-clock", type=int, required=True)
    a=p.parse_args()
    try:validate_client(a)
    except ValueError as error:p.error(str(error))
    a.output.mkdir(parents=True,exist_ok=False)
    report={'status':'FAIL','scope':'dual-clock experiment; acceptance requires separate audit','fault':a.fault,'model_step_ns':a.step_ms*1000000}
    report['perception_authority']='shadow only; no torque/planner/protection writes'
    report['world_tick_owner']='existing native server wall owner; no client ticks after bind'
    report['hv_dependency_ns']=a.hv_dependency_ms*1000000
    report['camera_condition']='absent' if a.camera_absent_control else '2k'
    report['execution_profile']=a.execution_profile
    rows=[];events=[];waits=[];process=actor=world=original=None;bound=False;session=run=None
    capture=Capture(a)
    c=carla.Client('127.0.0.1',2200);c.set_timeout(10)
    def rpc(op,**kw):
        request=dict(op=op,**kw,owner_key=os.environ['STRATADRIVE_M7_OWNER_KEY'])
        if op not in ('bind','describe'):request.update(session=session,run=run)
        value=json.loads(c.m7_nodrive(json.dumps(request)))
        events.append({'op':op,'wall_ns':time.monotonic_ns(),'response':value})
        return value
    def native(line):
        require(process.poll() is None,'native exited')
        process.stdin.write(line+'\n');process.stdin.flush()
        require(select.select([process.stdout],[],[],2)[0],'native IO timeout')
        value=process.stdout.readline();require(bool(value),'native EOF')
        return json.loads(value)
    try:
        report['versions']=[c.get_client_version(),c.get_server_version()]
        require(report['versions']==['294096e-dirty']*2,'versions')
        world=c.get_world();require(world.get_map().name.endswith('/Town03_Opt'),'map')
        require(not any(list(world.get_actors().filter(k)) for k in ('vehicle.*','sensor.*','walker.*')),'dedicated world')
        original=world.get_settings();settings=world.get_settings()
        settings.synchronous_mode=True;settings.fixed_delta_seconds=a.step_ms/1000;settings.no_rendering_mode=not a.cameras
        settings.substepping=True;settings.max_substep_delta_time=.01;settings.max_substeps=10
        report['rendering_enabled']=not settings.no_rendering_mode
        world.apply_settings(settings);world.tick()
        bp=world.get_blueprint_library().find('vehicle.lincoln.mkz_2020');bp.set_attribute('role_name','m7_wall_actual')
        actor=world.spawn_actor(bp,world.get_map().get_spawn_points()[0]);world.set_weather(carla.WeatherParameters.ClearNoon)
        if a.warmup_ticks:
            # Passive pre-bind settling is a diagnostic, never native driving.
            # The NoDrive component does not supply stock VehicleControl state.
            warm=[]
            for _ in range(a.warmup_ticks):
                frame=world.tick();snapshot=world.get_snapshot();state=snapshot.find(actor.id)
                v=state.get_velocity();warm.append({'frame':frame,'time':snapshot.timestamp.elapsed_seconds,'velocity':[v.x,v.y,v.z]})
            report['pre_init_warmup']={'ticks':a.warmup_ticks,'control_writes':0,'native_session_started':False,'observations':warm}
        if capture:capture.attach(world,actor,carla)
        binding=rpc('bind',actor=str(actor.id),application='42',model_sha256=hashlib.sha256(a.model.read_bytes()).hexdigest())
        require(binding['ok'],'bind');bound=True;session=binding['session'];run=binding['run'];report['binding']=binding
        model=int(binding['logical_begin_ns'])
        signal=(a.output/'wall-signal').resolve()
        stderr=(a.output/'native.stderr').open('w')
        process=subprocess.Popen(['chrt','-f','18',str(a.native.resolve()),str(signal),str((a.output/'native').resolve()),str(a.scenario.resolve()),str(a.step_ms),str(a.hv_dependency_ms), '--perception-shadow', f'{capture.rx.fileno()}:{world.id}:{a.wall_clock}'],
            pass_fds=(capture.rx.fileno(),), stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=stderr,text=True)
        capture.rx.close()
        capture.start_publisher()
        started=native(f'START {actor.id} {model} {session} {binding["physics"]["generation"]} {run}');report['native_initial']=started
        require(rpc('wall_start',initial=str(started['initial']),signal_path=str(signal),limit=str(a.ticks))['ok'],'same host wall start')
        report['wall_clock_contract']='host CLOCK_MONOTONIC acquisition; separate original CARLA model dt; no offset conversion'
        fault_sent=False;writers_checked=False;deadline=time.monotonic()+18
        last_progress=time.monotonic();last_count=0
        while time.monotonic()<deadline:
            status=rpc('wall_status');count=int(status['wall_frames'])
            r=native('GET');report['last_native']=r
            events.append({'op':'native_get','wall_ns':time.monotonic_ns(),'response':r})
            if a.execution_profile=='owner5ms' and int(status.get('wall_normal_intervals','0'))>=10 and not writers_checked:
                checks={'begin_ns':time.monotonic_ns(),'normal_before':int(status['wall_normal_intervals'])}
                blocked=c.apply_batch_sync([carla.command.ApplyVehicleControl(actor.id,carla.VehicleControl(throttle=1))],False)
                checks['batch_denied']=len(blocked)==1 and blocked[0].has_error() and 'M7 exclusive zero-probe owner' in blocked[0].error
                try:world.tick(.05);checks['tick_denied']=False
                except RuntimeError as error:checks['tick_denied']='M7 exclusive zero-probe owner' in str(error)
                denied=rpc('stage_native',frame=str(int(status['frame'])+1),native={})
                checks['external_stage_denied']=not denied['ok'] and denied['reason']=='wall_single_tick_owner'
                checks['end_ns']=time.monotonic_ns();report['writer_checks']=checks
                require(all(checks[k] for k in ('batch_denied','tick_denied','external_stage_denied')),'active wall single writer')
                writers_checked=True
            if count!=last_count:last_progress=time.monotonic();last_count=count
            if count>=a.ticks and not status['awaiting_ev_settlement']:break
            if capture.snapshot()['errors']:
                raise RuntimeError('shadow observer/recording error; ending finite trial')
            if status['latched']:raise RuntimeError('server latch '+status.get('latched_reason',status['reason']))
            if time.monotonic()-last_progress>.7:
                raise RuntimeError('no eligible physical tick: '+status.get('wall_wait',''))
            time.sleep(.005)
        else:raise RuntimeError('finite diagnostic execution horizon exhausted')
        report.update(status='EXECUTED_REQUIRES_AUDIT',normal=int(status['wall_normal_intervals']),
            protected=int(status['wall_protected_intervals']),settlements=count,final_server=status)
    except Exception:report['error']=traceback.format_exc()
    finally:
        if process:
            try:
                if process.poll() is None:
                    process.stdin.write('STOP\n');process.stdin.flush()
                process.stdin.close();report['native_exit']=process.wait(timeout=5)
            except Exception:
                process.kill();process.wait();report['native_forced_stop']=True
            stderr.close()
        if capture:
            try:capture.stop()
            except Exception:report['camera_cleanup_error']=traceback.format_exc()
        if bound:
            try:
                final=rpc('describe');count=int(final['wall_frames']);report['completed_physics']=count
                ingress=[]
                for index in range(int(final.get('wall_ingress_count','0'))):
                    reply=rpc('wall_ingress',index=str(index));require(reply['ok'],'complete CAN ingress history')
                    ingress.append(reply)
                (a.output/'ingress.json').write_text(json.dumps(ingress,indent=2)+'\n')
                previous=binding['physics']
                for index in range(count):
                    reply=rpc('wall_trace',index=str(index));require(reply['ok'],'complete receipt history')
                    receipt=reply['receipt'];raw=rpc('solver_trace',ticket=receipt['ticket'])
                    require(raw['ok'],'complete solver history')
                    rows.append({'index':index,'frame':int(receipt['frame'])-1,'physics':previous,
                        'receipt':receipt,'raw_solver':raw,'settlement':reply.get('settlement')})
                    previous=receipt['physics']
                before=rpc('describe')['frame'];paused=rpc('pause');time.sleep(.05);after=rpc('describe')
                report['pause']={'stable':before==after['frame'],'clear':after['physics']['inputs_zero'],'latched':paused['latched']}
                report['reset']=rpc('reset');report['close']=rpc('close');bound=False;actor=None
            except Exception:report['cleanup_error']=traceback.format_exc()
        if capture:
            try:capture.destroy(ownership_released=not bound)
            except Exception:report['camera_cleanup_error']=traceback.format_exc()
            (a.output/'sensors.json').write_text(json.dumps(capture.snapshot(),indent=2)+'\n')
        if any(report.get(k) for k in ('cleanup_error','camera_cleanup_error','native_forced_stop')) or capture.snapshot()['cleanup_errors']:
            report['status']='FAIL'
        if world and original and not bound:
            if actor:actor.destroy()
            world.apply_settings(original)
        report['receipts']=sum('receipt' in r for r in rows)
        (a.output/'native-waits.json').write_text(json.dumps(waits,indent=2)+'\n')
        (a.output/'trace.jsonl').write_text(''.join(json.dumps(r,separators=(',',':'))+'\n' for r in rows))
        (a.output/'events.json').write_text(json.dumps(events,indent=2)+'\n')
        (a.output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    return 0 if report['status']=='EXECUTED_REQUIRES_AUDIT' else 1
if __name__=='__main__':raise SystemExit(main())

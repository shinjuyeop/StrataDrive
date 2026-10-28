#!/usr/bin/env python3
"""Explicit dual-clock CARLA experiment. A failed attempt is never driving acceptance."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import select
import subprocess
import time
import traceback
import carla
from m7_1k_server_probe import FIELDS
from m7_1p_bridge import require, SOURCE
from m7_sensor_capture import Capture
from audit_m7_1r_work import f32


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--native',type=Path,required=True)
    p.add_argument('--model',type=Path,required=True)
    p.add_argument('--scenario',type=Path,required=True)
    p.add_argument('--ticks',type=int,default=400)
    p.add_argument('--fault',choices=('none','wall-gap','protection','snapshot','work-missing'),default='none')
    p.add_argument('--cameras',action='store_true')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    report={'status':'FAIL','scope':'dual-clock experiment; acceptance requires separate audit','fault':a.fault}
    rows=[];events=[];process=actor=world=original=None;bound=False;session=run=None
    capture=Capture(a.output) if a.cameras else None
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
    def get(energy=None,ready=False):
        limit=time.monotonic()+.5
        while time.monotonic()<limit:
            r=native('GET')
            if (energy is None or r.get('energy_end')==energy) and (not ready or r['ready']):return r
            report['last_native']=r
            time.sleep(.0005)
        raise RuntimeError('no eligible fresh Actual/settlement within diagnostic wait; budgets unchanged')
    try:
        report['versions']=[c.get_client_version(),c.get_server_version()]
        require(report['versions']==['294096e-dirty']*2,'versions')
        world=c.get_world();require(world.get_map().name.endswith('/Town03_Opt'),'map')
        require(not list(world.get_actors().filter('vehicle.*')),'dedicated world')
        original=world.get_settings();settings=world.get_settings()
        settings.synchronous_mode=True;settings.fixed_delta_seconds=.01;settings.no_rendering_mode=not a.cameras
        settings.substepping=True;settings.max_substep_delta_time=.01;settings.max_substeps=10
        world.apply_settings(settings);world.tick()
        bp=world.get_blueprint_library().find('vehicle.lincoln.mkz_2020');bp.set_attribute('role_name','m7_wall_actual')
        actor=world.spawn_actor(bp,world.get_map().get_spawn_points()[0]);world.set_weather(carla.WeatherParameters.ClearNoon)
        if capture:capture.attach(world,actor,carla)
        binding=rpc('bind',actor=str(actor.id),application='42',model_sha256=hashlib.sha256(a.model.read_bytes()).hexdigest())
        require(binding['ok'],'bind');bound=True;session=binding['session'];run=binding['run'];report['binding']=binding
        model=int(binding['logical_begin_ns']);frame=int(binding['frame']);ph=binding['physics']
        signal=(a.output/'wall-signal').resolve()
        stderr=(a.output/'native.stderr').open('w')
        process=subprocess.Popen(['chrt','-f','18',str(a.native.resolve()),str(signal),str((a.output/'native').resolve()),str(a.scenario.resolve())],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=stderr,text=True)
        started=native(f'START {actor.id} {model}');report['native_initial']=started
        require(rpc('wall_start',initial=str(started['initial']),signal_path=str(signal))['ok'],'same host wall start')
        normal=protected=settlements=0;fault_sent=False
        for i in range(a.ticks):
            row={'index':i,'frame':frame,'physics':ph,'wall_begin_ns':time.monotonic_ns()};rows.append(row)
            if normal>=50 and a.fault!='none' and not fault_sent:
                row['fault_ns']=time.monotonic_ns();fault_sent=True
                if a.fault=='protection':native('PROTECT')
                elif a.fault=='wall-gap':time.sleep(.1)
                elif a.fault=='snapshot':native('PROTECT')
                elif a.fault=='work-missing':native('PROTECT')
            r=get(ready=True);row['native']=r
            proof=dict(r['native'])
            for old,new in [('observed','observed_ns'),('enable','enable_ns'),('protection_since','protection_since_ns')]:proof[new]=proof.pop(old)
            for k in ('service_mask','credit_mask','release_mask','protection_selected_mask'):proof[k]=str(proof[k])
            stage=rpc('stage_native',frame=str(frame+1),native=proof);row['stage']=stage
            require(stage['ok'],'server native admission: '+stage['reason'])
            native('COMMIT')
            queued=rpc('advance',ticket=stage['ticket']);require(queued['ok'],'advance')
            deadline=time.monotonic()+1;receipt=None
            while time.monotonic()<deadline:
                response=rpc('receipt');require(not response['latched'],'server latch '+response['reason'])
                if response.get('receipt',{}).get('ticket')==stage['ticket']:receipt=response['receipt'];break
                time.sleep(.0005)
            require(receipt is not None,'no completed physics; never replay ambiguous advance')
            row['receipt']=receipt
            require(int(receipt['frame'])==frame+1 and int(receipt['logical_begin_ns'])==model,'frame/model binding')
            require(receipt['original_actual']['native']==proof and receipt['inputs_cleared_after_physics'],'Actual identity/single writer')
            work=receipt['solver_work'];actual=receipt['original_actual']['admitted_actual'];newph=receipt['physics']
            require(work['valid'] and receipt['interval_work_valid'] and work['abi']==2,'complete work')
            require(work['count']==(0 if work['sleeping'] else 320),'all solver substeps')
            require(all(w['solver_omega_source']==SOURCE for w in newph['wheels']),'wheel source identity')
            begin=int(receipt['physics_acquisition_begin_ns']);end=int(receipt['physics_acquisition_end_ns']);applied=int(receipt['wall_applied_ns'])
            require(started['initial']<=applied<=begin<=end<=time.monotonic_ns(),'same host acquisition bracket')
            oldest=int(actual['oldest_actuator_ns']) or applied
            means=work['rear_mean_rad_s'] if not work['sleeping'] else [0.]*320
            values=[frame+1,model,int(receipt['work_end_ns']),applied,begin,end,oldest,r['coil_source'],*r['coils'],
                actual['torque_nm'],f32(f32(.01)*f32(1/320)),int(work['sleeping']),
                (ph['wheels'][2]['solver_omega_rad_s']+ph['wheels'][3]['solver_omega_rad_s'])/2,
                *[w['solver_omega_rad_s'] for w in newph['wheels']],*means]
            packet='FRAME '+' '.join(str(v) if isinstance(v,int) else format(v,'.17g') for v in values)
            row['work_input']=packet;native(packet)
            settled=get(energy=int(receipt['work_end_ns']));row['settled']=settled
            ack=rpc('settle_work',ticket=receipt['ticket'],frame=receipt['frame'],end_ns=receipt['work_end_ns'],
                basis='OBSERVED_SOLVER_WORK_SINGLE_EV',total_mechanical_j=settled['settlement']['mechanical_j'],balance_j=settled['settlement']['balance_j'])
            require(ack['ok'],'single EV settlement');settlements+=1
            normal+=bool(actual['normal']);protected+=bool(actual['protection'])
            model=int(receipt['work_end_ns']);frame+=1;ph=newph
            snapshot=world.get_snapshot()
            row['vehicle_state']={'frame':snapshot.frame,'timestamp':snapshot.timestamp.elapsed_seconds}
            require(snapshot.frame==frame,'current state frame')
            if capture:require(not capture.snapshot()['errors'],'camera missing')
        report.update(status='EXECUTED_REQUIRES_AUDIT',normal=normal,protected=protected,settlements=settlements)
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
        if bound:
            try:
                for row in rows:
                    receipt=row.get('receipt')
                    if receipt:row['raw_solver']=rpc('solver_trace',ticket=receipt['ticket'])
                before=rpc('describe')['frame'];paused=rpc('pause');time.sleep(.05);after=rpc('describe')
                report['pause']={'stable':before==after['frame'],'clear':after['physics']['inputs_zero'],'latched':paused['latched']}
                report['reset']=rpc('reset');report['close']=rpc('close');bound=False;actor=None
            except Exception:report['cleanup_error']=traceback.format_exc()
        if capture:
            try:capture.stop();capture.destroy()
            except Exception:report['camera_cleanup_error']=traceback.format_exc()
            (a.output/'sensors.json').write_text(json.dumps(capture.snapshot(),indent=2)+'\n')
        if world and original and not bound:
            if actor:actor.destroy()
            world.apply_settings(original)
        report['receipts']=sum('receipt' in r for r in rows)
        (a.output/'trace.jsonl').write_text(''.join(json.dumps(r,separators=(',',':'))+'\n' for r in rows))
        (a.output/'events.json').write_text(json.dumps(events,indent=2)+'\n')
        (a.output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    return 0 if report['status']=='EXECUTED_REQUIRES_AUDIT' else 1
if __name__=='__main__':raise SystemExit(main())

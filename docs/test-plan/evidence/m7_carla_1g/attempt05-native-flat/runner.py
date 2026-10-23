#!/usr/bin/env python3
"""Owned CARLA telemetry / native sensor-shadow probe. No vehicle actuation API."""
import argparse
import gc
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import traceback
import carla


def save(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False)+'\n')


def require(ok, why):
    if not ok:
        raise RuntimeError(why)


def xyz(v):
    return [v.x, v.y, v.z]


def capture(args):
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    result = dict(status='FAIL', mode='wheel-sensor-shadow', driving=False,
                  apply_calls=0, fixture=args.fixture, ticks_planned=400,
                  runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), cleanup={},injections=[])
    client = carla.Client('127.0.0.1', 2000)
    client.set_timeout(15)
    world = client.get_world()
    original = world.get_settings()
    actors = []
    native = None
    try:
        result['versions'] = [client.get_client_version(), client.get_server_version()]
        require(result['versions'] == ['0.9.16', '0.9.16'], 'version mismatch')
        require(not list(world.get_actors().filter('vehicle.*')) and not list(world.get_actors().filter('sensor.*')), 'dedicated world not empty')
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .01
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        settings.no_rendering_mode = False
        world.apply_settings(settings)
        observed = world.get_settings()
        require(observed.synchronous_mode and abs(observed.fixed_delta_seconds-.01)<1e-8, 'settings readback')
        m = world.get_map()
        result['map'] = m.name
        require(args.map in m.name, 'startup map mismatch')
        if args.fixture == 'slope':
            # Offline XODR survey: forward downhill, no artificial force/velocity.
            wp = m.get_waypoint_xodr(73, 1, 30)
            require(wp is not None, 'ramp missing')
            pose = wp.transform
            pose.location.z += .35
        else:
            pose = m.get_spawn_points()[0]
        blueprint = world.get_blueprint_library().find('vehicle.lincoln.mkz_2020')
        ego = world.spawn_actor(blueprint, pose)
        actors.append(ego)
        # Default PhysX enabled; no apply_control, autopilot, physics overrides,
        # velocity/force injection, teleport, get_control-as-Actual, or cameras.
        result['ego'] = dict(id=ego.id, blueprint=blueprint.id, spawn=str(pose), physics=True)
        result['vehicle_methods'] = sorted(x for x in dir(ego) if not x.startswith('_'))
        result['physics_readback'] = str(ego.get_physics_control())
        result['radii_cm'] = [w.radius for w in ego.get_physics_control().wheels]
        world.tick(15)  # initialize wheel query states before telemetry RPC
        if args.native:
            native = subprocess.Popen([str(args.native), '--wheel-shadow', '1', '42', '7', str(ego.id)],
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=(out/'native.stderr').open('w'), text=True, bufsize=1)
            result['native_sha256'] = hashlib.sha256(args.native.read_bytes()).hexdigest()
        rows = []
        with (out/'frames.jsonl').open('w') as f:
            for index in range(result['ticks_planned']):
                if native and index==200:
                    paused=world.get_snapshot()
                    pause_begin=time.monotonic_ns()
                    time.sleep(.25)
                    resumed=world.get_snapshot()
                    require(paused.frame==resumed.frame and paused.timestamp.elapsed_seconds==resumed.timestamp.elapsed_seconds,'pause changed logical time')
                    result['injections'].append(dict(kind='pause',index=index,wall_begin_ns=pause_begin,
                        wall_end_ns=time.monotonic_ns(),frame=paused.frame,sim_s=paused.timestamp.elapsed_seconds))
                begin = time.monotonic_ns()
                before = world.get_snapshot()
                telemetry = ego.get_telemetry_data()
                repeat = ego.get_telemetry_data()
                after = world.get_snapshot()
                require(before.frame == after.frame and before.timestamp.elapsed_seconds == after.timestamp.elapsed_seconds, 'tick during telemetry')
                fields = ['omega', 'torque', 'tire_load', 'long_force', 'long_slip', 'lat_slip']
                raw = [{key: getattr(w, key) for key in fields} for w in telemetry.wheels]
                nonfinite = [(i,k) for i,w in enumerate(raw) for k,v in w.items() if not math.isfinite(v)]
                require(len(raw) == 4 and all(math.isfinite(w['omega']) for w in raw), 'invalid wheel measurement')
                require([w['omega'] for w in raw] == [w.omega for w in repeat.wheels], 'omega changed without tick')
                snap = before.find(ego.id)
                require(snap is not None, 'ego missing from snapshot')
                t = snap.get_transform()
                vel = snap.get_velocity()
                forward = t.get_forward_vector()
                row = dict(index=index, frame=before.frame, sim_s=before.timestamp.elapsed_seconds,
                           delta_s=before.timestamp.delta_seconds, actor=ego.id, run=1, application=42,
                           plant=7, clock=0x4D3746554E435449, bracket_after_frame=after.frame,
                           begin_ns=begin, telemetry_end_ns=time.monotonic_ns(), xyz=xyz(t.location),
                           velocity=xyz(vel), forward=xyz(forward), forward_m_s=vel.dot(forward),
                           wheel=[{k:v if math.isfinite(v) else None for k,v in w.items()} for w in raw],
                           invalid_debug_fields=nonfinite, repeated_omega_equal=True)
                if native:
                    import select
                    line = 'WHEEL {} {} {} {} {} {:.17g} {:.17g} {} {} {} {}\n'.format(
                        1,42,7,0x4D3746554E435449,before.frame,before.timestamp.elapsed_seconds,
                        before.timestamp.delta_seconds,ego.id,before.frame,
                        round(before.timestamp.elapsed_seconds*1e9),' '.join(format(w['omega'],'.17g') for w in raw))
                    native.stdin.write(line)
                    native.stdin.flush()
                    require(select.select([native.stdout], [], [], 10)[0], 'native timeout')
                    row['native'] = json.loads(native.stdout.readline())
                    row['request'] = line.strip()
                rows.append(row)
                f.write(json.dumps(row, allow_nan=False)+'\n')
                f.flush()
                if native and row['native'].get('status') != 'WHEEL_SHADOW_BARRIER':
                    raise RuntimeError('native rejected; no next tick')
                require(not native or row['native']['next_frame'] == before.frame+1, 'native frame permission')
                frame = world.tick(15)
                next_snap = world.get_snapshot()
                require(frame == next_snap.frame == before.frame+1, 'single tick owner violation')
                require(abs(next_snap.timestamp.elapsed_seconds-before.timestamp.elapsed_seconds-.01)<1e-6, 'tick delta')
        if native:
            before_fault=world.get_snapshot()
            native.stdin.write(line)
            native.stdin.flush()
            require(select.select([native.stdout],[],[],10)[0],'negative native timeout')
            rejected=json.loads(native.stdout.readline())
            after_fault=world.get_snapshot()
            result['negative']=dict(kind='duplicate-wheel-observation',reply=rejected,
                before_frame=before_fault.frame,after_frame=after_fault.frame)
            require(rejected['status']=='FAIL' and rejected['next_frame'] is None and before_fault.frame==after_fault.frame,'duplicate did not stop tick')
            require(native.wait(timeout=5)==1,'negative native exit')
        result['ticks_completed'] = len(rows)
        result['max_abs_omega_rad_s'] = max(abs(w['omega']) for r in rows for w in r['wheel'])
        result['max_forward_m_s'] = max(r['forward_m_s'] for r in rows)
        result['end_minus_start_xyz'] = [rows[-1]['xyz'][i]-rows[0]['xyz'][i] for i in range(3)]
        result['invalid_debug_field_count'] = sum(len(r['invalid_debug_fields']) for r in rows)
        result['status'] = 'OBSERVED'
    except Exception as e:
        result['error'] = str(e)
        result['traceback'] = traceback.format_exc()
    finally:
        if native:
            if native.poll() is None:
                native.stdin.close()
            try:
                result['native_exit'] = native.wait(timeout=5)
            except subprocess.TimeoutExpired:
                native.terminate()
                result['native_exit'] = native.wait(timeout=5)
        for actor in reversed(actors):
            try:
                require(actor.destroy(), 'destroy returned false')
            except Exception as e:
                result['cleanup'].setdefault('errors', []).append(str(e))
        try:
            world.apply_settings(original)
            check = world.get_settings()
            result['cleanup']['settings_restored'] = check.synchronous_mode == original.synchronous_mode and check.fixed_delta_seconds == original.fixed_delta_seconds
            fresh = carla.Client('127.0.0.1',2000)
            fresh.set_timeout(10)
            ids = {a.id for a in fresh.get_world().get_actors()}
            result['cleanup']['remaining_owned'] = [a.id for a in actors if a.id in ids]
        except Exception as e:
            result['cleanup'].setdefault('errors', []).append(str(e))
        if result['cleanup'].get('errors') or result['cleanup'].get('remaining_owned') or not result['cleanup'].get('settings_restored'):
            result['status'] = 'FAIL'
        save(out/'summary.json',result)
    return 0 if result['status']=='OBSERVED' else 1


def launch(args):
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output/'runner.py').write_bytes(Path(__file__).read_bytes())
    require(not subprocess.check_output(['ss','-H','-ltn','sport = :2000 or sport = :2001 or sport = :2002'],text=True), 'ports in use')
    spec = importlib.util.spec_from_file_location('helper',Path(__file__).with_name('run_m7_1e.py'))
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    record = dict(status='FAIL',readiness_errors=[])
    argv = ['./CarlaUE4.sh','/Game/Carla/Maps/'+args.map,'-RenderOffScreen','-quality-level=Low','-nosound',
            '-carla-rpc-port=2000','-vulkan','-stdout','-FullStdOutLogOutput','-log']
    record['server_command'] = argv
    with (args.output/'server.log').open('w') as log:
        proc = subprocess.Popen(argv,cwd=args.server,env=dict(os.environ,VK_ICD_FILENAMES='/usr/share/vulkan/icd.d/nvidia_icd.json'),
                                stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=helper.no_core)
        try:
            deadline=time.monotonic()+120
            while time.monotonic()<deadline and proc.poll() is None:
                try:
                    client=carla.Client('127.0.0.1',2000)
                    client.set_timeout(5)
                    world=client.get_world()
                    break
                except Exception as e:
                    record['readiness_errors'].append(str(e))
                    time.sleep(1)
            else:
                raise RuntimeError('readiness deadline')
            shipping=[p for p in helper.descendants(proc.pid) if b'CarlaUE4-Linux-Shipping' in Path(f'/proc/{p}/cmdline').read_bytes()]
            require(len(shipping)==1,'owned server identity')
            record['shipping_pid']=shipping[0]
            del world,client
            gc.collect()
            if args.map != 'Town10HD_Opt':
                # Packaged startup map argument was ignored (attempt01). Use a
                # fresh client process with no cached old World object.
                loader = [sys.executable, '-I', '-c',
                          'import carla; c=carla.Client("127.0.0.1",2000); c.set_timeout(90); '
                          'w=c.load_world("'+args.map+'"); print(w.get_map().name)']
                loaded = subprocess.run(loader,capture_output=True,text=True,timeout=100)
                record['map_load'] = dict(exit=loaded.returncode,stdout=loaded.stdout,stderr=loaded.stderr)
                require(loaded.returncode==0,'fresh-client map load failed')
            command=[sys.executable,'-I',str(Path(__file__).resolve()),'--capture','--fixture',args.fixture,
                     '--map',args.map,'--output',str(args.output/'capture')]
            if args.native:
                command += ['--native',str(args.native)]
            record['client_command']=command
            with (args.output/'client.log').open('w') as client_log:
                result=subprocess.run(command,stdout=client_log,stderr=subprocess.STDOUT,timeout=180)
                record['client_exit']=result.returncode
            record['status']='OBSERVED'
        except Exception as e:
            record['error']=str(e)
        finally:
            if proc.poll() is None:
                if 'shipping_pid' in record:
                    os.kill(record['shipping_pid'],signal.SIGTERM)
                else:
                    os.killpg(proc.pid,signal.SIGTERM)
                try:
                    record['server_exit']=proc.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    record['forced_kill']=True
                    os.killpg(proc.pid,signal.SIGKILL)
                    record['server_exit']=proc.wait(timeout=5)
            else:
                record['server_exit']=proc.returncode
            record['remaining_listeners']=subprocess.check_output(['ss','-H','-ltnp','sport = :2000 or sport = :2001 or sport = :2002'],text=True)
            save(args.output/'process.json',record)
    return 0 if record.get('client_exit')==0 else 1


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--server',type=Path)
    p.add_argument('--native',type=Path)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--map',default='Town10HD_Opt',choices=['Town10HD_Opt','Town03_Opt'])
    p.add_argument('--fixture',choices=['flat','slope'],default='flat')
    p.add_argument('--capture',action='store_true')
    args=p.parse_args()
    args.output=args.output.resolve()
    if args.native:
        args.native=args.native.resolve()
    if args.capture:
        return capture(args)
    require(args.server is not None,'--server required')
    args.server=args.server.resolve()
    return launch(args)


if __name__=='__main__':
    raise SystemExit(main())

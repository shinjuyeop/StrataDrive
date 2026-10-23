#!/usr/bin/env python3
"""Non-driving timing cost separation and read-only wheel/clock probes."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import faulthandler
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import time
import traceback
import carla

HELPER = Path(__file__).with_name('m7_1b_capture.py')
spec = importlib.util.spec_from_file_location('capture_helpers', HELPER)
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
MODES = ['no_render_state', 'render_state', 'camera_metadata', 'camera_audit']
PROFILE = {'dt_s': .01, 'camera_s': .05, 'startup': 100, 'main': 400, 'drain': 100,
           'orders': [MODES, list(reversed(MODES))], 'queue_capacity': 64,
           'camera': [800,600,90], 'static_ego': True, 'normal_driving': False,
           'actuation_calls': 0, 'wheel_probe': 'unpowered physics on; read-only RPC',
           'clock_mapping': 'diagnostic intervals only; not runtime conversion'}


def tick(world, previous):
    begin = time.monotonic_ns()
    f = world.tick(10)
    snap = world.get_snapshot()
    end = time.monotonic_ns()
    h.require(f == snap.frame == previous.frame+1, 'unexpected tick owner/frame')
    h.require(abs(snap.timestamp.elapsed_seconds-previous.timestamp.elapsed_seconds-.01) < 1e-6, 'sim step')
    return snap, {'frame': f, 'sim_s': snap.timestamp.elapsed_seconds,
                  'platform_s': snap.timestamp.platform_timestamp,
                  'begin_ns': begin, 'snapshot_end_ns': end,
                  'delta_s': snap.timestamp.delta_seconds}


def case(world, out, mode):
    out.mkdir()
    r = {'status': 'FAIL', 'mode': mode, 'profile': PROFILE, 'events': [], 'sensors': {}}
    actors, sensors, boxes, traces, packets = [], [], {}, [], []
    original = world.get_settings()
    try:
        s = world.get_settings()
        s.synchronous_mode, s.fixed_delta_seconds = True, .01
        s.substepping, s.max_substep_delta_time, s.max_substeps = True, .01, 10
        s.no_rendering_mode = mode == 'no_render_state'
        world.apply_settings(s)
        r['settings'] = h.settings(world.get_settings())
        h.require(r['settings'] == h.settings(s), 'settings readback')
        bp = world.get_blueprint_library().find('vehicle.lincoln.mkz_2020')
        ego = world.spawn_actor(bp, world.get_map().get_spawn_points()[0]); actors.append(ego)
        ego.set_simulate_physics(False); ego.set_autopilot(False)
        r['ego_id'] = ego.id
        if mode.startswith('camera'):
            for stream, name in [('rgb','sensor.camera.rgb'),('gt','sensor.camera.semantic_segmentation')]:
                bp = world.get_blueprint_library().find(name)
                for k,v in {'image_size_x':'800','image_size_y':'600','fov':'90','sensor_tick':'0.05','lens_k':'0','lens_kcube':'0'}.items(): bp.set_attribute(k,v)
                sensor = world.spawn_actor(bp, carla.Transform(carla.Location(x=1.5,z=1.7)), attach_to=ego, attachment_type=carla.AttachmentType.Rigid)
                actors.append(sensor); sensors.append(sensor)
                boxes[stream] = h.Inbox(1,stream,r['events'])
                sensor.listen(boxes[stream].put)
                r['sensors'][stream] = {'id':sensor.id,'attributes':dict(sensor.attributes)}
        def consume():
            for stream, box in boxes.items():
                for _,_,im,arrival in box.drain():
                    p = {'stream':stream,'frame':im.frame,'sim_s':im.timestamp,'arrival_ns':arrival,
                         'width':im.width,'height':im.height}
                    if mode == 'camera_audit':
                        raw=bytes(im.raw_data);p['sha256']=hashlib.sha256(raw).hexdigest()
                        if stream=='gt': p['histogram']=dict(Counter(raw[2::4]))
                    packets.append(p)
        previous = world.get_snapshot()
        for i in range(600):
            snap,t = tick(world,previous); previous=snap
            actor=snap.find(ego.id);h.require(actor is not None,'ego snapshot absent')
            v=actor.get_velocity()
            t['velocity_mps']=[v.x,v.y,v.z]
            t['state_read_end_ns']=time.monotonic_ns()
            consume()
            t['consume_end_ns']=time.monotonic_ns();traces.append(t)
        deadline=time.monotonic()+1
        while time.monotonic()<deadline: consume();time.sleep(.01)
        r['status']='COLLECTED'
    except Exception: r['error']=traceback.format_exc()
    finally:
        errors=[]
        r['stopped']={}
        for sensor in sensors:
            try: sensor.stop();r['stopped'][str(sensor.id)]=not sensor.is_listening()
            except Exception as e: errors.append(str(e))
        r['queue_cleared']={k:b.close() for k,b in boxes.items()}
        before={k:b.callbacks for k,b in boxes.items()};time.sleep(.1)
        r['callback_quiet']=before=={k:b.callbacks for k,b in boxes.items()}
        r['destroyed']={}
        for a in reversed(actors):
            try:r['destroyed'][str(a.id)]=a.destroy()
            except Exception as e:errors.append(str(e))
        try:
            world.tick(10)
            r['remaining_owned']=[a.id for a in world.get_actors() if a.id in {a.id for a in actors}]
            h.require(not r['remaining_owned'] and all(r['destroyed'].values()) and all(r['stopped'].values()) and r['callback_quiet'],'cleanup')
            world.apply_settings(original)
        except Exception:errors.append(traceback.format_exc())
        if errors:r['status']='FAIL';r['cleanup_errors']=errors
        r['queue_high_water']={k:b.high_water for k,b in boxes.items()}
        h.save(out/'result.json',r)
        (out/'ticks.jsonl').write_text(''.join(json.dumps(t)+'\n' for t in traces))
        (out/'cameras.jsonl').write_text(''.join(json.dumps(p)+'\n' for p in packets))
    return r


def wheel_clock_probe(world, out):
    r={'status':'FAIL','scope':'stationary/unpowered physics on; no driven calibration','rows':[]}
    original=world.get_settings();ego=None
    try:
        s=world.get_settings();s.synchronous_mode=True;s.fixed_delta_seconds=.01;s.no_rendering_mode=True
        world.apply_settings(s)
        ego=world.spawn_actor(world.get_blueprint_library().find('vehicle.lincoln.mkz_2020'),world.get_map().get_spawn_points()[0])
        ego.set_autopilot(False);ego.set_simulate_physics(True)
        physics=ego.get_physics_control()
        r['wheels_config']=[{'radius_cm':w.radius,'max_steer_deg':w.max_steer_angle,'max_brake_torque_nm':w.max_brake_torque} for w in physics.wheels]
        wheels=[carla.VehicleWheelLocation.FL_Wheel,carla.VehicleWheelLocation.FR_Wheel,carla.VehicleWheelLocation.BL_Wheel,carla.VehicleWheelLocation.BR_Wheel]
        prev=world.get_snapshot()
        for i in range(120):
            snap,t=tick(world,prev);prev=snap
            v=snap.find(ego.id).get_velocity();t['velocity_mps']=[v.x,v.y,v.z]
            t['wheel_begin_ns']=time.monotonic_ns()
            t['pitch_deg']=[ego.get_wheel_pitch_angle(w) for w in wheels]
            t['wheel_end_ns']=time.monotonic_ns();t['frame_after_rpc']=world.get_snapshot().frame
            h.require(t['frame_after_rpc']==snap.frame and all(math.isfinite(x) for x in t['pitch_deg']),'wheel frame/nonfinite')
            r['rows'].append(t)
            if i==59:
                a=world.get_snapshot();start=time.monotonic_ns();time.sleep(.25);b=world.get_snapshot()
                r['pause']={'wall_ns':time.monotonic_ns()-start,'before_frame':a.frame,'after_frame':b.frame,
                            'before_sim_s':a.timestamp.elapsed_seconds,'after_sim_s':b.timestamp.elapsed_seconds,
                            'before_platform_s':a.timestamp.platform_timestamp,'after_platform_s':b.timestamp.platform_timestamp}
        r['status']='COLLECTED'
    except Exception:r['error']=traceback.format_exc()
    finally:
        try:
            if ego:r['destroyed']=ego.destroy();world.tick(10)
            r['remaining_vehicles']=[a.id for a in world.get_actors().filter('vehicle.*')]
            h.require(not r['remaining_vehicles'],'wheel probe cleanup')
            world.apply_settings(original)
        except Exception:r['cleanup_error']=traceback.format_exc();r['status']='FAIL'
        h.save(out/'wheel-clock.json',r)
    return r


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);faulthandler.enable()
    r={'status':'FAIL','utc':datetime.now(timezone.utc).isoformat(),'profile':PROFILE,'cases':[],
       'sources':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),HELPER]}}
    h.save(a.output/'summary.json',r);world=original=None
    try:
        c=carla.Client('127.0.0.1',2000);c.set_timeout(20)
        r['versions']=[c.get_client_version(),c.get_server_version()];h.require(r['versions']==['0.9.16']*2,'versions')
        world=c.get_world();original=world.get_settings();weather=world.get_weather()
        h.require(not world.get_actors().filter('vehicle.*') and not world.get_actors().filter('sensor.*'),'empty dedicated world')
        r['settings_before']=h.settings(original);r['map']=world.get_map().name
        world.set_weather(carla.WeatherParameters.ClearNoon)
        for rep,order in enumerate(PROFILE['orders'],1):
            for mode in order:
                name=f'{rep}-{mode}';result=case(world,a.output/name,mode)
                r['cases'].append({'name':name,'status':result['status']});h.save(a.output/'summary.json',r)
                h.require(result['status']=='COLLECTED',name+' failed')
        probe=wheel_clock_probe(world,a.output);h.require(probe['status']=='COLLECTED','wheel probe failed')
        world.set_weather(weather);r['status']='COLLECTED'
    except Exception:r['error']=traceback.format_exc()
    finally:
        try:
            if world is not None and original is not None:
                world.apply_settings(original);r['settings_after']=h.settings(world.get_settings())
                r['remaining_actors']=[a.id for a in world.get_actors() if a.type_id.startswith(('vehicle.','sensor.'))]
                h.require(not r['remaining_actors'] and r['settings_before']==r['settings_after'],'final cleanup')
        except Exception:r['cleanup_error']=traceback.format_exc();r['status']='FAIL'
        h.save(a.output/'summary.json',r);print(json.dumps(r,indent=2))
    return 0 if r['status']=='COLLECTED' else 1

if __name__=='__main__':raise SystemExit(main())

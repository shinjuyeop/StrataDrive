#!/usr/bin/env python3
"""One finite renderer-only diagnostic using original, deliberately stale poses.

No live physical owner, inference, vehicle control or perception publication.
All camera packets, including warmup/unmapped packets, are retained losslessly.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import threading
import time
import traceback
import uuid
import zlib

import carla

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.scene_mailbox_v1 import ActorPose, SceneBinding, SceneSnapshot, encode
from physical_ai.perception.carla_render_adapter_v1 import KinematicRenderer, spawn_clone
from physical_ai.perception.render_provenance_v1 import RenderSession, RenderAssociation, RenderAssociations


def sha(data):
    return hashlib.sha256(data).hexdigest()


def original_scenes(bundle):
    manifest = json.loads((bundle/'run-manifest.json').read_text())
    data = (bundle/'run.tar.gz').read_bytes()
    if sha(data) != manifest['sha256']:
        raise ValueError('original owner archive changed')
    with tarfile.open(bundle/'run.tar.gz', 'r:gz') as tar:
        def read(name):
            data = tar.extractfile(name).read()
            if sha(data) != manifest['members'][name]['sha256']:
                raise ValueError('original owner member changed')
            return data
        result = json.loads(read('capture/result.json'))
        sensors = json.loads(read('capture/sensors.json'))
        lines = read('capture/trace.jsonl').splitlines()
    if len(lines) != 400 or result['execution_profile'] != 'owner5ms':
        raise ValueError('declared original finite owner case')
    b = result['binding']; actor = int(b['actor'])
    context = dict(scope='incomplete retained ego kinematics; diagnostic only',
                   source_archive_sha256=manifest['sha256'], map='Town03_Opt', actor=actor)
    binding = SceneBinding(42, uuid.UUID(b['run']).bytes, sensors['source_clock'],
                           int(b['physics']['generation']), result['model_step_ns'],
                           bytes.fromhex(sha(json.dumps(context, sort_keys=True).encode())),
                           bytes.fromhex(b['model_sha256']), (actor,))
    scenes = []
    for index in (0, 199, 399):
        row = json.loads(lines[index]); r = row['receipt']; p = r['physics']
        if r['run'] != b['run'] or r['actor'] != b['actor'] or not r['interval_work_valid'] or row['settlement'] is None:
            raise ValueError('original settled physical receipt')
        scenes.append(SceneSnapshot(binding, int(r['frame']), round(r['simulation_end_seconds']*1e9),
                      int(r['physics_acquisition_begin_ns']), int(r['physics_acquisition_end_ns']),
                      (ActorPose(actor, tuple(p['body_world_position_m']), tuple(p['body_quaternion_xyzw']),
                                 tuple(p['com_velocity_world_m_s']), tuple(p['angular_velocity_world_rad_s'])),)))
    context['original_state_observations'] = [x for x in sensors['state'] if x['frame'] in {s.frame for s in scenes}]
    if {x['frame'] for x in context['original_state_observations']} != {s.frame for s in scenes}:
        raise ValueError('original actual-state observations missing')
    return context, binding, scenes


def run(args):
    args.output.mkdir(parents=True, exist_ok=False)
    report = dict(schema='m10-render-replay-v1', status='FAIL', scope='renderer-only retained kinematic replay',
                  live_physical_owner=False, complete_scene=False, native_publications=0, inference_calls=0,
                  raw=[], ticks=[], mapped=[], cleanup_errors=[], errors=[])
    world = original = actor = sensor = history = None
    records = []; lock = threading.Lock(); accepting = True; consumed = 0
    try:
        context, binding, scenes = original_scenes(args.original)
        report['original'] = context
        report['scene_packets'] = [encode(s).hex() for s in scenes]
        client = carla.Client('127.0.0.1', args.port); client.set_timeout(10)
        report['versions'] = [client.get_client_version(), client.get_server_version()]
        if report['versions'] != ['294096e-dirty'] * 2:
            raise ValueError('pinned SDK/server version')
        world = client.get_world(); road = world.get_map()
        if not road.name.endswith('/Town03_Opt') or any(list(world.get_actors().filter(k)) for k in ('vehicle.*','walker.*','sensor.*')):
            raise ValueError('dedicated renderer-only Town03 world')
        original = world.get_settings(); settings = world.get_settings()
        settings.synchronous_mode = True; settings.fixed_delta_seconds = .05
        settings.no_rendering_mode = False
        world.apply_settings(settings)
        applied = world.get_settings()
        if not applied.synchronous_mode or applied.no_rendering_mode or abs(applied.fixed_delta_seconds-.05) > 1e-9:
            raise ValueError('renderer settings readback')
        world.set_weather(carla.WeatherParameters.ClearNoon)
        lights = list(world.get_actors().filter('traffic.traffic_light'))
        for light in lights:
            light.set_state(carla.TrafficLightState.Red); light.freeze(True)
        world.tick()
        report['render_context'] = dict(map=road.name, xodr_sha256=sha(road.to_opendrive().encode()),
              world=world.id, step_seconds=.05, traffic_lights=[dict(id=x.id, state=str(x.get_state()), frozen=x.is_frozen()) for x in lights],
              weather=str(world.get_weather()), scope='diagnostic renderer settings; not reconstructed original scene')
        bp = world.get_blueprint_library().find('vehicle.lincoln.mkz_2020')
        bp.set_attribute('role_name','m10_render_clone')
        spawn_pose = road.get_spawn_points()[0]
        report['clone_preparation'] = dict(spawn_point_index=0, source_pose_unchanged=True,
                                          physics_disabled_before_source_pose=True)
        actor = spawn_clone(world, carla, bp, spawn_pose, scenes[0].actors[0])
        adapter = KinematicRenderer(client, world, carla, binding, {binding.actor_ids[0]:actor})
        bp = world.get_blueprint_library().find('sensor.camera.rgb')
        attrs = dict(image_size_x='2560', image_size_y='1536', fov='90', sensor_tick='0.05',
                     role_name='m10_render_replay', enable_postprocess_effects='True')
        for name, value in attrs.items(): bp.set_attribute(name, value)
        camera_pose = carla.Transform(carla.Location(x=1.4, z=1.7))
        sensor = world.spawn_actor(bp, camera_pose, attach_to=actor)
        actual = dict(sensor.attributes)
        for name, value in attrs.items():
            if name in ('role_name','enable_postprocess_effects'):
                if actual[name].lower() != value.lower(): raise ValueError('camera attribute '+name)
            elif float(actual[name]) != float(value): raise ValueError('camera attribute '+name)
        calibration = dict(attributes=actual, relative_pose=dict(x=1.4,y=0,z=1.7,pitch=0,yaw=0,roll=0))
        report['calibration'] = calibration
        session = RenderSession(binding, uuid.uuid4().bytes, world.id, sensor.id,
                                bytes.fromhex(sha(json.dumps(calibration, sort_keys=True).encode())))
        report['renderer_instance'] = session.renderer_instance.hex()
        history = RenderAssociations(session)

        def received(image):
            entered = time.monotonic_ns()
            with lock:
                if not accepting: return
                if len(records) >= 32:
                    report['errors'].append('camera recorder capacity exceeded')
                    return
                records.append((dict(frame=image.frame, source_ns=round(image.timestamp*1e9),
                                     received_wall_ns=entered, width=image.width, height=image.height), bytes(image.raw_data)))
        sensor.listen(received)

        def drain():
            nonlocal consumed
            with lock: pending = records[consumed:]; consumed = len(records)
            for row, raw in pending:
                image = history.consume(renderer_instance=session.renderer_instance, renderer_world=world.id,
                         camera_id=sensor.id, bgra=raw, **row)
                if image is not None:
                    now = time.monotonic_ns()
                    state = next(x for x in context['original_state_observations'] if x['frame'] == image.association.scene.frame)
                    reason = image.unavailable_reason(state['source_ns'], state['begin_wall_ns'], now)
                    if reason != 'original_scene_expired':
                        raise ValueError('retained old scene must remain expired: '+reason)
                    report['mapped'].append(dict(renderer_frame=row['frame'], physical_frame=image.association.scene.frame,
                        physical_source_ns=image.association.scene.source_ns,
                        renderer_source_ns=image.association.renderer_source_ns, scene_sha256=image.association.scene_sha256,
                        original_acquisition_begin_ns=image.association.scene.acquired_begin_ns,
                        original_state_received_wall_ns=state['begin_wall_ns'],
                        callback_received_wall_ns=image.received_wall_ns, unavailable_reason=reason))

        # Preparation frames are retained and explicitly have no physical mapping.
        for _ in range(8):
            world.tick(); drain()
        for scene in scenes:
            begin = time.monotonic_ns(); adapter.apply(scene); end = time.monotonic_ns()
            for _ in range(4):
                tick_begin = time.monotonic_ns(); frame = world.tick(); snap = world.get_snapshot(); tick_end = time.monotonic_ns()
                if snap.frame != frame: raise ValueError('actual renderer tick identity')
                readback = adapter.verify(scene, snap)
                a = RenderAssociation(session, scene, frame, round(snap.timestamp.elapsed_seconds*1e9), begin, end, tick_begin, tick_end)
                history.record(a)
                report['ticks'].append(dict(renderer_frame=frame, renderer_source_ns=a.renderer_source_ns,
                    physical_frame=scene.frame, scene_sha256=a.scene_sha256,
                    apply_begin_ns=begin, apply_end_ns=end, tick_begin_ns=tick_begin, tick_end_ns=tick_end,
                    actual_pose_readback=True, clone_readback=readback))
                drain()
        time.sleep(.2); drain()
        if report['errors'] or {x['physical_frame'] for x in report['mapped']} != {s.frame for s in scenes}:
            raise ValueError('all three retained poses need actual associated camera packets')
        report['status'] = 'PASS_RENDERER_DIAGNOSTIC_ONLY'
    except Exception:
        report['error'] = traceback.format_exc()
    finally:
        if sensor:
            try: sensor.stop()
            except Exception: report['cleanup_errors'].append(traceback.format_exc())
        with lock: accepting = False
        if history:
            report['history'] = dict(consumed=history.consumed, evicted=history.evicted)
            history.close()
        for item in (sensor, actor):
            if item:
                try:
                    if not item.destroy(): raise ValueError('actor destroy rejected')
                except Exception: report['cleanup_errors'].append(traceback.format_exc())
        if world and original:
            try: world.apply_settings(original)
            except Exception: report['cleanup_errors'].append(traceback.format_exc())
        for index, (row, raw) in enumerate(records):
            data = zlib.compress(raw, 1); path = f'{index:03d}-{row["frame"]}.bgra.z'
            (args.output/path).write_bytes(data)
            report['raw'].append(dict(**row, path=path, bgra_sha256=sha(raw), stored_sha256=sha(data),
                                      raw_bytes=len(raw), stored_bytes=len(data)))
        if report['cleanup_errors']: report['status'] = 'FAIL'
        (args.output/'result.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('status','error') if k in report}))
    return 0 if report['status'] == 'PASS_RENDERER_DIAGNOSTIC_ONLY' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=2300)
    parser.add_argument('--original', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    raise SystemExit(run(parser.parse_args()))

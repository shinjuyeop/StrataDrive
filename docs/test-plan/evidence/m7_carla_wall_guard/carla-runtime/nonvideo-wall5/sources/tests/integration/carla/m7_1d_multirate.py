#!/usr/bin/env python3
"""M7-1d: NON_DRIVING 10ms world/state + 50ms cameras. No ECU clock bridge."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import faulthandler
import gc
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import threading
import time
import traceback
import uuid

import carla

# Explicit sibling import also works under python -I. Historical harness unchanged.
HELPER = Path(__file__).with_name('m7_1b_capture.py')
spec = importlib.util.spec_from_file_location('m7_capture_helpers', HELPER)
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
DT, CAMERA_DT, TOL = 0.01, 0.05, 1e-6
STARTUP, DRAIN = 100, 100
PROFILE = {'world_s': DT, 'camera_s': CAMERA_DT, 'camera_stride': 5,
           'startup_ticks': STARTUP, 'drain_ticks': DRAIN,
           'nominal_ticks': 800, 'fault_and_reset_ticks': 400,
           'camera': [800, 600, 90], 'queue_capacity': h.CAPACITY,
           'final_callback_wait_wall_s': 3, 'pause_wall_s': 0.25,
           'freshness_limit_ns': 30_000_000, 'ego_physics': False,
           'autopilot': False, 'actuation_calls': 0,
           'source_clock': 'CARLA simulation', 'receipt_clock': 'Host CLOCK_MONOTONIC',
           'wall_acquisition_mapping': 'unavailable', 'M6_runtime': 'not attached'}


class Owner:
    def __init__(self, world):
        self.world = world
        self.thread = threading.get_ident()
        self.previous = world.get_snapshot()
        self.trace = []

    def tick(self):
        h.require(threading.get_ident() == self.thread, 'foreign tick thread')
        begin = time.monotonic_ns()
        frame = self.world.tick(h.TIMEOUT)
        snapshot = self.world.get_snapshot()
        self.trace.append({'frame': frame, 'snapshot_frame': snapshot.frame,
                           'previous_frame': self.previous.frame,
                           'previous_sim_s': self.previous.timestamp.elapsed_seconds,
                           'sim_s': snapshot.timestamp.elapsed_seconds,
                           'delta_s': snapshot.timestamp.delta_seconds,
                           'begin_ns': begin, 'end_ns': time.monotonic_ns()})
        h.require(frame == snapshot.frame == self.previous.frame + 1, 'frame discontinuity')
        h.require(abs(snapshot.timestamp.delta_seconds - DT) <= TOL and
                  abs(snapshot.timestamp.elapsed_seconds - self.previous.timestamp.elapsed_seconds - DT) <= TOL,
                  'not a 10ms simulation step')
        self.previous = snapshot
        return snapshot


def collect(world, output, epoch, count, fault=False):
    output.mkdir()
    run_id = str(uuid.uuid4())
    join = h.Joiner(run_id, epoch)
    result = {'status': 'FAIL', 'run_id': run_id, 'plant_epoch': epoch,
              'episode': world.id, 'profile': PROFILE, 'fault': fault,
              'requested_ticks': count, 'events': [], 'sensors': {}}
    actors, sensors, boxes, frames = [], [], {}, []
    owner = None
    weather = world.get_weather()
    try:
        h.require(not world.get_actors().filter('vehicle.*') and
                  not world.get_actors().filter('sensor.*'), 'dedicated empty world required')
        world.set_weather(carla.WeatherParameters.ClearNoon)
        bp = world.get_blueprint_library().find('vehicle.lincoln.mkz_2020')
        bp.set_attribute('role_name', 'stratadrive_m7_1d_ego')
        spawn = world.get_map().get_spawn_points()[0]
        ego = world.spawn_actor(bp, spawn)
        actors.append(ego)
        ego.set_simulate_physics(False)
        ego.set_autopilot(False)
        result.update(map=world.get_map().name, blueprint=bp.id, ego_id=ego.id, spawn=h.pose(spawn))
        # API inventory only: static vehicle velocity is not a wheel sensor.
        result['wheel_api_inventory'] = [name for name in dir(ego) if 'wheel' in name.lower()]
        for stream, kind in [('rgb.front', 'sensor.camera.rgb'), ('gt.front', 'sensor.camera.semantic_segmentation')]:
            bp = world.get_blueprint_library().find(kind)
            for key, value in {'image_size_x': '800', 'image_size_y': '600', 'fov': '90',
                               'sensor_tick': '0.05', 'lens_k': '0', 'lens_kcube': '0'}.items():
                bp.set_attribute(key, value)
            sensor = world.spawn_actor(bp, carla.Transform(carla.Location(x=1.5, z=1.7)),
                                       attach_to=ego, attachment_type=carla.AttachmentType.Rigid)
            actors.append(sensor)
            sensors.append(sensor)
            result['sensors'][stream] = {'id': sensor.id, 'parent_id': sensor.parent.id,
                                          'attributes': dict(sensor.attributes)}
            h.require(sensor.parent.id == ego.id and abs(float(sensor.attributes['sensor_tick']) - CAMERA_DT) < TOL,
                      'sensor setup readback mismatch')
            boxes[stream] = h.Inbox(epoch, stream, result['events'])
            sensor.listen(boxes[stream].put)
        owner = Owner(world)
        first = owner.previous.frame + 1
        result['first_frame'] = first
        # Five consecutive state losses exercise >30ms without changing timestamps.
        state_drops = set(range(first + 130, first + 135)) if fault else set()
        camera_dropped = set()

        def consume():
            for stream, box in boxes.items():
                for packet_epoch, _, image, arrived in box.drain():
                    if fault and stream not in camera_dropped and first + 130 <= image.frame < first + 135:
                        camera_dropped.add(stream)
                        result['events'].append({'reason': 'injected_drop', 'stream': stream, 'frame': image.frame})
                        continue
                    raw = bytes(image.raw_data)
                    h.require(image.width == 800 and image.height == 600 and len(raw) == 800*600*4, 'image format')
                    packet = {'run_id': run_id, 'plant_epoch': packet_epoch, 'stream': stream,
                              'source_id': f"sensor:{result['sensors'][stream]['id']}",
                              'sequence': image.frame, 'frame': image.frame,
                              'timestamp_seconds': image.timestamp, 'source_time_ns': round(image.timestamp*1e9),
                              'arrival_monotonic_ns': arrived, 'delivery_monotonic_ns': time.monotonic_ns(),
                              'validity': 'valid', 'width': image.width, 'height': image.height,
                              'encoding': 'BGRA8', 'stride': image.width*4,
                              'sha256': hashlib.sha256(raw).hexdigest(), 'pose_carla': h.pose(image.transform)}
                    if stream == 'gt.front':
                        packet['class_histogram'] = dict(Counter(raw[2::4]))
                    join.accept(packet)

        for i in range(count):
            snapshot = owner.tick()
            frames.append(snapshot.frame)
            packet = h.state_packet(snapshot, ego, run_id, epoch)
            if snapshot.frame in state_drops:
                result['events'].append({'reason': 'injected_drop', 'stream': 'state', 'frame': snapshot.frame})
            else:
                join.accept(packet)
            consume()
            if not fault and i == count // 2:
                before = world.get_snapshot()
                begin = time.monotonic_ns()
                time.sleep(PROFILE['pause_wall_s'])
                after = world.get_snapshot()
                result['pause'] = {'before_frame': before.frame, 'after_frame': after.frame,
                                   'before_sim_s': before.timestamp.elapsed_seconds,
                                   'after_sim_s': after.timestamp.elapsed_seconds,
                                   'begin_ns': begin, 'end_ns': time.monotonic_ns(),
                                   'ECU_wall_timeout': 'NOT RUN'}
                h.require(before.frame == after.frame and before.timestamp.elapsed_seconds == after.timestamp.elapsed_seconds,
                          'simulation advanced during pause')
        deadline = time.monotonic() + PROFILE['final_callback_wait_wall_s']
        while time.monotonic() < deadline:
            consume()
            time.sleep(0.01)
        result['settings_end'] = h.settings(world.get_settings())
        h.require(result['settings_end']['synchronous_mode'] and
                  abs(result['settings_end']['fixed_delta_seconds']-DT) < TOL, 'world settings changed')
        result['status'] = 'COLLECTED'  # Independent oracle supplies the acceptance verdict.
    except Exception:
        result['error'] = traceback.format_exc()
    finally:
        errors = []
        result['listeners_after_stop'] = {}
        for sensor in sensors:
            try:
                sensor.stop()
                result['listeners_after_stop'][str(sensor.id)] = sensor.is_listening()
            except Exception as exc:
                errors.append(str(exc))
        result['cleared'] = {k: b.close() for k, b in boxes.items()}
        before = {k: b.callbacks for k, b in boxes.items()}
        time.sleep(0.1)
        result['callback_quiet'] = before == {k: b.callbacks for k, b in boxes.items()}
        result['destroy_results'] = {}
        for actor in reversed(actors):
            try:
                result['destroy_results'][str(actor.id)] = actor.destroy()
            except Exception as exc:
                errors.append(str(exc))
        try:
            if owner:
                owner.tick()  # Cleanup only; separate from collection denominator.
            result['remaining_owned_ids'] = [a.id for a in world.get_actors() if a.id in {x.id for x in actors}]
            world.set_weather(weather)
            h.require(not result['remaining_owned_ids'] and all(result['destroy_results'].values()) and
                      not any(result['listeners_after_stop'].values()) and result['callback_quiet'], 'cleanup incomplete')
        except Exception:
            errors.append(traceback.format_exc())
        if errors:
            result['cleanup_errors'], result['status'] = errors, 'FAIL'
        result['join_events'] = join.events
        result['collection_ticks'] = len(frames)
        result['queue_high_water'] = {k: b.high_water for k, b in boxes.items()}
        h.save(output/'result.json', result)
        (output/'ticks.jsonl').write_text(''.join(json.dumps(t)+'\n' for t in (owner.trace if owner else [])))
        (output/'packets.jsonl').write_text(''.join(json.dumps(p)+'\n' for p in join.records.values()))
        for folder, streams in [('online', ('rgb.front', 'state')), ('training_evaluation', ('gt.front',))]:
            (output/folder).mkdir()
            (output/folder/'records.jsonl').write_text(''.join(json.dumps(p)+'\n' for p in join.records.values() if p['stream'] in streams))
    return result, join


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    faulthandler.enable()
    summary = {'status': 'FAIL', 'started_utc': datetime.now(timezone.utc).isoformat(),
               'profile': PROFILE, 'sources': {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in (Path(__file__), HELPER)}, 'python': sys.version,
               'executable': sys.executable, 'carla_module': carla.__file__, 'cases': []}
    h.save(args.output/'summary.json', summary)
    world = original = None
    try:
        client = carla.Client('127.0.0.1', 2000)
        client.set_timeout(h.TIMEOUT)
        summary['versions'] = [client.get_client_version(), client.get_server_version()]
        h.require(summary['versions'] == ['0.9.16']*2, 'version mismatch')
        world = client.get_world()
        original = world.get_settings()
        summary['settings_before'] = h.settings(original)
        settings = world.get_settings()
        settings.synchronous_mode, settings.fixed_delta_seconds = True, DT
        settings.no_rendering_mode = False
        settings.substepping, settings.max_substep_delta_time, settings.max_substeps = True, 0.01, 10
        world.apply_settings(settings)
        summary['settings_during'] = h.settings(world.get_settings())
        h.require(summary['settings_during'] == h.settings(settings), 'settings readback')
        for name, count, fault in [('nominal', 800, False), ('drop', 400, True)]:
            result, join = collect(world, args.output/name, 1, count, fault)
            summary['cases'].append({'name': name, 'status': result['status']})
            summary['stage'] = name
            h.save(args.output/'summary.json', summary)
            h.require(result['status'] == 'COLLECTED', f'{name} failed')
            if name == 'nominal':
                old_packets = [next(p for p in join.records.values() if p['stream'] == s) for s in h.STREAMS]
                old_run = join.run_id
        before_episode = world.id
        summary['stage'] = 'before_fresh_client_reload'
        h.save(args.output/'summary.json', summary)
        world = None
        del client
        gc.collect()
        client = carla.Client('127.0.0.1', 2000)
        client.set_timeout(h.TIMEOUT)
        world = client.get_world()
        h.require(world.id == before_episode, 'external reset')
        world = client.reload_world(False)
        h.require(world.id != before_episode, 'episode unchanged')
        h.require(h.settings(world.get_settings()) == summary['settings_during'], 'reload settings changed')
        result, join = collect(world, args.output/'after_reset', 2, 400)
        for p in old_packets:
            h.require(not join.accept(p) and join.events[-1]['reason'] == 'old_epoch', 'old metadata accepted')
        h.save(args.output/'reset.json', {'before_episode': before_episode, 'after_episode': world.id,
               'before_run': old_run, 'after_run': join.run_id, 'before_epoch': 1, 'after_epoch': 2,
               'old_metadata_rejections': join.events[-3:], 'old_Actual_ECU': 'NOT RUN'})
        summary['cases'].append({'name': 'after_reset', 'status': result['status']})
        h.require(result['status'] == 'COLLECTED', 'reset collection failed')
        summary['status'] = 'COLLECTED'
    except Exception:
        summary['error'] = traceback.format_exc()
    finally:
        try:
            if world is not None and original is not None:
                world.apply_settings(original)
                summary['settings_after'] = h.settings(world.get_settings())
                h.require(summary['settings_after'] == summary['settings_before'], 'settings not restored')
                summary['remaining_actors'] = [a.id for a in world.get_actors() if a.type_id.startswith(('vehicle.', 'sensor.'))]
                h.require(not summary['remaining_actors'], 'actors remain')
        except Exception:
            summary['cleanup_error'], summary['status'] = traceback.format_exc(), 'FAIL'
        h.save(args.output/'summary.json', summary)
        print(json.dumps(summary, indent=2))
    return 0 if summary['status'] == 'COLLECTED' else 1


if __name__ == '__main__':
    raise SystemExit(main())

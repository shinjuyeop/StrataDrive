#!/usr/bin/env python3
"""CARLA 0.9.16 NON_DRIVING RGB/GT/state collection and containment tests."""
import argparse
import faulthandler
import gc
from collections import Counter, deque
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import threading
import time
import traceback
import uuid
import zlib

import carla

PERIOD = 0.05
TOLERANCE = 1e-6
CAPACITY = 64
TIMEOUT = 10.0
STREAMS = ('rgb.front', 'gt.front', 'state')


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def xyz(v):
    return [v.x, v.y, v.z]


def pose(t):
    return {'position_m': xyz(t.location), 'rotation_deg':
            [t.rotation.roll, t.rotation.pitch, t.rotation.yaw]}


def settings(s):
    return {k: getattr(s, k) for k in ('synchronous_mode', 'fixed_delta_seconds',
            'no_rendering_mode', 'substepping', 'max_substep_delta_time', 'max_substeps')}


def png(path, width, height, channels, data):
    """Lossless sample export; GT retains raw class IDs, without a palette."""
    def chunk(kind, body):
        return struct.pack('!I', len(body)) + kind + body + struct.pack('!I', zlib.crc32(kind + body))
    stride = width * channels
    scanlines = b''.join(b'\0' + data[y*stride:(y+1)*stride] for y in range(height))
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!IIBBBBB',
                     width, height, 8, 2 if channels == 3 else 0, 0, 0, 0)) +
                     chunk(b'IDAT', zlib.compress(scanlines)) + chunk(b'IEND', b''))


class TickOwner:
    def __init__(self, world):
        self.world, self.thread = world, threading.get_ident()
        self.previous = world.get_snapshot()
        self.trace = []

    def tick(self, expected):
        require(threading.get_ident() == self.thread, 'wrong tick owner')
        require(expected == self.previous.frame + 1, 'duplicate/out-of-order tick request')
        current = self.world.get_settings()
        require(current.synchronous_mode and abs(current.fixed_delta_seconds - PERIOD) < TOLERANCE,
                'world timing settings changed')
        begin = time.monotonic_ns()
        frame = self.world.tick(TIMEOUT)
        snapshot = self.world.get_snapshot()
        self.trace.append({'request_frame': expected, 'return_frame': frame,
                           'snapshot_frame': snapshot.frame, 'begin_ns': begin,
                           'end_ns': time.monotonic_ns(), 'sim_seconds': snapshot.timestamp.elapsed_seconds,
                           'delta_seconds': snapshot.timestamp.delta_seconds})
        require(frame == expected == snapshot.frame, 'tick/frame discontinuity')
        require(abs(snapshot.timestamp.delta_seconds - PERIOD) <= TOLERANCE, 'delta != 50ms')
        require(abs(snapshot.timestamp.elapsed_seconds - self.previous.timestamp.elapsed_seconds - PERIOD)
                <= TOLERANCE, 'simulation timestamp discontinuity')
        self.previous = snapshot
        return snapshot


class Inbox:
    """Bounded callback queue: drop newest on overflow, retain loss evidence."""
    def __init__(self, epoch, kind, events, fault=False):
        self.epoch, self.kind, self.events, self.fault = epoch, kind, events, fault
        self.queue, self.lock = deque(), threading.Lock()
        self.closed = False
        self.base = None
        self.held = None
        self.callbacks = 0
        self.high_water = 0

    def put(self, image):
        item = (self.epoch, self.kind, image, time.monotonic_ns())
        with self.lock:
            self.callbacks += 1
            if self.closed:
                self.events.append({'reason': 'closed_callback', 'stream': self.kind, 'frame': image.frame})
                return
            if self.base is None:
                self.base = image.frame
            index = image.frame - self.base
            # Explicit callback-boundary faults, original image/frame/time intact.
            if self.fault and index == 25:
                self.events.append({'reason': 'injected_drop', 'stream': self.kind, 'frame': image.frame})
                return
            if self.fault and index == 30:
                self.held = item
                self.events.append({'reason': 'injected_delay', 'stream': self.kind, 'frame': image.frame})
                return
            self._append(item)
            if self.fault and index == 31:
                self._append(item)  # duplicate, never a new measurement
            if self.fault and index == 32 and self.held:
                self._append(self.held)  # delivered after two newer source frames
                self.held = None

    def _append(self, item):
        if len(self.queue) == CAPACITY:
            self.events.append({'reason': 'overflow', 'stream': self.kind, 'frame': item[2].frame})
        else:
            self.queue.append(item)
            self.high_water = max(self.high_water, len(self.queue))

    def drain(self):
        with self.lock:
            items = list(self.queue)
            self.queue.clear()
            return items

    def close(self):
        with self.lock:
            self.closed = True
            cleared = len(self.queue) + int(self.held is not None)
            self.queue.clear()
            self.held = None
            return cleared


class Joiner:
    def __init__(self, run_id, epoch):
        self.run_id, self.epoch = run_id, epoch
        self.records, self.events, self.dead = {}, [], set()
        self.latest = {}

    def accept(self, packet):
        key = (packet['frame'], packet['stream'])
        reason = None
        if packet['run_id'] != self.run_id or packet['plant_epoch'] != self.epoch:
            reason = 'old_epoch'
        elif key in self.dead:
            reason = 'late_after_deadline'
        elif key in self.records:
            reason = 'duplicate'
        if reason:
            self.events.append({'reason': reason, 'stream': packet['stream'], 'frame': packet['frame']})
            return False
        if packet['frame'] < self.latest.get(packet['stream'], -1):
            self.events.append({'reason': 'reordered', 'stream': packet['stream'], 'frame': packet['frame']})
        self.latest[packet['stream']] = max(packet['frame'], self.latest.get(packet['stream'], -1))
        self.records[key] = packet
        return True

    def expire(self, frames):
        missing = []
        for frame in frames:
            for stream in STREAMS:
                key = (frame, stream)
                if key not in self.records:
                    self.dead.add(key)
                    missing.append({'frame': frame, 'stream': stream, 'reason': 'missing'})
        return missing


def state_packet(snapshot, ego, run_id, epoch):
    actor = snapshot.find(ego.id)
    require(actor is not None, 'ego missing in snapshot')
    t = actor.get_transform()
    velocity, acceleration, angular = actor.get_velocity(), actor.get_acceleration(), actor.get_angular_velocity()
    # Project reflection is at actor origin; rear axle calibration remains open.
    s = [1, -1, 1]
    rotation = t.get_matrix()
    return {'run_id': run_id, 'plant_epoch': epoch, 'stream': 'state',
            'source_id': f'ego:{ego.id}', 'sequence': snapshot.frame, 'frame': snapshot.frame,
            'timestamp_seconds': snapshot.timestamp.elapsed_seconds,
            'source_time_ns': round(snapshot.timestamp.elapsed_seconds * 1e9),
            'arrival_monotonic_ns': time.monotonic_ns(), 'validity': 'valid',
            'reference_point': 'actor_origin; rear axle transform uncalibrated',
            'pose_carla': pose(t), 'velocity_carla_mps': xyz(velocity),
            'acceleration_carla_mps2': xyz(acceleration), 'angular_carla_deg_s': xyz(angular),
            'position_project_m': [t.location.x, -t.location.y, t.location.z],
            'rotation_project': [[s[i]*rotation[i][j]*s[j] for j in range(3)] for i in range(3)],
            'velocity_project_mps': [velocity.x, -velocity.y, velocity.z],
            'angular_project_rad_s': [-math.radians(angular.x), math.radians(angular.y), -math.radians(angular.z)]}


def collect(world, output, epoch, fault=False, count=240, inject_exception=False):
    output.mkdir(exist_ok=False)
    run_id = str(uuid.uuid4())
    join = Joiner(run_id, epoch)
    result = {'run_id': run_id, 'plant_epoch': epoch, 'fault_injection': fault,
              'status': 'FAIL', 'tick_count_requested': count, 'events': [],
              'profile': {'startup': 20, 'main': count-40, 'drain': 20,
                          'camera': [800, 600, 90, PERIOD], 'queue_capacity': CAPACITY,
                          'deadline_wall_s': TIMEOUT, 'non_driving': True,
                          'camera_actor_extrinsic': {'x': 1.5, 'y': 0, 'z': 1.7, 'pitch': 0, 'yaw': 0, 'roll': 0},
                          'calibration_id': 'm7-smoke-front-v1; not OEM/rear-axle calibration'},
              'online_streams': ['rgb.front', 'state'], 'training_evaluation_streams': ['gt.front']}
    actors, sensors, boxes = [], [], {}
    owner = None
    frames = []
    samples = set()
    original_weather = world.get_weather()
    expected_exception = False
    try:
        require(not world.get_actors().filter('vehicle.*'), 'dedicated empty vehicle world required')
        world.set_weather(carla.WeatherParameters.ClearNoon)
        bp = world.get_blueprint_library().find('vehicle.lincoln.mkz_2020')
        bp.set_attribute('role_name', 'stratadrive_m7_1b_ego')
        spawn = world.get_map().get_spawn_points()[0]
        ego = world.spawn_actor(bp, spawn)
        actors.append(ego)
        ego.set_simulate_physics(False)
        ego.set_autopilot(False)
        result.update(map=world.get_map().name, blueprint=bp.id, ego_id=ego.id, spawn=pose(spawn), sensors={})
        extrinsic = carla.Transform(carla.Location(x=1.5, z=1.7))
        for stream, kind in [('rgb.front', 'sensor.camera.rgb'), ('gt.front', 'sensor.camera.semantic_segmentation')]:
            bp = world.get_blueprint_library().find(kind)
            for key, value in {'image_size_x': '800', 'image_size_y': '600', 'fov': '90',
                               'sensor_tick': '0.05', 'lens_k': '0', 'lens_kcube': '0'}.items():
                bp.set_attribute(key, value)
            sensor = world.spawn_actor(bp, extrinsic, attach_to=ego, attachment_type=carla.AttachmentType.Rigid)
            actors.append(sensor)
            sensors.append(sensor)
            require(sensor.parent.id == ego.id, 'sensor parent mismatch')
            result['sensors'][stream] = {'id': sensor.id, 'parent_id': sensor.parent.id,
                                          'attributes': dict(sensor.attributes), 'actor_extrinsic': pose(extrinsic)}
            boxes[stream] = Inbox(epoch, stream, result['events'], fault)
            sensor.listen(boxes[stream].put)
        focal = 800 / (2 * math.tan(math.radians(90)/2))
        result['intrinsics'] = [[focal, 0, 400], [0, focal, 300], [0, 0, 1]]
        owner = TickOwner(world)
        result['tick_guard'] = []
        try:
            owner.tick(owner.previous.frame)  # explicit duplicate request; no RPC
        except RuntimeError as exc:
            result['tick_guard'].append(str(exc))
        require(result['tick_guard'], 'duplicate tick guard did not reject')

        def consume():
            for stream, box in boxes.items():
                for item_epoch, _, image, arrival in box.drain():
                    raw = bytes(image.raw_data)
                    require(len(raw) == 800*600*4 and image.width == 800 and image.height == 600,
                            'invalid camera layout')
                    require(math.isfinite(image.timestamp), 'nonfinite sensor time')
                    record = {'run_id': run_id, 'plant_epoch': item_epoch, 'stream': stream,
                              'source_id': f'sensor:{result["sensors"][stream]["id"]}',
                              'sequence': image.frame, 'frame': image.frame,
                              'timestamp_seconds': image.timestamp, 'source_time_ns': round(image.timestamp*1e9),
                              'arrival_monotonic_ns': arrival, 'delivery_monotonic_ns': time.monotonic_ns(),
                              'validity': 'valid', 'encoding': 'BGRA8', 'stride': 3200,
                              'width': image.width, 'height': image.height, 'pose_carla': pose(image.transform),
                              'sha256_bgra': hashlib.sha256(raw).hexdigest()}
                    if stream == 'gt.front':
                        labels = raw[2::4]  # raw red-channel class IDs, never CityScapes palette
                        require(all(x == 0 for x in raw[0::4]) and all(x == 0 for x in raw[1::4]),
                                'GT is not raw label encoding')
                        record['class_histogram'] = dict(Counter(labels))
                        record['label_map'] = 'CARLA0.9.16 raw semantic tags; red channel'
                    accepted = join.accept(record)
                    if accepted and len(frames) >= 21 and stream not in samples and image.frame in frames[20:]:
                        folder = output / ('training_evaluation' if stream == 'gt.front' else 'online')
                        folder.mkdir(exist_ok=True)
                        if stream == 'gt.front':
                            png(folder/'semantic_ids.png', 800, 600, 1, labels)
                        else:
                            rgb = bytearray(800*600*3)
                            rgb[0::3], rgb[1::3], rgb[2::3] = raw[2::4], raw[1::4], raw[0::4]
                            png(folder/'rgb.png', 800, 600, 3, rgb)
                        record['sample_export'] = str(folder.relative_to(output))
                        samples.add(stream)

        errors = []
        def other_thread_tick():
            try:
                owner.tick(owner.previous.frame + 1)
            except RuntimeError as exc:
                errors.append(str(exc))
        thread = threading.Thread(target=other_thread_tick)
        thread.start()
        thread.join()
        require(errors == ['wrong tick owner'], 'foreign tick thread not rejected')
        result['tick_guard'].extend(errors)
        for i in range(count):
            snap = owner.tick(owner.previous.frame + 1)
            frames.append(snap.frame)
            packet = state_packet(snap, ego, run_id, epoch)
            if fault and i == 25:
                result['events'].append({'reason': 'injected_drop', 'stream': 'state', 'frame': snap.frame})
            else:
                join.accept(packet)
                if fault and i == 31:
                    join.accept(packet)
            consume()
            if i == 119 or (count < 120 and i == 35):
                before = world.get_snapshot()
                start = time.monotonic_ns()
                time.sleep(0.25)
                after = world.get_snapshot()
                result['pause'] = {'before_frame': before.frame, 'after_frame': after.frame,
                                   'before_sim_s': before.timestamp.elapsed_seconds,
                                   'after_sim_s': after.timestamp.elapsed_seconds,
                                   'wall_ns': time.monotonic_ns()-start, 'existing_M6_monitors': 'NOT RUN'}
                require(before.frame == after.frame and before.timestamp.elapsed_seconds == after.timestamp.elapsed_seconds,
                        'world advanced during pause')
            if inject_exception and i == 21:
                raise InterruptedError('deliberate sensor lifecycle exception')
        # Camera callbacks may lag; collect late delivery at original frame/time.
        deadline = time.monotonic() + TIMEOUT
        while time.monotonic() < deadline:
            consume()
            if all((f, s) in join.records for f in frames for s in STREAMS):
                break
            time.sleep(0.01)
        missing = join.expire(frames)
        result['missing'] = missing
        result['windows'] = {}
        for name, selected in [('startup', frames[:20]), ('main', frames[20:-20]), ('drain', frames[-20:])]:
            result['windows'][name] = {'expected_frames': len(selected), 'streams': {}}
            for stream in STREAMS:
                lost = [f for f in selected if (f, stream) not in join.records]
                result['windows'][name]['streams'][stream] = {'received': len(selected)-len(lost), 'missing_frames': lost}
        pairs = 0
        for frame in frames:
            packets = [join.records.get((frame, s)) for s in STREAMS]
            if not all(packets):
                continue
            require(max(p['timestamp_seconds'] for p in packets)-min(p['timestamp_seconds'] for p in packets)
                    <= TOLERANCE, 'cross-stream timestamp mismatch')
            require(packets[0]['pose_carla'] == packets[1]['pose_carla'], 'RGB/GT camera pose mismatch')
            # RGB/GT must match the configured rigid transform of this actor.
            actor = packets[2]
            sign = [1, -1, 1]
            native_rotation = [[sign[i]*actor['rotation_project'][i][j]*sign[j]
                                for j in range(3)] for i in range(3)]
            offset = [1.5, 0, 1.7]
            expected = [actor['pose_carla']['position_m'][i] +
                        sum(native_rotation[i][j]*offset[j] for j in range(3)) for i in range(3)]
            require(max(abs(a-b) for a, b in zip(expected, packets[0]['pose_carla']['position_m']))
                    < 1e-4, 'camera/actor extrinsic mismatch')
            pairs += 1
        result['joined_frames'] = pairs
        result['extrinsic_tolerance_m'] = 1e-4
        if not fault:
            require(all(not v['missing_frames'] for v in result['windows']['main']['streams'].values()),
                    'nominal main sensor loss')
        else:
            for stream in STREAMS:
                injected = [e['frame'] for e in result['events'] if e['reason'] == 'injected_drop' and e['stream'] == stream]
                require(injected and all({'frame': f, 'stream': stream, 'reason': 'missing'} in missing for f in injected),
                        'injected loss hidden')
            for stream in ('rgb.front', 'gt.front'):
                require(any(e['reason'] == 'reordered' and e['stream'] == stream for e in join.events), 'reorder not observed')
            require(sum(e['reason'] == 'duplicate' for e in join.events) >= 3, 'duplicates not detected')
        result['status'] = 'PASS'
    except InterruptedError as exc:
        if not inject_exception:
            raise
        result['expected_exception'] = str(exc)
        expected_exception = True
    except Exception:
        result['error'] = traceback.format_exc()
    finally:
        try:
            cleanup_errors = []
            result['listeners_after_stop'] = {}
            for sensor in sensors:
                try:
                    sensor.stop()
                    result['listeners_after_stop'][str(sensor.id)] = sensor.is_listening()
                except Exception as exc:
                    cleanup_errors.append(f'stop {sensor.id}: {exc}')
            result['queue_cleared'] = {k: b.close() for k, b in boxes.items()}
            stopped_counts = {k: b.callbacks for k, b in boxes.items()}
            time.sleep(0.1)
            result['callback_counts_after_stop'] = {k: b.callbacks for k, b in boxes.items()}
            result['callback_quiet'] = stopped_counts == result['callback_counts_after_stop']
            result['destroy_results'] = {}
            for actor in reversed(actors):
                try:
                    result['destroy_results'][str(actor.id)] = actor.destroy()
                except Exception as exc:
                    cleanup_errors.append(f'destroy {actor.id}: {exc}')
            if owner:
                owner.tick(owner.previous.frame+1)
            result['remaining_owned_ids'] = [a.id for a in world.get_actors() if a.id in {x.id for x in actors}]
            require(not cleanup_errors, str(cleanup_errors))
            require(not any(result['listeners_after_stop'].values()), 'sensor listener still active')
            require(result['callback_quiet'], 'callbacks continued after stop')
            require(not result['remaining_owned_ids'] and all(result['destroy_results'].values()), 'owned actor cleanup failed')
            require(all(not b.queue and b.held is None and b.closed for b in boxes.values()), 'queue cleanup failed')
            world.set_weather(original_weather)
            if expected_exception:
                result['status'] = 'PASS'
        except Exception:
            result['cleanup_error'] = traceback.format_exc()
            result['status'] = 'FAIL'
        result['join_events'] = join.events
        result['queue_high_water'] = {k: b.high_water for k, b in boxes.items()}
        result['ticks'] = len(owner.trace) if owner else 0
        result['collection_ticks'] = len(frames)
        result['wall_tick_s'] = (owner.trace[len(frames)-1]['end_ns']-owner.trace[0]['begin_ns'])/1e9 if frames else 0
        result['real_time_factor'] = len(frames)*PERIOD/result['wall_tick_s'] if result['wall_tick_s'] else None
        save(output/'result.json', result)
        (output/'ticks.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in (owner.trace if owner else [])))
        (output/'packets.jsonl').write_text(''.join(json.dumps(p)+'\n' for p in join.records.values()))
        # Separate exported consumer channels; mixed packets.jsonl is audit only.
        for folder, streams in [('online', ('rgb.front', 'state')),
                                ('training_evaluation', ('gt.front',))]:
            (output/folder).mkdir(exist_ok=True)
            (output/folder/'records.jsonl').write_text(''.join(json.dumps(p)+'\n'
                for p in join.records.values() if p['stream'] in streams))
    return result, join


def replay_boundary_checks(previous, output):
    """Metadata replay tests complement live callback faults; never live plant claims."""
    records = list(previous.records.values())
    require(records, 'no live packets for replay')
    tests = []
    for stream in STREAMS:
        p = next(p for p in records if p['stream'] == stream)
        fresh = Joiner(str(uuid.uuid4()), previous.epoch+1)
        require(not fresh.accept(p) and fresh.events[-1]['reason'] == 'old_epoch', 'old callback accepted')
        same = Joiner(p['run_id'], p['plant_epoch'])
        same.dead.add((p['frame'], stream))
        require(not same.accept(p) and same.events[-1]['reason'] == 'late_after_deadline', 'late callback healed missing')
        tests.append({'stream': stream, 'old_epoch': 'rejected', 'late_after_deadline': 'rejected',
                      'frame': p['frame'], 'source_time_ns': p['source_time_ns']})
    # Synthetic frame objects exercise queue capacity, not a live sensor overflow.
    class Frame:
        frame = 1
    box = Inbox(1, 'rgb.front', [])
    for _ in range(CAPACITY+1):
        box.put(Frame())
    require(len(box.queue) == CAPACITY and len(box.events) == 1 and box.events[0]['reason'] == 'overflow',
            'bounded queue overflow not reported')
    before = [(i[2].frame, i[3]) for i in box.queue]
    box.close()
    require(not box.queue and box.closed, 'queue did not clear')
    # Coordinate sign/round-trip checks include nonzero vectors, independent of static ego.
    v = [1.25, -2.5, 3.75]
    reflected = [v[0], -v[1], v[2]]
    require([reflected[0], -reflected[1], reflected[2]] == v, 'reflection round trip')
    require(-math.radians(90) < 0, 'yaw sign')
    save(output/'boundary-replay.json', {'status': 'PASS', 'scope': 'metadata/synthetic capacity replay, not live overflow/ECU test',
         'streams': tests, 'overflow_count': len(box.events), 'queue_high_water': len(before),
         'coordinate_round_trip': 'PASS', 'GT_online_subscriptions': 0})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    faulthandler.enable()
    summary = {'status': 'FAIL', 'started_utc': datetime.now(timezone.utc).isoformat(),
               'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'python': sys.version, 'executable': sys.executable, 'carla_module': carla.__file__, 'cases': [],
               'clock_domains': {'source': 'CARLA simulation', 'arrival': 'Host CLOCK_MONOTONIC'},
               'M6_runtime': 'not attached', 'ego_actuation': 'none'}
    world = original = None
    try:
        client = carla.Client('127.0.0.1', 2000)
        client.set_timeout(TIMEOUT)
        summary['versions'] = [client.get_client_version(), client.get_server_version()]
        require(summary['versions'] == ['0.9.16', '0.9.16'], 'version mismatch')
        world = client.get_world()
        original = world.get_settings()
        summary['settings_before'] = settings(original)
        configured = world.get_settings()
        configured.synchronous_mode, configured.fixed_delta_seconds = True, PERIOD
        configured.no_rendering_mode = False
        configured.substepping, configured.max_substep_delta_time, configured.max_substeps = True, 0.01, 10
        world.apply_settings(configured)
        summary['settings_during'] = settings(world.get_settings())
        require(summary['settings_during'] == settings(configured), 'settings readback mismatch')
        for name, fault, count, exception in [('nominal', False, 240, False), ('callback_faults', True, 80, False),
                                               ('exception_cleanup', False, 60, True)]:
            result, join = collect(world, args.output/name, 1, fault, count, exception)
            summary['cases'].append({'case': name, 'status': result['status']})
            summary['stage'] = name
            save(args.output/'summary.json', summary)
            require(result['status'] == 'PASS', f'{name} failed')
            if name == 'nominal':
                old_join = join
                replay_boundary_checks(join, args.output)
        before = world.id
        summary['stage'] = 'before_reload'
        save(args.output/'summary.json', summary)
        # Retire the sensor-session client before reset. Same-client native
        # reload crashed in recorded attempts; a clean client probe succeeded.
        world = None
        del client
        gc.collect()
        client = carla.Client('127.0.0.1', 2000)
        client.set_timeout(TIMEOUT)
        world = client.get_world()
        require(world.id == before, 'unexpected external world reset')
        world = client.reload_world(False)
        require(world.id != before, 'world episode did not change')
        result, new_join = collect(world, args.output/'after_reset', 2, count=80)
        old_packet = next(iter(old_join.records.values()))
        require(not new_join.accept(old_packet) and new_join.events[-1]['reason'] == 'old_epoch', 'old epoch accepted after actual reload')
        save(args.output/'reset.json', {'before_episode': before, 'after_episode': world.id,
             'before_run_id': old_join.run_id, 'after_run_id': new_join.run_id,
             'before_epoch': old_join.epoch, 'after_epoch': new_join.epoch,
             'old_callback_replay': new_join.events[-1], 'status': result['status'],
             'old_Actual_ECU_replay': 'NOT RUN'})
        summary['cases'].append({'case': 'after_reset', 'status': result['status']})
        require(result['status'] == 'PASS', 'after_reset failed')
        summary['status'] = 'PASS'
    except Exception:
        summary['error'] = traceback.format_exc()
    finally:
        try:
            if world is not None and original is not None:
                world.apply_settings(original)
                summary['settings_after'] = settings(world.get_settings())
                require(summary['settings_after'] == summary['settings_before'], 'settings not restored')
                summary['remaining_vehicles'] = [a.id for a in world.get_actors().filter('vehicle.*')]
                summary['remaining_sensors'] = [a.id for a in world.get_actors().filter('sensor.*')]
                require(not summary['remaining_vehicles'] and not summary['remaining_sensors'], 'actors remain')
        except Exception:
            summary['cleanup_error'] = traceback.format_exc()
            summary['status'] = 'FAIL'
        save(args.output/'summary.json', summary)
        print(json.dumps(summary, indent=2))
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())

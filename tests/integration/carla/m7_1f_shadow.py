#!/usr/bin/env python3
"""CARLA non-driving tick owner + native functional-clock shadow, no actuation."""
import argparse
import gc
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import queue
import select
import signal
import subprocess
import sys
import time
import traceback
import carla

DOMAIN = 0x4D3746554E435449
SCOPE = (1, 42, 7)  # trusted, isolated test scope; not a production EpochStore grant


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def require(value, why):
    if not value:
        raise RuntimeError(why)


def step_line(snapshot, scope=SCOPE):
    return 'STEP {} {} {} {} {} {:.17g} {:.17g}\n'.format(
        *scope, DOMAIN, snapshot.frame, snapshot.timestamp.elapsed_seconds,
        snapshot.timestamp.delta_seconds)


def exchange(proc, line):
    proc.stdin.write(line)
    proc.stdin.flush()
    require(select.select([proc.stdout], [], [], 10)[0], 'native shadow wall timeout')
    text = proc.stdout.readline()
    require(bool(text), 'native shadow exited without reply')
    return json.loads(text)


def capture(native, output):
    output.mkdir(parents=True, exist_ok=False)
    report = {'status': 'FAIL', 'mode': 'functional-shadow', 'driving': False,
              'native_inputs': 'stationary SIL actuator/electrical fixture; no CARLA wheel feed',
              'carla_apply_calls': 0, 'scope': SCOPE, 'clock_domain': DOMAIN,
              'ticks_planned': 320, 'world_dt_s': .01, 'camera_dt_s': .05,
              'injections': [], 'cleanup': {}}
    report['artifacts'] = {
        'native_sha256': hashlib.sha256(native.read_bytes()).hexdigest(),
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'native_sources': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted(Path(__file__).with_name('m7_1f').glob('*')) if p.is_file()}}
    client = carla.Client('127.0.0.1', 2000)
    client.set_timeout(10)
    world = client.get_world()
    original = world.get_settings()
    actors, sensors = [], []
    inbox = queue.Queue(maxsize=128)
    overflow = []
    proc = None
    packets = []

    def callback(stream):
        def receive(image):
            packet = {'stream': stream, 'frame': image.frame, 'sim_s': image.timestamp,
                      'arrival_ns': time.monotonic_ns(), 'width': image.width, 'height': image.height}
            try:
                inbox.put_nowait(packet)
            except queue.Full:
                overflow.append({'stream': stream, 'frame': image.frame})
        return receive

    def drain():
        while True:
            try:
                packets.append(inbox.get_nowait())
            except queue.Empty:
                return

    try:
        report['versions'] = [client.get_client_version(), client.get_server_version()]
        require(report['versions'] == ['0.9.16', '0.9.16'], 'version')
        require(not list(world.get_actors().filter('vehicle.*')) and not list(world.get_actors().filter('sensor.*')),
                'requires empty dedicated world')
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .01
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        settings.no_rendering_mode = False
        world.apply_settings(settings)
        observed = world.get_settings()
        require(observed.synchronous_mode and abs(observed.fixed_delta_seconds-.01) < 1e-8,
                'settings readback')
        report['map'] = world.get_map().name
        blueprint = world.get_blueprint_library().find('vehicle.lincoln.mkz_2020')
        ego = world.spawn_actor(blueprint, world.get_map().get_spawn_points()[0])
        actors.append(ego)
        ego.set_simulate_physics(False)
        ego.set_autopilot(False)
        report['ego'] = {'id': ego.id, 'blueprint': blueprint.id, 'physics': False}
        for stream, name in [('rgb', 'sensor.camera.rgb'), ('gt', 'sensor.camera.semantic_segmentation')]:
            blueprint = world.get_blueprint_library().find(name)
            for key, value in {'image_size_x': '800', 'image_size_y': '600', 'fov': '90',
                               'sensor_tick': '.05', 'lens_k': '0', 'lens_kcube': '0'}.items():
                blueprint.set_attribute(key, value)
            sensor = world.spawn_actor(blueprint, carla.Transform(carla.Location(x=1.5, z=1.7)),
                                       attach_to=ego, attachment_type=carla.AttachmentType.Rigid)
            actors.append(sensor)
            sensors.append(sensor)
            sensor.listen(callback(stream))
        with (output/'native.stderr').open('w') as errors, (output/'frames.jsonl').open('w') as frames:
            command = [str(native), '--functional-shadow', *map(str, SCOPE)]
            report['native_command'] = command
            proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=errors, text=True, bufsize=1)
            snapshot = world.get_snapshot()
            for index in range(report['ticks_planned']):
                if index in (150, 220):
                    before = time.monotonic_ns()
                    time.sleep(.1 if index == 150 else .25)
                    after = time.monotonic_ns()
                    paused = world.get_snapshot()
                    require(paused.frame == snapshot.frame and
                            paused.timestamp.elapsed_seconds == snapshot.timestamp.elapsed_seconds, 'pause changed observation')
                    report['injections'].append({'index': index, 'kind': 'slow-host' if index == 150 else 'pause',
                                                  'wall_begin_ns': before, 'wall_end_ns': after,
                                                  'frame': snapshot.frame, 'sim_s': snapshot.timestamp.elapsed_seconds})
                request = step_line(snapshot)
                begin = time.monotonic_ns()
                ack = exchange(proc, request)
                ack_ns = time.monotonic_ns()
                require(ack['status'] == 'SHADOW_BARRIER' and ack['driving'] is False and
                        ack['service_mask'] == 255 and ack['next_frame'] == snapshot.frame+1, 'native barrier')
                require(abs(ack['now_ns']-round(snapshot.timestamp.elapsed_seconds*1e9)) <= 1, 'native time changed')
                if index >= 150:
                    require(ack['armed_fixture'] and ack['release_mask'] == ack['credit_mask'] == 255 and
                            ack['actual_interval_fixture'], 'native fixture not ready')
                frame = world.tick(10)
                next_snapshot = world.get_snapshot()
                end = time.monotonic_ns()
                require(frame == next_snapshot.frame == ack['next_frame'], 'external tick/ambiguous response')
                require(abs(next_snapshot.timestamp.elapsed_seconds-snapshot.timestamp.elapsed_seconds-.01) < 1e-6, 'tick delta')
                frames.write(json.dumps({'index': index, 'request': request.strip(), 'frame': snapshot.frame,
                                         'sim_s': snapshot.timestamp.elapsed_seconds, 'platform_s': snapshot.timestamp.platform_timestamp,
                                         'begin_ns': begin, 'ack_ns': ack_ns, 'tick_end_ns': end,
                                         'tick_frame': frame, 'tick_sim_s': next_snapshot.timestamp.elapsed_seconds,
                                         'native': ack})+'\n')
                frames.flush()
                drain()
                snapshot = next_snapshot
            # Replay the last consumed input. A fatal reply must not authorize any
            # further world tick. This is deliberately after the nominal window.
            rejected = exchange(proc, request)
            require(rejected['status'] == 'FAIL' and rejected['next_frame'] is None, 'duplicate not rejected')
            report['negative'] = {'kind': 'duplicate-observation', 'request': request.strip(), 'reply': rejected,
                                  'frame_before': snapshot.frame, 'frame_after': world.get_snapshot().frame}
            require(report['negative']['frame_before'] == report['negative']['frame_after'], 'tick after fault')
            report['native_exit'] = proc.wait(timeout=10)
            require(report['native_exit'] == 1, 'negative process exit')
            report['ticks_completed'] = report['ticks_planned']
        time.sleep(.1)
        drain()
        require(not overflow, 'sensor queue overflow')
        report['status'] = 'SHADOW_COMPLETE'
    except Exception as error:
        report['error'] = str(error)
        report['traceback'] = traceback.format_exc()
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
            report['native_cleanup_exit'] = proc.wait(timeout=10)
        for sensor in sensors:
            try:
                sensor.stop()
            except Exception as error:
                report['cleanup'].setdefault('errors', []).append(str(error))
        for actor in reversed(actors):
            try:
                require(actor.destroy(), 'destroy returned false')
            except Exception as error:
                report['cleanup'].setdefault('errors', []).append(str(error))
        try:
            world.apply_settings(original)
            check = world.get_settings()
            report['cleanup']['settings_restored'] = check.synchronous_mode == original.synchronous_mode and check.fixed_delta_seconds == original.fixed_delta_seconds
            fresh = carla.Client('127.0.0.1', 2000)
            fresh.set_timeout(10)
            ids = {a.id for a in fresh.get_world().get_actors()}
            report['cleanup']['remaining_owned'] = [a.id for a in actors if a.id in ids]
        except Exception as error:
            report['cleanup'].setdefault('errors', []).append(str(error))
        drain()
        report['overflow'] = overflow
        save(output/'sensor-metadata.json', packets)
        if report['cleanup'].get('errors') or report['cleanup'].get('remaining_owned') or not report['cleanup'].get('settings_restored'):
            report['status'] = 'FAIL'
        save(output/'summary.json', report)
    return 0 if report['status'] == 'SHADOW_COMPLETE' else 1


def launch(server, native, output):
    output.mkdir(parents=True, exist_ok=False)
    require(not subprocess.check_output(['ss', '-H', '-ltn', 'sport = :2000 or sport = :2001 or sport = :2002'], text=True),
            'server ports already in use; no process touched')
    spec = importlib.util.spec_from_file_location('diagnostic_runner', Path(__file__).with_name('run_m7_1e.py'))
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    record = {'status': 'FAIL', 'readiness_errors': []}
    argv = ['./CarlaUE4.sh', '-RenderOffScreen', '-quality-level=Low', '-nosound', '-carla-rpc-port=2000',
            '-vulkan', '-stdout', '-FullStdOutLogOutput', '-log']
    record['server_command'] = argv
    record['server_directory'] = str(server)
    with (output/'server.log').open('w') as log:
        proc = subprocess.Popen(argv, cwd=server, env=dict(os.environ, VK_ICD_FILENAMES='/usr/share/vulkan/icd.d/nvidia_icd.json'),
                                stdout=log, stderr=subprocess.STDOUT, start_new_session=True, preexec_fn=helper.no_core)
        try:
            deadline = time.monotonic()+120
            ready = False
            while time.monotonic() < deadline and proc.poll() is None:
                try:
                    client = carla.Client('127.0.0.1', 2000)
                    client.set_timeout(5)
                    world = client.get_world()
                    ready = True
                    break
                except Exception as error:
                    record['readiness_errors'].append(str(error))
                    save(output/'process.json', record)
                    time.sleep(1)
            require(ready, 'server not ready')
            shipping = [pid for pid in helper.descendants(proc.pid)
                        if b'CarlaUE4-Linux-Shipping' in Path(f'/proc/{pid}/cmdline').read_bytes()]
            require(len(shipping) == 1, 'owned server identity')
            record['shipping_pid'] = shipping[0]
            del world, client
            gc.collect()
            command = [sys.executable, '-I', str(Path(__file__).resolve()), '--capture', '--native', str(native), '--output', str(output/'capture')]
            record['client_command'] = command
            with (output/'client.log').open('w') as client_log:
                completed = subprocess.run(command, stdout=client_log, stderr=subprocess.STDOUT, timeout=180)
                record['client_exit'] = completed.returncode
            record['status'] = 'OBSERVED'
        except Exception as error:
            record['error'] = str(error)
        finally:
            if proc.poll() is None:
                if 'shipping_pid' in record:
                    os.kill(record['shipping_pid'], signal.SIGTERM)
                else:
                    os.killpg(proc.pid, signal.SIGTERM)
                try:
                    record['server_exit'] = proc.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    record['forced_kill'] = True
                    os.killpg(proc.pid, signal.SIGKILL)
                    record['server_exit'] = proc.wait(timeout=5)
            else:
                record['server_exit'] = proc.returncode
            record['remaining_listeners'] = subprocess.check_output(['ss', '-H', '-ltnp', 'sport = :2000 or sport = :2001 or sport = :2002'], text=True)
            save(output/'process.json', record)
    return 0 if record['status'] == 'OBSERVED' and record.get('client_exit') == 0 else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', type=Path)
    parser.add_argument('--native', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--capture', action='store_true')
    args = parser.parse_args()
    if args.capture:
        return capture(args.native.resolve(), args.output.resolve())
    require(args.server is not None, '--server required for dedicated runner')
    return launch(args.server.resolve(), args.native.resolve(), args.output.resolve())


if __name__ == '__main__':
    raise SystemExit(main())

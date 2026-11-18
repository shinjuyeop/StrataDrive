#!/usr/bin/env python3
"""Isolated editor/packaged renderer memory and SDK smoke; no physical acceptance.

Use the existing three-actor catalog and 2K camera. Retain every callback byte;
no inference, native ECU, timing promotion or new quality evaluation occurs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import resource
import subprocess
import sys
import tarfile
import time
import traceback
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'tests/integration/perception'))
from carla_readiness_v1 import wait_ready
from renderer_shutdown_v1 import shutdown, allow_shutdown_tracer
from physical_ai.perception.carla_render_adapter_v1 import spawn_clone
from physical_ai.perception.scene_mailbox_v1 import ActorPose
from paired_scene_capture_v1 import environment


def digest(data):
    return hashlib.sha256(data).hexdigest()


class IdentityObserved(Exception):
    pass


def memory(pid):
    status = {}
    for line in Path(f'/proc/{pid}/status').read_text().splitlines():
        key, _, value = line.partition(':')
        if key.startswith(('Vm', 'Rss')):
            status[key] = value.strip()
    return dict(wall_ns=time.monotonic_ns(), process=status,
        meminfo=Path('/proc/meminfo').read_text(),
        memory_pressure=Path('/proc/pressure/memory').read_text(),
        io_pressure=Path('/proc/pressure/io').read_text(),
        vmstat=Path('/proc/vmstat').read_text())


def main(a):
    import carla
    out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    archive = ROOT/'docs/test-plan/evidence/m10_gc_recovery_v3/normal-300s-01/bounded-review.tar.gz'
    with tarfile.open(archive) as tar:
        catalog = json.load(tar.extractfile('capture/paired/catalog.json'))['catalog']
        editor = json.load(tar.extractfile('server.json'))['argv']['renderer']
    packaged = Path('/d/shin/stratadrive-tools/carla-0.9.16/server')
    project = Path(editor[1]).parent if a.kind == 'editor' else packaged/'CarlaUE4'
    argv = editor if a.kind == 'editor' else [str(project/'Binaries/Linux/CarlaUE4-Linux-Shipping'),
        'CarlaUE4', *[v for v in editor[2:] if not v.startswith('-Strata')]]
    assert Path('/sys/devices/system/cpu/intel_pstate/max_perf_pct').read_text().strip() == '100'
    running = subprocess.check_output(['ps', '-eo', 'comm='], text=True).splitlines()
    assert not any(v == 'UE4Editor' or v.startswith('CarlaUE4-Linux-') for v in running)
    ini = project/'Saved/Config/Linux/GameUserSettings.ini'
    original_ini = ini.read_bytes() if ini.exists() else None
    report = dict(scope=__doc__, kind=a.kind, status='STARTED', argv=argv,
        script_sha256=digest(Path(__file__).read_bytes()), executable_sha256=digest(Path(argv[0]).read_bytes()),
        source_archive_sha256=digest(archive.read_bytes()), source_catalog=catalog,
        native_started=False, model_calls=0, physical_acceptance=False,
        identity_only=a.identity_only, images=[], memory=[])
    if a.kind == 'editor':
        report['module_sha256'] = digest((project/'Plugins/Carla/Binaries/Linux/libUE4Editor-Carla.so').read_bytes())
    (out/'source.py').write_bytes(Path(__file__).read_bytes())
    (out/'declared.json').write_text(json.dumps(report, indent=2)+'\n')
    actors = []; world = sensor = process = None; received = queue.Queue(maxsize=64); overflow = []
    def callback(image):
        row = dict(frame=image.frame, source_ns=round(image.timestamp*1e9),
            received_ns=time.monotonic_ns(), width=image.width, height=image.height)
        try: received.put_nowait((row, bytes(image.raw_data)))
        except queue.Full: overflow.append(row)
    def drain():
        import numpy as np
        while not received.empty():
            row, data = received.get_nowait()
            assert (row['width'], row['height'], len(data)) == (2560, 1536, 2560*1536*4)
            rgb = np.frombuffer(data, np.uint8).reshape(1536, 2560, 4)[:, :, 2::-1].copy().tobytes()
            encoded = zlib.compress(data, 1); name = f"frame-{row['frame']}.bgra.zlib"
            (out/name).write_bytes(encoded)
            assert zlib.decompress(encoded) == data
            row.update(raw_sha256=digest(data), rgb_sha256=digest(rgb), stored_sha256=digest(encoded),
                stored_bytes=len(encoded), file=name)
            report['images'].append(row)
    def hook():
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0)); allow_shutdown_tracer()
    try:
        with (out/'renderer.log').open('x') as log:
            process = subprocess.Popen(['taskset', '-c', '6-7,14-15', *argv],
                cwd=packaged if a.kind == 'packaged' else ROOT,
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True, preexec_fn=hook)
            begin = time.monotonic_ns()
            report['readiness'] = wait_ready(sys.executable, 2300, out/'readiness.jsonl')
            report['ready_after_seconds'] = (time.monotonic_ns()-begin)/1e9
            report['memory'].append(memory(process.pid))
            client = carla.Client('127.0.0.1', 2300); client.set_timeout(10)
            report['client_version'] = client.get_client_version()
            world = client.get_world(); road = world.get_map()
            report['observed_map'] = dict(name=road.name, xodr_sha256=digest(road.to_opendrive().encode()))
            if a.identity_only:
                report['status'] = 'MAP_IDENTITY_OBSERVED_ONLY'
                raise IdentityObserved()
            if a.kind == 'packaged' and road.name != catalog['map']:
                remaining = 180-(time.monotonic_ns()-begin)/1e9
                if remaining <= 0: raise TimeoutError('target-map readiness within original180s')
                client.set_timeout(remaining)
                world = client.load_world(Path(catalog['map']).name)
                road = world.get_map(); client.set_timeout(10)
                report['loaded_map'] = dict(name=road.name, xodr_sha256=digest(road.to_opendrive().encode()),
                    world=world.id, ready_after_seconds=(time.monotonic_ns()-begin)/1e9)
                assert report['loaded_map']['ready_after_seconds'] <= 180
            assert road.name == catalog['map'] and digest(road.to_opendrive().encode()) == catalog['xodr_sha256']
            report['memory'].append(memory(process.pid))
            settings = world.get_settings(); settings.synchronous_mode = True; settings.fixed_delta_seconds = .05
            world.apply_settings(settings)
            weather = carla.WeatherParameters()
            for key, value in catalog['environment']['weather'].items(): setattr(weather, key, value)
            world.set_weather(weather)
            for light in world.get_actors().filter('traffic.traffic_light'):
                light.set_state(carla.TrafficLightState.Red); light.freeze(True)
            world.tick()
            assert environment(world) == catalog['environment']
            for i, item in enumerate(catalog['actors']):
                bp = world.get_blueprint_library().find(item['blueprint'])
                for key, value in item['attributes'].items():
                    if bp.has_attribute(key) and bp.get_attribute(key).is_modifiable: bp.set_attribute(key, value)
                pose = ActorPose(**{k: tuple(v) if isinstance(v, list) else v for k,v in item['initial_pose'].items()})
                actor = spawn_clone(world, carla, bp, road.get_spawn_points()[i+3], pose); actors.append(actor)
                assert actor.type_id == item['blueprint'] and dict(actor.attributes) == item['attributes']
            ego = actors[next(i for i,v in enumerate(catalog['actors']) if v['id'] == catalog['ego_id'])]
            bp = world.get_blueprint_library().find('sensor.camera.rgb')
            for key,value in dict(image_size_x='2560', image_size_y='1536', fov='90', sensor_tick='.1', enable_postprocess_effects='True').items():
                bp.set_attribute(key, value)
            pose = catalog['camera_relative']
            sensor = world.spawn_actor(bp, carla.Transform(carla.Location(pose['x'],pose['y'],pose['z']),
                carla.Rotation(pose['pitch'],pose['yaw'],pose['roll'])), attach_to=ego)
            report['camera_attributes'] = dict(sensor.attributes); sensor.listen(callback)
            capture_deadline = time.monotonic()+60
            for _ in range(48):
                if time.monotonic() >= capture_deadline: raise TimeoutError('60s finite camera smoke')
                started = time.monotonic(); world.tick(); drain()
                report['memory'].append(memory(process.pid))
                time.sleep(max(0, .05-(time.monotonic()-started)))
            sensor.stop(); time.sleep(.2); drain()
            assert len(report['images']) >= 20 and not overflow
            report['status'] = 'SDK_CAMERA_SMOKE_COMPLETE_NOT_INTEGRATED_ACCEPTANCE'
    except IdentityObserved:
        pass
    except Exception:
        report.update(status='FAIL', error=traceback.format_exc())
    finally:
        if sensor is not None:
            try: sensor.stop(); sensor.destroy()
            except RuntimeError: pass
        for actor in reversed(actors):
            try: actor.destroy()
            except RuntimeError: pass
        if a.kind == 'packaged' and world is not None and sensor is not None:
            # The stock synchronous server polls TickCue in its game-thread
            # loop. Release that wait only after ending cameras/actor use.
            try:
                before = world.get_snapshot(); begin = time.monotonic_ns()
                settings = world.get_settings(); settings.synchronous_mode = False
                world.apply_settings(settings)
                report['exit_unpark'] = dict(begin_ns=begin, end_ns=time.monotonic_ns(),
                    final_capture_frame=before.frame, synchronous_after=world.get_settings().synchronous_mode,
                    scope='post-capture shutdown only; no native authority or inference')
                assert report['exit_unpark']['synchronous_after'] is False
            except Exception:
                report['status'] = 'FAIL'; report['exit_unpark_error'] = traceback.format_exc()
        if process is not None:
            report['shutdown'] = shutdown(process, out/'shutdown', diagnostics=a.kind == 'editor')
            if report['shutdown'].get('forced_stop') or report['shutdown']['server_exit'] not in (0,130):
                report['status'] = 'FAIL'
        drain()
        if original_ini is None: ini.unlink(missing_ok=True)
        else: ini.write_bytes(original_ini)
        report['overflow'] = overflow
        (out/'result.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(dict(status=report['status'], images=len(report['images']),
            ready_after_seconds=report.get('ready_after_seconds'), error=report.get('error'))), flush=True)
    return 0 if report['status'] != 'FAIL' else 1


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kind', choices=('editor', 'packaged'), required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--identity-only', action='store_true')
    raise SystemExit(main(p.parse_args()))

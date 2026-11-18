#!/usr/bin/env python3
"""Bounded isolated engine GC diagnosis, not a physical/native acceptance run.

No renderer, inference or native ECU is started. Ordinary synchronous 5ms world
ticks advance 130 simulation seconds as fast as the SDK permits. The periodic
61.1s collector remains enabled; no collection is forced or skipped.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import socket
import subprocess
import sys
import tarfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tests/integration/perception'))
from carla_readiness_v1 import PROBE
from renderer_shutdown_v1 import shutdown, allow_shutdown_tracer


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def prepare(process, out, env, stopped):
    """Separate asset preparation, before the power lease or measured ticks."""
    deadline = time.monotonic()+600
    with (out/'readiness.jsonl').open('x') as log:
        while time.monotonic() < deadline:
            if stopped or process.poll() is not None:
                raise RuntimeError('asset preparation stopped')
            row = dict(begin_ns=time.monotonic_ns())
            try:
                probe = subprocess.run([sys.executable, '-c', PROBE, '2200'], env=env,
                    capture_output=True, text=True, timeout=min(5, max(.01, deadline-time.monotonic())))
                row.update(exit=probe.returncode, stdout=probe.stdout, stderr=probe.stderr)
            except subprocess.TimeoutExpired:
                row['timeout'] = True
            row['end_ns'] = time.monotonic_ns()
            log.write(json.dumps(row)+'\n'); log.flush()
            if row.get('exit') == 0:
                return json.loads(row['stdout'])
            time.sleep(.1)
    raise TimeoutError('separate 600s diagnostic asset preparation exhausted')


def main(args):
    import carla
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    archive = ROOT/'docs/test-plan/evidence/m10_gc_recovery_v3/normal-300s-01/bounded-review.tar.gz'
    with tarfile.open(archive) as tar:
        original = json.load(tar.extractfile('server.json'))['argv']['owner']
        catalog = json.load(tar.extractfile('capture/paired/catalog.json'))['catalog']
    argv = [a for a in original if not a.startswith('-StrataM')]
    options = ',gc.TimeBetweenPurgingPendingKillObjects 61.1,gc.MinDesiredObjectsPerSubTask '+str(args.gc_batch)
    if args.object_inventory:
        options += ',obj list'
    argv = [a+options if a.startswith('-ExecCmds=') else a for a in argv]
    argv += ['-LogCmds=LogGarbage Verbose']
    if args.no_visual_tags:
        if args.module_manifest is None:
            raise ValueError('visual tag candidate requires a declared module manifest')
        argv += ['-StrataM10NoVisualTags']
    module_path = Path(original[1]).parent/'Plugins/Carla/Binaries/Linux/libUE4Editor-Carla.so'
    module_sha = sha(module_path)
    if args.module_manifest is not None:
        declared_module = json.loads(args.module_manifest.read_text())
        if declared_module['module_path'] != str(module_path) or declared_module['module_sha256'] != module_sha:
            raise ValueError('installed candidate module identity')
    cpus = '2-4,10-12' if args.owner_cores == 3 else '2-5,10-13'
    argv = ['taskset', '-c', cpus, *argv]
    if subprocess.run(['pgrep', '-x', 'UE4Editor'], stdout=subprocess.DEVNULL).returncode == 0:
        raise RuntimeError('another engine is running')
    for port in (2200, 2201, 2202):
        with socket.socket() as guard:
            # An exited server can leave TIME_WAIT sockets. This still refuses
            # an active listener; it does not enable SO_REUSEPORT.
            guard.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            guard.bind(('127.0.0.1', port))
    cap = Path('/sys/devices/system/cpu/intel_pstate/max_perf_pct')
    if cap.read_text().strip() != '100':
        raise RuntimeError('expected restored host')
    helper = Path('/usr/local/sbin/stratadrive-m10-boost-lease')
    if sha(helper) != '92238599f138698e9346e6638ccac8b495da9fd50074c3bbbb8c52fd633947ae':
        raise RuntimeError('installed helper identity')
    ini = Path(original[1]).parent/'Saved/Config/Linux/GameUserSettings.ini'
    ini_bytes = ini.read_bytes()
    report = dict(scope=__doc__, argv=argv, script_sha256=sha(__file__),
        prior_archive_sha256=sha(archive), source_catalog=catalog,
        executable_sha256=sha(original[0]), runtime_modified_by_probe=False,
        milestone_closed=False, ticks=0, status='STARTED',
        preparation_limit_seconds=600, preparation_host_max_perf_pct=100)
    report.update(module_sha256=module_sha, no_visual_tags=args.no_visual_tags,
        module_manifest_sha256=sha(args.module_manifest) if args.module_manifest else None)
    (out/'source.py').write_bytes(Path(__file__).read_bytes())
    (out/'declared.json').write_text(json.dumps(report, indent=2)+'\n')
    stopped = []
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stopped.append(True))
    process = lease = anchor = None
    actors = []
    def hook():
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        allow_shutdown_tracer()
    try:
        with (out/'power-lease.jsonl').open('x') as lease_log:
            env = dict(os.environ, OMP_WAIT_POLICY='PASSIVE')
            env.pop('STRATADRIVE_M7_OWNER_KEY', None)
            with (out/'owner.log').open('x') as log:
                process = subprocess.Popen(argv, env=env, stdout=log, stderr=subprocess.STDOUT,
                    start_new_session=True, preexec_fn=hook)
                report['readiness'] = prepare(process, out, env, stopped)
                client = carla.Client('127.0.0.1', 2200); client.set_timeout(10)
                world = client.get_world()
                if hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest() != catalog['xodr_sha256']:
                    raise RuntimeError('map identity')
                settings = world.get_settings(); settings.synchronous_mode = True; settings.fixed_delta_seconds = .005
                settings.no_rendering_mode = True
                world.apply_settings(settings)
                library = world.get_blueprint_library()
                for item in catalog['actors']:
                    blueprint = library.find(item['blueprint'])
                    for key, value in item['attributes'].items():
                        if blueprint.has_attribute(key) and blueprint.get_attribute(key).is_modifiable:
                            blueprint.set_attribute(key, value)
                    pose = item['initial_pose']; q = pose['quaternion_xyzw']
                    yaw = math.degrees(math.atan2(2*(q[3]*q[2]+q[0]*q[1]), 1-2*(q[1]*q[1]+q[2]*q[2])))
                    position = list(pose['position_m']); position[2] += .25
                    actor = world.spawn_actor(blueprint, carla.Transform(carla.Location(*position), carla.Rotation(yaw=yaw)))
                    actor.set_simulate_physics(False); actors.append(actor)
                report['diagnostic_actor_ids'] = [a.id for a in actors]
                def vec(v): return [v.x, v.y, v.z]
                def rot(v): return [v.pitch, v.yaw, v.roll]
                def box(v): return dict(location=vec(v.location), extent=vec(v.extent), rotation=rot(v.rotation))
                geometry = dict(level_boxes=sorted([box(v) for v in world.get_level_bbs(carla.CityObjectLabel.Any)],
                    key=lambda x: json.dumps(x, sort_keys=True)),
                    environment=sorted([dict(name=v.name, kind=str(v.type), bounding_box=box(v.bounding_box),
                        location=vec(v.transform.location), rotation=rot(v.transform.rotation))
                        for v in world.get_environment_objects(carla.CityObjectLabel.Any)], key=lambda x:x['name']),
                    actors=[dict(type=a.type_id, attributes=dict(a.attributes), semantic_tags=list(a.semantic_tags)) for a in actors])
                (out/'scene-inventory.json').write_text(json.dumps(geometry, sort_keys=True, indent=2)+'\n')
                report['scene_inventory_sha256'] = sha(out/'scene-inventory.json')
                # End the user-owned anchor to release the root helper; never
                # signal a privileged PID or require another authentication.
                anchor = subprocess.Popen(['/bin/sleep', '600'])
                lease = subprocess.Popen(['sudo', '-n', '-k', str(helper), '--owner-pid', str(anchor.pid), '--seconds', '600'],
                    stdout=lease_log, stderr=subprocess.STDOUT)
                until = time.monotonic()+5
                while cap.read_text().strip() != '70':
                    if lease.poll() is not None or time.monotonic() >= until:
                        raise RuntimeError('bounded host lease did not start')
                    time.sleep(.05)
                report['begin_wall_ns'] = time.monotonic_ns()
                report['begin_utc_ns'] = time.time_ns()
                report['begin_frame'] = world.get_snapshot().frame
                until = time.monotonic()+300
                for i in range(26000):
                    if stopped or time.monotonic() >= until or cap.read_text().strip() != '70':
                        raise RuntimeError('diagnostic stopped or deadline/lease ended')
                    world.tick(); report['ticks'] = i+1
                    if (i+1) % 2000 == 0:
                        print(json.dumps(dict(ticks=i+1, elapsed_s=(time.monotonic_ns()-report['begin_wall_ns'])/1e9)), flush=True)
                report['end_wall_ns'] = time.monotonic_ns()
                report['end_utc_ns'] = time.time_ns()
                report['end_frame'] = world.get_snapshot().frame
                report['status'] = 'DIAGNOSTIC_COMPLETE_NOT_PHYSICAL_ACCEPTANCE'
    except Exception as error:
        report.update(status='DIAGNOSTIC_FAILED', error=repr(error))
    finally:
        try:
            if process is not None:
                report['shutdown'] = shutdown(process, out, diagnostics=True)
        finally:
            if anchor is not None and anchor.poll() is None:
                anchor.terminate(); anchor.wait(timeout=5)
            if lease is not None:
                lease.wait(timeout=10)
            ini.write_bytes(ini_bytes)
        report['host_max_perf_pct_after'] = int(cap.read_text())
        report['ini_restored'] = ini.read_bytes() == ini_bytes
        report['files'] = {str(p.relative_to(out)): dict(bytes=p.stat().st_size, sha256=sha(p))
            for p in out.rglob('*') if p.is_file()}
        (out/'result.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(dict(status=report['status'], ticks=report['ticks'], host_max_perf_pct_after=report['host_max_perf_pct_after'])), flush=True)
    return 0 if report['status'] == 'DIAGNOSTIC_COMPLETE_NOT_PHYSICAL_ACCEPTANCE' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--owner-cores', type=int, choices=(3, 4), default=3)
    parser.add_argument('--gc-batch', type=int, choices=(32, 128, 1024), default=128)
    parser.add_argument('--object-inventory', action='store_true')
    parser.add_argument('--module-manifest', type=Path)
    parser.add_argument('--no-visual-tags', action='store_true')
    raise SystemExit(main(parser.parse_args()))

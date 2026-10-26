#!/usr/bin/env python3
"""Prepare one rendered scene until observed shader/DF queues remain empty.

Uses same-host debugger observations only for diagnostic readiness. They are not
vehicle source timestamps, native deadlines, or proof of general crash safety.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import threading
import time
import traceback

import carla
from m7_1j_render_probe import settings


def queues_empty(q):
    direct = ("distance_tasks", "shader_outstanding", "shader_external", "shader_queue")
    keys = direct + ("shader_finalize_allocated", "shader_finalize_free",
                     "shader_maps_allocated", "shader_maps_free")
    return (all(type(q.get(k)) is int and q[k] >= 0 for k in keys)
            and all(q[k] == 0 for k in direct)
            and q["shader_finalize_allocated"] == q["shader_finalize_free"]
            and q["shader_maps_allocated"] == q["shader_maps_free"])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--debugger-dir", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--expected-version", required=True)
    p.add_argument("--port", type=int, default=2200)
    p.add_argument("--timeout", type=float, default=1200)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    r = dict(status="FAIL", scope="rendered physics-disabled scene readiness; no actuation/AI",
             queue_observations=[], ticks=0)
    original = world = None
    actors, sensors = [], []
    touched = False
    images = Counter()
    lock = threading.Lock()
    started = time.monotonic()

    def callback(name):
        def consume(image):
            with lock:
                images[name] += 1
        return consume

    try:
        if "Engine is initialized. Leaving FEngineLoop::Init()" not in (args.debugger_dir / "gdb.log").read_text(errors="replace"):
            raise RuntimeError("engine initialization not yet observed")
        client = carla.Client("127.0.0.1", args.port)
        client.set_timeout(20)
        r["client_version"] = client.get_client_version()
        r["server_version"] = client.get_server_version()
        if not r["client_version"] == r["server_version"] == args.expected_version:
            raise RuntimeError("identity mismatch")
        world = client.get_world()
        r["map"] = world.get_map().name
        if r["map"].rsplit("/", 1)[-1] != "Town03_Opt" or list(world.get_actors().filter("vehicle.*")):
            raise RuntimeError("dedicated empty Town03_Opt required")
        original = world.get_settings()
        r["settings_before"] = settings(original)
        desired = world.get_settings()
        desired.synchronous_mode, desired.fixed_delta_seconds = True, .01
        desired.no_rendering_mode = False
        desired.substepping, desired.max_substep_delta_time, desired.max_substeps = True, .01, 10
        touched = True
        world.apply_settings(desired)
        r["settings_during"] = settings(world.get_settings())
        if r["settings_during"] != settings(desired):
            raise RuntimeError("settings readback mismatch")
        bp = world.get_blueprint_library().find("vehicle.lincoln.mkz_2020")
        ego = world.spawn_actor(bp, world.get_map().get_spawn_points()[0])
        actors.append(ego)
        ego.set_simulate_physics(False)  # Never register a fresh ego with TM.
        for name, kind in (("rgb", "sensor.camera.rgb"), ("gt", "sensor.camera.semantic_segmentation")):
            bp = world.get_blueprint_library().find(kind)
            for k, v in (("image_size_x", "320"), ("image_size_y", "240"), ("fov", "90"), ("sensor_tick", "0.05")):
                bp.set_attribute(k, v)
            sensor = world.spawn_actor(bp, carla.Transform(carla.Location(x=1.6, z=1.7), carla.Rotation(pitch=-8)), attach_to=ego)
            actors.append(sensor)
            sensors.append(sensor)
            sensor.listen(callback(name))
        r["owned_actor_ids"] = [a.id for a in actors]
        r["scene_started_monotonic"] = time.monotonic()
        zeros, previous_frame, seen_seq = [], None, None
        while time.monotonic() - started < args.timeout:
            frame = world.tick(20)
            snap = world.get_snapshot()
            if frame != snap.frame or (previous_frame is not None and frame != previous_frame + 1):
                raise RuntimeError("frame/snapshot discontinuity")
            if abs(snap.timestamp.delta_seconds - .01) > 1e-6:
                raise RuntimeError("simulation dt mismatch")
            previous_frame = frame
            r["ticks"] += 1
            r["last_original_state"] = dict(frame=frame, elapsed_seconds=snap.timestamp.elapsed_seconds)
            try:
                state = json.loads((args.debugger_dir / "gdb-event.json").read_text())
                q = json.loads((args.debugger_dir / "latest-queues.json").read_text())
            except json.JSONDecodeError:
                # Debugger files can be observed during a write. A partial
                # observation never contributes to readiness.
                continue
            if state["stops"] or "inferior_exit_code" in state:
                raise RuntimeError("debugger stopped or inferior exited")
            if q["seq"] == seen_seq:
                continue
            seen_seq = q["seq"]
            if state["started_monotonic"] + q["wall_s"] < r["scene_started_monotonic"]:
                continue  # Ignore pre-map/pre-camera/stale observations.
            r["queue_observations"].append(q)
            zeros = zeros + [q] if queues_empty(q) else []
            with lock:
                received = dict(images)
            if len(zeros) >= 2 and zeros[-1]["wall_s"] - zeros[-2]["wall_s"] >= 9.5 and min(received.get(k, 0) for k in ("rgb", "gt")) >= 10:
                r["ready_samples"] = zeros[-2:]
                r["received_callback_counts"] = received
                r["status"] = "PASS"
                break
        else:
            raise TimeoutError("diagnostic preparation budget exceeded; not a native deadline")
    except Exception:
        r["error"] = traceback.format_exc()
    finally:
        try:
            if world is not None:
                client.set_timeout(5)
                for sensor in sensors:
                    if sensor.is_alive and sensor.is_listening:
                        sensor.stop()
                r["destroy_returns"] = {a.id: a.destroy() for a in reversed(actors) if a.is_alive}
                if actors:
                    world.tick(5)
                    snap, registry = world.get_snapshot(), world.get_actors()
                    r["remaining_owned"] = [a.id for a in actors if registry.find(a.id) or snap.find(a.id)]
                    if r["remaining_owned"] or not all(r["destroy_returns"].values()):
                        raise RuntimeError("actor cleanup failed")
                if touched:
                    world.apply_settings(original)
                    r["settings_after"] = settings(world.get_settings())
                    if r["settings_after"] != r["settings_before"]:
                        raise RuntimeError("settings restore failed")
        except Exception:
            r["cleanup_error"] = traceback.format_exc()
            r["status"] = "FAIL"
        r["elapsed_wall_s"] = time.monotonic() - started
        (args.output / "result.json").write_text(json.dumps(r, indent=2) + "\n")
        print(json.dumps({k: v for k, v in r.items() if k not in ("queue_observations", "ready_samples")}))
    return 0 if r["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

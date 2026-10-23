#!/usr/bin/env python3
"""Non-driving CARLA 0.9.16 connection and ego lifecycle smoke; no M6 imports."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
import traceback

import carla


class InjectedLifecycleError(Exception):
    pass


def settings_snapshot(settings):
    return {name: getattr(settings, name) for name in (
        "synchronous_mode", "fixed_delta_seconds", "no_rendering_mode",
        "substepping", "max_substep_delta_time", "max_substeps")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    # Never overwrite an earlier attempt, including a failed attempt.
    args.output.mkdir(parents=True, exist_ok=False)
    result = {"started_utc": datetime.now(timezone.utc).isoformat(),
              "python": sys.version, "executable": sys.executable,
              "carla_module": carla.__file__, "endpoint": ["127.0.0.1", args.port],
              "mode": "NON_DRIVING; ego physics disabled; no control API",
              "cases": [], "status": "FAIL"}
    started = time.monotonic()
    world = original = None
    owned = []
    try:
        client = carla.Client("127.0.0.1", args.port)
        client.set_timeout(10.0)
        result["client_version"] = client.get_client_version()
        result["server_version"] = client.get_server_version()
        if result["client_version"] != "0.9.16" or result["server_version"] != "0.9.16":
            raise RuntimeError("exact client/server version mismatch")
        world = client.get_world()
        result["map"] = world.get_map().name
        result["initial_vehicle_ids"] = [a.id for a in world.get_actors().filter("vehicle.*")]
        if result["initial_vehicle_ids"]:
            raise RuntimeError("requires a dedicated server without existing vehicles")
        original = world.get_settings()
        result["settings_before"] = settings_snapshot(original)
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        settings.substepping = True
        settings.max_substep_delta_time = 0.01
        settings.max_substeps = 10
        world.apply_settings(settings)
        result["settings_during"] = settings_snapshot(world.get_settings())
        if result["settings_during"] != settings_snapshot(settings):
            raise RuntimeError("settings readback mismatch")
        blueprint = world.get_blueprint_library().find("vehicle.lincoln.mkz_2020")
        blueprint.set_attribute("role_name", "stratadrive_m7_1a_ego")
        spawn = world.get_map().get_spawn_points()[0]
        result["blueprint"] = blueprint.id
        result["spawn"] = {"x": spawn.location.x, "y": spawn.location.y,
                           "z": spawn.location.z, "pitch": spawn.rotation.pitch,
                           "yaw": spawn.rotation.yaw, "roll": spawn.rotation.roll}
        for inject in (False, True):
            case = {"name": "injected_exception_cleanup" if inject else "normal_cleanup",
                    "status": "FAIL"}
            result["cases"].append(case)
            try:
                ego = world.spawn_actor(blueprint, spawn)
                owned.append(ego)
                case["actor_id"] = ego.id
                ego.set_simulate_physics(False)
                ego.set_autopilot(False)
                frame = world.tick(10.0)
                if world.get_actor(ego.id) is None:
                    raise RuntimeError("spawned ego absent")
                case["observed_frame"] = frame
                velocity = ego.get_velocity()
                case["velocity_mps"] = [velocity.x, velocity.y, velocity.z]
                case["alive_before_cleanup"] = ego.is_alive
                if inject:
                    raise InjectedLifecycleError("deliberate exception after ego creation")
            except InjectedLifecycleError as exc:
                case["expected_exception"] = str(exc)
            finally:
                if owned:
                    actor = owned[-1]
                    case["destroy_return"] = actor.destroy()
                    case["cleanup_observations"] = []
                    # get_actor(id) can return a cached actor description after
                    # destruction. Use current episode IDs and snapshot instead.
                    for _ in range(10):
                        frame = world.tick(10.0)
                        snapshot = world.get_snapshot()
                        present = world.get_actors().find(actor.id) is not None
                        in_snapshot = snapshot.find(actor.id) is not None
                        case["cleanup_observations"].append({
                            "tick_frame": frame, "snapshot_frame": snapshot.frame,
                            "registry_present": present, "snapshot_present": in_snapshot})
                        if not present and not in_snapshot:
                            break
                    case["present_after_cleanup"] = present or in_snapshot
                    if not case["present_after_cleanup"]:
                        owned.pop()
                    if not case["destroy_return"] or case["present_after_cleanup"]:
                        raise RuntimeError("ego cleanup failed")
            case["status"] = "PASS"
        result["remaining_vehicle_ids"] = [a.id for a in world.get_actors().filter("vehicle.*")]
        if result["remaining_vehicle_ids"]:
            raise RuntimeError("unexpected vehicle remains")
        result["status"] = "PASS"
    except Exception:
        result["error"] = traceback.format_exc()
    finally:
        try:
            for actor in owned:
                if actor.is_alive:
                    actor.destroy()
            if world is not None and original is not None:
                world.apply_settings(original)
                result["settings_after"] = settings_snapshot(world.get_settings())
                if result["settings_after"] != result["settings_before"]:
                    raise RuntimeError("world settings restoration mismatch")
        except Exception:
            result["cleanup_error"] = traceback.format_exc()
            result["status"] = "FAIL"
        result["elapsed_wall_s"] = time.monotonic() - started
        (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

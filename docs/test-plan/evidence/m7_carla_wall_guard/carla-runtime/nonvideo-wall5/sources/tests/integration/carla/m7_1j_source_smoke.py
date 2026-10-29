#!/usr/bin/env python3
"""Non-driving source-build smoke. No controller/actuation or M6 imports."""
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
import traceback

import carla


FIELDS = ("synchronous_mode", "fixed_delta_seconds", "no_rendering_mode",
          "substepping", "max_substep_delta_time", "max_substeps")


def settings(s):
    return {key: getattr(s, key) for key in FIELDS}


class InjectedError(Exception):
    pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--port", type=int, default=2200)
    parser.add_argument("--expected-map", default="Town10HD_Opt")
    parser.add_argument("--no-rendering", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    result = dict(started_utc=datetime.now(timezone.utc).isoformat(),
                  executable=sys.executable, carla_module=carla.__file__,
                  endpoint=["127.0.0.1", args.port], expected_version=args.expected_version,
                  mode="NON_DRIVING; ego physics disabled; no apply_control",
                  status="FAIL", cases=[])
    start = time.monotonic()
    world = original = None
    settings_touched = False
    owned = []
    trace = []
    try:
        client = carla.Client("127.0.0.1", args.port)
        client.set_timeout(20.0)
        result["client_version"] = client.get_client_version()
        result["server_version"] = client.get_server_version()
        if not (result["client_version"] == result["server_version"] == args.expected_version):
            raise RuntimeError("pinned source client/server version mismatch")
        world = client.get_world()
        result["map"] = world.get_map().name
        result["expected_map"] = args.expected_map
        if result["map"].rsplit("/", 1)[-1] != args.expected_map:
            raise RuntimeError("unexpected map; do not silently accept default-map fallback")
        result["initial_vehicle_ids"] = [a.id for a in world.get_actors().filter("vehicle.*")]
        if result["initial_vehicle_ids"]:
            raise RuntimeError("requires isolated server without pre-existing vehicles")
        original = world.get_settings()
        result["settings_before"] = settings(original)
        # Startup UCarlaSettings and FEpisodeSettings are separate in 0.9.16.
        # Do not infer the Episode readback from the startup INI's rendering flag.
        result["requested_no_rendering"] = args.no_rendering
        desired = world.get_settings()
        if args.no_rendering:
            desired.no_rendering_mode = True
        desired.synchronous_mode = True
        desired.fixed_delta_seconds = .01
        desired.substepping = True
        desired.max_substep_delta_time = .01
        desired.max_substeps = 10
        settings_touched = True
        world.apply_settings(desired)
        result["settings_during"] = settings(world.get_settings())
        if result["settings_during"] != settings(desired):
            raise RuntimeError("world settings readback mismatch")
        blueprint = world.get_blueprint_library().find("vehicle.lincoln.mkz_2020")
        blueprint.set_attribute("role_name", "stratadrive_source_smoke")
        spawn = world.get_map().get_spawn_points()[0]
        result["blueprint"] = blueprint.id
        result["spawn"] = {key: getattr(spawn.location, key) for key in ("x", "y", "z")}

        for inject in (False, True):
            case = dict(name="injected_exception_cleanup" if inject else "normal_cleanup", status="FAIL")
            result["cases"].append(case)
            ego = None
            try:
                ego = world.spawn_actor(blueprint, spawn)
                owned.append(ego)
                case["actor_id"] = ego.id
                ego.set_simulate_physics(False)
                # Fresh spawn is never registered with Traffic Manager. In 0.9.16
                # even set_autopilot(False) constructs a TM client/server.
                previous = None
                deltas = []
                ticks = 2 if inject else 100
                for index in range(ticks):
                    before = time.monotonic_ns()
                    frame = world.tick(20.0)
                    snapshot = world.get_snapshot()
                    after = time.monotonic_ns()
                    t = snapshot.timestamp
                    trace.append(dict(case=case["name"], index=index, tick_frame=frame,
                                      snapshot_frame=snapshot.frame, elapsed_seconds=t.elapsed_seconds,
                                      delta_seconds=t.delta_seconds, platform_timestamp=t.platform_timestamp,
                                      request_monotonic_ns=before, received_monotonic_ns=after))
                    if frame != snapshot.frame or snapshot.find(ego.id) is None:
                        raise RuntimeError("tick/snapshot/ego mismatch")
                    if abs(t.delta_seconds - .01) > 1e-6:
                        raise RuntimeError("snapshot fixed delta is not 10ms")
                    if previous is not None:
                        delta = t.elapsed_seconds - previous[1]
                        deltas.append(delta)
                        if frame != previous[0] + 1 or abs(delta - .01) > 1e-6:
                            raise RuntimeError("frame gap or simulation timestamp increment mismatch")
                    previous = (frame, t.elapsed_seconds)
                case["ticks"] = ticks
                case["timestamp_increment_min_s"] = min(deltas)
                case["timestamp_increment_max_s"] = max(deltas)
                velocity = ego.get_velocity()
                case["velocity_m_s"] = [velocity.x, velocity.y, velocity.z]
                if any(abs(v) > 1e-6 for v in case["velocity_m_s"]):
                    raise RuntimeError("physics-disabled ego moved")
                if inject:
                    raise InjectedError("deliberate post-spawn lifecycle exception")
            except InjectedError as exc:
                case["expected_exception"] = str(exc)
            finally:
                if ego is not None:
                    case["destroy_return"] = ego.destroy()
                    case["cleanup_observations"] = []
                    for _ in range(10):
                        frame = world.tick(20.0)
                        snapshot = world.get_snapshot()
                        present = world.get_actors().find(ego.id) is not None
                        in_snapshot = snapshot.find(ego.id) is not None
                        case["cleanup_observations"].append(dict(
                            tick_frame=frame, snapshot_frame=snapshot.frame,
                            registry_present=present, snapshot_present=in_snapshot))
                        if not present and not in_snapshot:
                            break
                    if not case["destroy_return"] or present or in_snapshot:
                        raise RuntimeError("owned actor cleanup failed")
                    owned.remove(ego)
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
                if settings_touched:
                    world.apply_settings(original)
                result["settings_after"] = settings(world.get_settings())
                if result["settings_after"] != result["settings_before"]:
                    raise RuntimeError("world settings restoration mismatch")
        except Exception:
            result["cleanup_error"] = traceback.format_exc()
            result["status"] = "FAIL"
        result["elapsed_wall_s"] = time.monotonic() - start
        (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        if trace:
            with (args.output / "ticks.csv").open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(trace[0]))
                writer.writeheader()
                writer.writerows(trace)
        print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

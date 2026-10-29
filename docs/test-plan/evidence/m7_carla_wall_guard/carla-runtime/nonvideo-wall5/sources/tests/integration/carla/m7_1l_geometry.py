#!/usr/bin/env python3
"""Read-only, frozen-frame rest geometry under multiple explicit INIT poses."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import traceback

import carla

FIELDS = ("synchronous_mode", "fixed_delta_seconds", "no_rendering_mode",
          "substepping", "max_substep_delta_time", "max_substeps")
POSES = ((0, 0, 0), (90, 0, 0), (-90, 0, 0), (180, 0, 0), (37, 7, -4))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--port", type=int, default=2200)
    p.add_argument("--expected-version", default="294096e-dirty")
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    r = dict(status="FAIL", started_utc=datetime.now(timezone.utc).isoformat(),
             mode="frozen-frame geometry; physics enabled; no actuation/tick while bound",
             snapshots=[], normal_driving_enabled=False, pressure_calibration="UNAVAILABLE")
    world = original = actor = None
    bound = False
    session = "0"
    run = ""
    events = []
    try:
        client = carla.Client("127.0.0.1", args.port)
        client.set_timeout(10)
        r["client_version"], r["server_version"] = client.get_client_version(), client.get_server_version()
        assert r["client_version"] == r["server_version"] == args.expected_version
        world = client.get_world()
        assert world.get_map().name.endswith("/Town03_Opt")
        assert not list(world.get_actors().filter("vehicle.*"))
        original = world.get_settings()
        r["original_settings"] = {name: getattr(original, name) for name in FIELDS}
        settings = world.get_settings()
        settings.synchronous_mode, settings.fixed_delta_seconds = True, .01
        settings.no_rendering_mode, settings.substepping = True, True
        settings.max_substep_delta_time, settings.max_substeps = .01, 10
        world.apply_settings(settings)
        world.tick()  # Preparation only, before any bound ego exists.

        def rpc(op, **data):
            req = dict(op=op, owner_key=os.environ["STRATADRIVE_M7_OWNER_KEY"], **data)
            if op not in ("bind", "describe"):
                req.update(session=session, run=run)
            reply = json.loads(client.m7_nodrive(json.dumps(req)))
            events.append(dict(request={k: v for k, v in req.items() if k != "owner_key"}, response=reply))
            return reply

        bp = world.get_blueprint_library().find("vehicle.lincoln.mkz_2020")
        bp.set_attribute("role_name", "m7_rest_geometry_probe")
        start = world.get_map().get_spawn_points()[0].location
        for yaw, pitch, roll in POSES:
            initial = carla.Transform(carla.Location(start.x, start.y, start.z+3),
                                      carla.Rotation(pitch=pitch, yaw=yaw, roll=roll))
            actor = world.spawn_actor(bp, initial)
            binding = rpc("bind", actor=str(actor.id))
            bound = binding["locked"]
            session, run = binding["session"], binding["run"]
            assert binding["ok"] and binding["physics"]["nodrive"]
            first, second = rpc("geometry"), rpc("geometry")
            assert first["ok"] and first == second
            assert first["frame"] == binding["frame"]
            assert first["geometry"]["valid"] and first["geometry"]["inputs_zero"]
            # Public field is COMNudge, not the absolute PhysX local COM.
            public = actor.get_physics_control()
            sample = dict(init_pose=dict(yaw_deg=yaw, pitch_deg=pitch, roll_deg=roll),
                          binding=binding, snapshot=first,
                          public_physics=dict(mass_kg=public.mass,
                              center_of_mass_field=[public.center_of_mass.x, public.center_of_mass.y, public.center_of_mass.z],
                              wheels=[dict(radius_cm=w.radius, max_brake_nm=w.max_brake_torque,
                                           max_steer_deg=w.max_steer_angle) for w in public.wheels]))
            r["snapshots"].append(sample)
            if (yaw, pitch, roll) == POSES[-1]:
                reset = rpc("reset")
                stale = rpc("geometry")
                r["reset_geometry_guard"] = dict(reset=reset, rejected=stale)
                assert reset["ok"] and reset["latched"]
                assert not stale["ok"] and stale["reason"] == "geometry_generation"
                assert stale["frame"] == first["frame"]
            closed = rpc("close")
            assert closed["ok"] and not closed["registry_actor_present"]
            bound, actor = False, None
        r["status"] = "PASS_READBACK_ONLY"
    except Exception:
        r["error"] = traceback.format_exc()
    finally:
        try:
            if bound:
                closed = rpc("close")
                if not closed["ok"]:
                    raise RuntimeError("bound ego close failed")
                actor = None
            if actor is not None:
                actor.destroy()
            if original is not None:
                world.apply_settings(original)
                r["restored_settings"] = {name: getattr(world.get_settings(), name) for name in FIELDS}
                r["remaining_vehicle_ids"] = [a.id for a in world.get_actors().filter("vehicle.*")]
                assert r["restored_settings"] == r["original_settings"] and not r["remaining_vehicle_ids"]
        except Exception:
            r["cleanup_error"] = traceback.format_exc()
            r["status"] = "FAIL"
        (args.output/"result.json").write_text(json.dumps(r, indent=2)+"\n")
        (args.output/"rpc-events.json").write_text(json.dumps(events, indent=2)+"\n")
    print(json.dumps(dict(status=r["status"], poses=len(r["snapshots"]), output=str(args.output))))
    return 0 if r["status"] == "PASS_READBACK_ONLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""One RGB/instance pair per predeclared placement; no model or control imports."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import sys
import time
import traceback
import carla


def pose(transform):
    return {
        group: {key: getattr(getattr(transform, group), key) for key in keys}
        for group, keys in (
            ("location", ("x", "y", "z")),
            ("rotation", ("pitch", "yaw", "roll")),
        )
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--partition", choices=("development", "holdout"), required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--port", type=int, default=2300)
    a = p.parse_args()
    plan = json.loads(a.plan.read_text())
    part = plan["partitions"][a.partition]
    if (
        plan["schema"] != "m10-quality-plan-v1"
        or plan["world_step_ns"] != 10_000_000
        or plan["sensor_tick_seconds"] != 0
        or len(part["cases"]) != 81
        or plan["settle_ticks"] != 40
        or plan["capture_ticks"] != 10
        or plan["selected_capture_tick"] != 5
    ):
        raise ValueError("capture plan/executable mismatch")
    a.output.mkdir(parents=True, exist_ok=False)
    report = dict(
        schema="m10-quality-capture-v1",
        status="FAIL",
        partition=a.partition,
        plan_sha256=hashlib.sha256(a.plan.read_bytes()).hexdigest(),
        epoch=1,
        clock_instance=None,
        frames=[],
        scenes=[],
        cleanup_errors=[],
        overflow=[],
        camera=dict(width=640, height=384, fov_degrees=90, calibration_revision=1),
        selection="one paired original frame at capture tick5 after40 settling ticks; sensors acquire every world tick; not20Hz timing qualification",
    )
    world = original = None
    sensors, scene_actors = [], []
    queues = {k: queue.Queue(maxsize=128) for k in ("rgb", "instance")}

    def callback(name):
        def collect(image):
            try:
                queues[name].put_nowait(image)
            except queue.Full:
                report["overflow"].append([name, image.frame])

        return collect

    def destroy_scene():
        for actor in reversed(scene_actors):
            if not actor.destroy():
                raise ValueError(f"scene actor destroy failed {actor.id}")
        scene_actors.clear()

    try:
        client = carla.Client("127.0.0.1", a.port)
        client.set_timeout(20)
        report["client_version"] = client.get_client_version()
        report["server_version"] = client.get_server_version()
        if (
            report["client_version"] != "294096e-dirty"
            or report["server_version"] != "294096e-dirty"
        ):
            raise ValueError("SDK/server identity")
        world = client.get_world()
        report["clock_instance"] = world.id
        if world.get_map().name.rsplit("/", 1)[-1] != plan["map"]:
            raise ValueError("map mismatch")
        if list(world.get_actors().filter("vehicle.*")) or list(
            world.get_actors().filter("sensor.*")
        ):
            raise ValueError("requires isolated empty server")
        library = world.get_blueprint_library()
        inventory = {bp.id for bp in library}
        required = {x["blueprint"] for c in part["cases"] for x in c["actors"]}
        report["required_blueprints"] = sorted(required)
        report["available_vehicle_blueprints"] = sorted(
            x for x in inventory if x.startswith("vehicle.")
        )
        if required - inventory:
            raise ValueError(
                f"required blueprint missing: {sorted(required - inventory)}"
            )
        original = world.get_settings()
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.01
        settings.no_rendering_mode = False
        settings.substepping = True
        settings.max_substep_delta_time = 0.01
        settings.max_substeps = 10
        world.apply_settings(settings)
        applied = world.get_settings()
        if (
            not applied.synchronous_mode
            or applied.no_rendering_mode
            or abs(applied.fixed_delta_seconds - 0.01) > 1e-9
        ):
            raise ValueError("world readback")
        base = world.get_map().get_spawn_points()[part["spawn_point_index"]]
        report["base_pose"] = pose(base)
        report["xodr_sha256"] = hashlib.sha256(
            world.get_map().to_opendrive().encode()
        ).hexdigest()
        yaw = math.radians(base.rotation.yaw)

        def transform(forward, right, z, angle=0):
            return carla.Transform(
                carla.Location(
                    x=base.location.x + forward * math.cos(yaw) - right * math.sin(yaw),
                    y=base.location.y + forward * math.sin(yaw) + right * math.cos(yaw),
                    z=base.location.z + z,
                ),
                carla.Rotation(yaw=base.rotation.yaw + angle),
            )

        camera_pose = transform(0, 0, part["camera_height_m"])
        camera_pose.rotation.pitch = part["camera_pitch_degrees"]
        report["camera_pose"] = pose(camera_pose)
        report["sensor_attributes"] = {}
        for stream, kind in (
            ("rgb", "sensor.camera.rgb"),
            ("instance", "sensor.camera.instance_segmentation"),
        ):
            bp = library.find(kind)
            for key, val in (
                ("image_size_x", "640"),
                ("image_size_y", "384"),
                ("fov", "90"),
                ("sensor_tick", "0"),
            ):
                bp.set_attribute(key, val)
            if stream == "rgb":
                bp.set_attribute("enable_postprocess_effects", "True")
            sensor = world.spawn_actor(bp, camera_pose)
            sensors.append(sensor)
            report["sensor_attributes"][stream] = dict(sensor.attributes)
            sensor.listen(callback(stream))
        previous = None

        def tick():
            nonlocal previous
            number = world.tick(20)
            snapshot = world.get_snapshot()
            if (
                snapshot.frame != number
                or (previous is not None and number != previous + 1)
                or abs(snapshot.timestamp.delta_seconds - 0.01) > 1e-6
            ):
                raise ValueError("tick ownership/period")
            previous = number
            return number, snapshot.timestamp.elapsed_seconds

        report["weather_readback"] = {}
        for case in part["cases"]:
            destroy_scene()
            weather = getattr(carla.WeatherParameters, case["weather"])
            world.set_weather(weather)
            actual = world.get_weather()
            report["weather_readback"][case["weather"]] = {
                k: getattr(actual, k)
                for k in (
                    "cloudiness",
                    "precipitation",
                    "precipitation_deposits",
                    "sun_altitude_angle",
                    "sun_azimuth_angle",
                    "fog_density",
                )
            }
            entries = []
            for index, item in enumerate(case["actors"]):
                bp = library.find(item["blueprint"])
                if bp.has_attribute("is_invincible"):
                    bp.set_attribute("is_invincible", "true")
                # Spawn in separate free space, then place explicitly with physics disabled.
                actor = world.spawn_actor(bp, transform(-5 - index * 8, 0, 3))
                scene_actors.append(actor)
                actor.set_simulate_physics(False)
                actor.set_transform(
                    transform(
                        item["forward_m"],
                        item["right_m"],
                        item["z_offset_m"],
                        item["yaw_offset_degrees"],
                    )
                )
                entries.append(
                    dict(
                        actor_id=actor.id,
                        blueprint=actor.type_id,
                        class_id=item["class_id"],
                        role=item["role"],
                        pose=pose(actor.get_transform()),
                    )
                )
            for q in queues.values():
                while not q.empty():
                    q.get_nowait()
            for _ in range(plan["settle_ticks"]):
                tick()
            # All discarded captures are explicit sensor settling; chosen frame is fixed before any image is examined.
            for q in queues.values():
                while not q.empty():
                    q.get_nowait()
            selected = stamp = None
            for offset in range(1, plan["capture_ticks"] + 1):
                frame, source = tick()
                if offset == plan["selected_capture_tick"]:
                    selected, stamp = frame, source
            found = {}
            deadline = time.monotonic() + 5
            while len(found) != 2 and time.monotonic() < deadline:
                for stream, q in queues.items():
                    while not q.empty():
                        image = q.get_nowait()
                        if image.frame == selected:
                            if stream in found:
                                raise ValueError("duplicate selected sensor frame")
                            found[stream] = image
                time.sleep(0.001)
            if len(found) != 2:
                raise ValueError(f"missing selected pair: {case['id']} frame{selected}")
            record = dict(
                scene=case["id"],
                frame=selected,
                source_ns=round(found["rgb"].timestamp * 1e9),
                snapshot_seconds=stamp,
            )
            for stream, image in found.items():
                raw = bytes(image.raw_data)
                if (image.width, image.height, len(raw)) != (
                    640,
                    384,
                    640 * 384 * 4,
                ) or abs(image.timestamp - stamp) > 1e-6:
                    raise ValueError("camera layout/source")
                path = Path(stream) / f"{selected:08d}.bgra"
                (a.output / path).parent.mkdir(exist_ok=True)
                (a.output / path).write_bytes(raw)
                record[stream] = dict(
                    path=str(path), sha256=hashlib.sha256(raw).hexdigest()
                )
            if found["rgb"].timestamp != found["instance"].timestamp:
                raise ValueError("pair timestamp")
            report["frames"].append(record)
            report["scenes"].append(
                dict(
                    id=case["id"],
                    weather=case["weather"],
                    stratum=case["stratum"],
                    target_class=case["target_class"],
                    actors=entries,
                    frame=selected,
                )
            )
            print(json.dumps(dict(case=case["id"], frame=selected)), flush=True)
        if report["overflow"]:
            raise ValueError("sensor queue overflow")
        report["status"] = "PASS"
    except Exception:
        report["error"] = traceback.format_exc()
    finally:
        for sensor in sensors:
            try:
                sensor.stop()
            except Exception as error:
                report["cleanup_errors"].append(str(error))
        for actor in list(reversed(scene_actors)) + list(reversed(sensors)):
            try:
                if not actor.destroy():
                    report["cleanup_errors"].append(f"destroy failed {actor.id}")
            except Exception as error:
                report["cleanup_errors"].append(str(error))
        if world is not None and original is not None:
            try:
                world.apply_settings(original)
            except Exception as error:
                report["cleanup_errors"].append(str(error))
        if report["cleanup_errors"]:
            report["status"] = "FAIL"
        (a.output / "capture.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report.get(k) for k in ("status", "error", "cleanup_errors")}))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

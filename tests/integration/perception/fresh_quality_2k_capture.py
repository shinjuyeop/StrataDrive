"""Capture the preselected paired RGB and instance exposure for each frozen static road scene."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import time
import traceback
import zlib

import carla
from carla_camera_resolution_v1 import pose
from fresh_quality_2k_plan import validate_retained
from quality_geometry_v4 import check_pose
from quality_staging_v5 import staging_pose


def transform(value):
    return carla.Transform(
        carla.Location(**value["location"]), carla.Rotation(**value["rotation"])
    )


def place(world, road, case, actors):
    entries = []
    for index, item in enumerate(case["actors"]):
        blueprint = world.get_blueprint_library().find(item["blueprint"])
        if blueprint.has_attribute("is_invincible"):
            blueprint.set_attribute("is_invincible", "true")
        stage = staging_pose(item["pose"], index)
        actor = world.spawn_actor(blueprint, transform(stage))
        actors.append(actor)
        actor.set_simulate_physics(False)
        final = transform(item["pose"])
        actor.set_transform(final)
        lane = road.get_waypoint(
            final.location, project_to_road=True, lane_type=carla.LaneType.Driving
        )
        error = final.location - lane.transform.location
        projection = math.hypot(error.x, error.y)
        clearance = error.z - item["clearance_m"]
        if (
            projection > 2
            or abs(clearance) > 0.15
            or lane.road_id != item["road_node"]["road_id"]
            or lane.lane_id != item["road_node"]["lane_id"]
        ):
            raise ValueError(f"{case['id']} actual surveyed lane or clearance mismatch")
        entries.append(
            dict(
                actor_id=actor.id,
                staging_requested_pose=stage,
                blueprint=actor.type_id,
                class_id=item["class_id"],
                role=item["role"],
                road_readback=dict(
                    road_id=lane.road_id,
                    lane_id=lane.lane_id,
                    projection_m=projection,
                    clearance_error_m=clearance,
                ),
            )
        )
    return entries


def store_image(target, kind, image):
    data = bytes(image.raw_data)
    if (image.width, image.height, len(data)) != (2560, 1536, 2560 * 1536 * 4):
        raise ValueError("2K camera byte layout")
    path = Path(kind) / f"{image.frame:08d}.bgra.z"
    encoded = zlib.compress(data, level=1)
    with (target / path).open("xb") as stream:
        stream.write(encoded)
    return dict(
        path=str(path),
        raw_bytes=len(data),
        stored_bytes=len(encoded),
        compression="zlib-1",
        sha256=hashlib.sha256(data).hexdigest(),
        stored_sha256=hashlib.sha256(encoded).hexdigest(),
    )


def capture(args):
    validate_retained(args.plan.parent)
    plan = json.loads(args.plan.read_text())
    part = plan["partitions"][args.partition]
    if args.plan.name != plan["phase"] + ".json":
        raise ValueError("declared plan phase")
    args.output.mkdir(parents=True, exist_ok=False)
    for kind in ("rgb", "instance"):
        (args.output / kind).mkdir()
    report = dict(
        status="FAIL",
        schema="m10-fresh-2k-capture-v1",
        phase=plan["phase"],
        partition=args.partition,
        site=part["spawn_point_index"],
        frames=[],
        scenes=[],
        errors=[],
        cleanup_errors=[],
        plan_sha256=hashlib.sha256(args.plan.read_bytes()).hexdigest(),
        sensors={},
        alignment={},
        camera=plan["camera"],
        sensor_tick_seconds=plan["sensor_tick_seconds"],
        epoch=1,
    )
    client = carla.Client("127.0.0.1", args.port)
    client.set_timeout(15)
    world = original = None
    actors, sensors = [], []
    frames = {kind: queue.Queue(maxsize=16) for kind in ("rgb", "instance")}
    overflow = []

    def collect(kind):
        def receive(image):
            try:
                frames[kind].put_nowait(image)
            except queue.Full:
                overflow.append((kind, image.frame))

        return receive

    def drain():
        for kind, pending in frames.items():
            while True:
                try:
                    yield kind, pending.get_nowait()
                except queue.Empty:
                    break

    def destroy_actors():
        while actors:
            actor = actors[-1]
            if not actor.destroy():
                raise ValueError(f"actor {actor.id} destroy failed")
            actors.pop()

    try:
        world = client.get_world()
        road = world.get_map()
        report.update(
            xodr_sha256=hashlib.sha256(road.to_opendrive().encode()).hexdigest(),
            world=world.id,
            sdk=client.get_client_version(),
            server=client.get_server_version(),
        )
        if (
            road.name.split("/")[-1] != plan["map"]
            or report["xodr_sha256"] != plan["xodr_sha256"]
            or report["sdk"] != "294096e-dirty"
            or report["server"] != report["sdk"]
            or any(
                a.type_id.startswith(("vehicle.", "walker.", "sensor."))
                for a in world.get_actors()
            )
        ):
            raise ValueError("isolated server, map and SDK identity")
        original = world.get_settings()
        cfg = world.get_settings()
        cfg.synchronous_mode, cfg.fixed_delta_seconds, cfg.no_rendering_mode = (
            True,
            0.01,
            False,
        )
        cfg.substepping, cfg.max_substep_delta_time, cfg.max_substeps = True, 0.01, 10
        world.apply_settings(cfg)
        applied = world.get_settings()
        if (
            not applied.synchronous_mode
            or applied.no_rendering_mode
            or abs(applied.fixed_delta_seconds - 0.01) > 1e-9
        ):
            raise ValueError("world settings readback")
        last_frame = None

        def tick():
            nonlocal last_frame
            frame = world.tick(15)
            snapshot = world.get_snapshot()
            if (
                frame != snapshot.frame
                or snapshot.id != world.id
                or (last_frame is not None and frame != last_frame + 1)
                or abs(snapshot.timestamp.delta_seconds - 0.01) > 1e-6
            ):
                raise ValueError("world tick or source discontinuity")
            last_frame = frame
            return frame, snapshot.timestamp.elapsed_seconds

        camera_pose = transform(part["camera_pose"])
        for kind, name in [("rgb", "rgb"), ("instance", "instance_segmentation")]:
            bp = world.get_blueprint_library().find("sensor.camera." + name)
            for key, value in dict(
                image_size_x="2560", image_size_y="1536", fov="90", sensor_tick="0.1"
            ).items():
                bp.set_attribute(key, value)
            if kind == "rgb":
                bp.set_attribute("enable_postprocess_effects", "true")
            sensor = world.spawn_actor(bp, camera_pose)
            sensors.append(sensor)
            attrs = dict(sensor.attributes)
            if (
                int(attrs["image_size_x"]),
                int(attrs["image_size_y"]),
                float(attrs["fov"]),
            ) != (2560, 1536, 90) or abs(float(attrs["sensor_tick"]) - 0.1) > 1e-6:
                raise ValueError("actual camera calibration or exposure period")
            report["sensors"][kind] = dict(id=sensor.id, attributes=attrs)
            sensor.listen(collect(kind))
        for _ in range(plan["alignment_ticks"]):
            tick()
        time.sleep(0.2)
        for kind, image in drain():
            report["alignment"].setdefault(kind, []).append(image.frame)
        streams = [report["alignment"].get(kind, []) for kind in frames]
        # Spawning a sensor can produce an initial exposure; only settled consecutive exposures define phase.
        if (
            any(len(s) < 2 or s[-1] - s[-2] != 10 for s in streams)
            or streams[0][-1] % 10 != streams[1][-1] % 10
        ):
            raise ValueError(
                f"unmatched paired 10 Hz acquisition schedule {report['alignment']}"
            )
        phase = streams[0][-1] % 10
        for case in part["cases"]:
            destroy_actors()
            weather = getattr(carla.WeatherParameters, case["weather"])
            world.set_weather(weather)
            actual_weather = world.get_weather()
            weather_values = {
                k: getattr(actual_weather, k)
                for k in (
                    "cloudiness",
                    "precipitation",
                    "precipitation_deposits",
                    "sun_altitude_angle",
                    "sun_azimuth_angle",
                    "fog_density",
                )
            }
            if any(
                abs(v - getattr(weather, k)) > 0.001 for k, v in weather_values.items()
            ):
                raise ValueError("weather readback")
            entries = place(world, road, case, actors)
            for _ in range(plan["settle_ticks"]):
                tick()
                for _kind, _image in drain():
                    pass
            # This exact frame is fixed before reading either stream.
            chosen = last_frame + 1 + (phase - last_frame - 1) % 10
            found = {}
            stamp = None

            def collect_chosen():
                for kind, image in drain():
                    if image.frame == chosen:
                        if kind in found:
                            raise ValueError("duplicate selected acquisition")
                        found[kind] = image

            while last_frame < chosen + plan["readback_ticks"]:
                frame, source = tick()
                if frame == chosen:
                    stamp = source
                collect_chosen()
            until = time.monotonic() + 5
            while len(found) < 2 and time.monotonic() < until:
                time.sleep(0.002)
                collect_chosen()
            if (
                len(found) != 2
                or found["rgb"].timestamp != found["instance"].timestamp
                or abs(found["rgb"].timestamp - stamp) > 1e-6
                or overflow
            ):
                raise ValueError(
                    f"{case['id']} missing, invalid or overflowed paired exposure {chosen}"
                )
            row = dict(
                scene=case["id"],
                frame=chosen,
                source_ns=round(found["rgb"].timestamp * 1e9),
                snapshot_seconds=stamp,
            )
            for kind, image in found.items():
                row[kind] = store_image(args.output, kind, image)
            for item, actor, entry in zip(case["actors"], actors, entries):
                entry["pose"] = pose(actor.get_transform())
                check_pose(entry["pose"], item["pose"])
            for sensor in sensors:
                check_pose(pose(sensor.get_transform()), part["camera_pose"])
            report["frames"].append(row)
            report["scenes"].append(
                dict(
                    id=case["id"],
                    frame=chosen,
                    actors=entries,
                    weather_readback=weather_values,
                    **{k: case[k] for k in ("weather", "stratum", "target_class")},
                )
            )
            print(case["id"], chosen, flush=True)
        report["status"] = "PASS"
    except Exception:
        report["errors"].append(traceback.format_exc())
    finally:
        for sensor in sensors:
            try:
                sensor.stop()
            except Exception:
                report["cleanup_errors"].append(traceback.format_exc())
        for actor in reversed(actors + sensors):
            try:
                if not actor.destroy():
                    raise ValueError(f"cleanup failed {actor.id}")
            except Exception:
                report["cleanup_errors"].append(traceback.format_exc())
        if original is not None:
            try:
                world.apply_settings(original)
            except Exception:
                report["cleanup_errors"].append(traceback.format_exc())
        report["overflow"] = overflow
        if overflow or report["cleanup_errors"]:
            report["status"] = "FAIL"
        (args.output / "capture.json").write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n"
        )
    print(report["status"], report["errors"], report["cleanup_errors"], flush=True)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument(
        "--partition", choices=("development", "holdout"), required=True
    )
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    raise SystemExit(capture(parser.parse_args()))

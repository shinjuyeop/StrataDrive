#!/usr/bin/env python3
"""Parked, isolated CARLA RGB/instance collection. No inference/control imports."""

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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=2300)
    parser.add_argument("--expected-version", default="294096e-dirty")
    parser.add_argument(
        "--rgb-postprocess", choices=("disabled", "enabled"), default="disabled"
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    report = {
        "status": "FAIL",
        "mode": "parked sensor evaluation only; no apply_control or AI authority",
        "seed": 0,  # UE4 -FixedSeed initializes both engine RNG seeds to zero.
        "map": "Town03_Opt",
        "weather": "ClearNoon",
        "rendering_quality": "unqualified; inspect raw images for asset/sky/warning defects",
        "rgb_postprocess": args.rgb_postprocess,
        "frames": [],
        "scenes": [],
        "sensor_attributes": {},
        "camera": {
            "width": 640,
            "height": 384,
            "fov_degrees": 90,
            "period_ns": 50_000_000,
            "calibration_revision": 1,
        },
        "world_step_ns": 10_000_000,
        "epoch": 1,
        "clock_instance": None,  # Bound to the actual isolated episode below.
        "cleanup_errors": [],
    }
    world = original = None
    actors = []
    sensors = []
    queues = {name: queue.Queue(maxsize=128) for name in ("rgb", "instance")}
    overflow = []

    def callback(name):
        def capture(image):
            try:
                queues[name].put_nowait(image)
            except queue.Full:
                overflow.append((name, image.frame))

        return capture

    try:
        client = carla.Client("127.0.0.1", args.port)
        client.set_timeout(20)
        report["client_version"] = client.get_client_version()
        report["server_version"] = client.get_server_version()
        if (
            not report["client_version"]
            == report["server_version"]
            == args.expected_version
        ):
            raise ValueError("client/server identity")
        world = client.get_world()
        report["clock_instance"] = world.id
        if world.get_map().name.rsplit("/", 1)[-1] != "Town03_Opt":
            raise ValueError("map mismatch")
        if list(world.get_actors().filter("vehicle.*")) or list(
            world.get_actors().filter("sensor.*")
        ):
            raise ValueError("requires isolated empty server")
        report["xodr_sha256"] = hashlib.sha256(
            world.get_map().to_opendrive().encode()
        ).hexdigest()
        original = world.get_settings()
        desired = world.get_settings()
        desired.synchronous_mode = True
        desired.fixed_delta_seconds = 0.01
        desired.no_rendering_mode = False
        desired.substepping = True
        desired.max_substep_delta_time = 0.01
        desired.max_substeps = 10
        world.apply_settings(desired)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        applied = world.get_settings()
        if (
            not applied.synchronous_mode
            or applied.no_rendering_mode
            or abs(applied.fixed_delta_seconds - 0.01) > 1e-9
        ):
            raise ValueError("settings readback")
        base = world.get_map().get_spawn_points()[0]
        report["base_pose"] = pose(base)
        yaw = math.radians(base.rotation.yaw)

        def transform(forward, right, z, rotation=0):
            return carla.Transform(
                carla.Location(
                    x=base.location.x + forward * math.cos(yaw) - right * math.sin(yaw),
                    y=base.location.y + forward * math.sin(yaw) + right * math.cos(yaw),
                    z=base.location.z + z,
                ),
                carla.Rotation(yaw=base.rotation.yaw + rotation),
            )

        library = world.get_blueprint_library()
        vehicle = world.spawn_actor(
            library.find("vehicle.lincoln.mkz_2020"), transform(12, -1.3, 0)
        )
        actors.append(vehicle)
        vehicle.set_simulate_physics(False)
        pedestrian = world.spawn_actor(
            library.find("walker.pedestrian.0001"), transform(10, 2.5, 0.5, 180)
        )
        actors.append(pedestrian)
        pedestrian.set_simulate_physics(False)
        camera_pose = transform(0, 0, 1.7)
        camera_pose.rotation.pitch = -6
        report["camera_pose"] = pose(camera_pose)
        report["actors"] = [{"id": actor.id, "type": actor.type_id} for actor in actors]
        for name, kind in (
            ("rgb", "sensor.camera.rgb"),
            ("instance", "sensor.camera.instance_segmentation"),
        ):
            bp = library.find(kind)
            for key, value in (
                ("image_size_x", "640"),
                ("image_size_y", "384"),
                ("fov", "90"),
                ("sensor_tick", ".05"),
            ):
                bp.set_attribute(key, value)
            if name == "rgb":
                bp.set_attribute(
                    "enable_postprocess_effects",
                    "True" if args.rgb_postprocess == "enabled" else "False",
                )
            sensor = world.spawn_actor(bp, camera_pose)
            report["sensor_attributes"][name] = dict(sensor.attributes)
            actors.append(sensor)
            sensors.append(sensor)
            sensor.listen(callback(name))
        previous = None

        def tick():
            nonlocal previous
            number = world.tick(20)
            snapshot = world.get_snapshot()
            if number != snapshot.frame or (
                previous is not None and number != previous + 1
            ):
                raise ValueError("single tick ownership violated")
            if abs(snapshot.timestamp.delta_seconds - 0.01) > 1e-6:
                raise ValueError("world period")
            previous = number
            return number, snapshot.timestamp.elapsed_seconds

        # Warmup is explicit and never enters the evaluation denominator.
        for _ in range(50):
            tick()
        time.sleep(0.2)
        for q in queues.values():
            while not q.empty():
                q.get_nowait()
        scenarios = (
            ("normal", (12, -1.3, 0), (10, 2.5, 0.5)),
            ("far", (45, -1.3, 0), (35, 2.5, 0.5)),
            ("occluded", (12, 0, 0), (15, 1, 0.5)),
        )
        for name, car_location, person_location in scenarios:
            vehicle.set_transform(transform(*car_location))
            pedestrian.set_transform(transform(*person_location, rotation=180))
            # Ten ticks allow sensor/render state to settle after placement.
            for _ in range(10):
                tick()
            time.sleep(0.1)
            for q in queues.values():
                while not q.empty():
                    q.get_nowait()
            states = {}
            for _ in range(100):
                number, stamp = tick()
                states[number] = stamp
            # Camera delivery is allowed to lag, but no extra physics ticks are hidden.
            deadline = time.monotonic() + 5
            received = {"rgb": {}, "instance": {}}
            while time.monotonic() < deadline:
                for stream, q in queues.items():
                    while not q.empty():
                        image = q.get_nowait()
                        if image.frame in states:
                            if image.frame in received[stream]:
                                raise ValueError("duplicate camera frame")
                            received[stream][image.frame] = image
                if len(received["rgb"]) >= 20 and len(received["instance"]) >= 20:
                    break
                time.sleep(0.01)
            if (
                set(received["rgb"]) != set(received["instance"])
                or len(received["rgb"]) != 20
            ):
                raise ValueError(
                    f"camera pair denominator {name}: {[len(v) for v in received.values()]}"
                )
            numbers = sorted(received["rgb"])
            if any(b - a != 5 for a, b in zip(numbers, numbers[1:])):
                raise ValueError("camera frame gap")
            scene = {
                "name": name,
                "car_pose": pose(vehicle.get_transform()),
                "person_pose": pose(pedestrian.get_transform()),
                "first_frame": numbers[0],
                "last_frame": numbers[-1],
                "count": len(numbers),
            }
            report["scenes"].append(scene)
            for number in numbers:
                rgb, instance = received["rgb"][number], received["instance"][number]
                if (
                    abs(rgb.timestamp - instance.timestamp) > 1e-9
                    or abs(rgb.timestamp - states[number]) > 1e-6
                ):
                    raise ValueError("sensor/snapshot time mismatch")
                entry = {
                    "scene": name,
                    "frame": number,
                    "source_ns": round(rgb.timestamp * 1e9),
                    "snapshot_seconds": states[number],
                }
                for stream, image in (("rgb", rgb), ("instance", instance)):
                    raw = bytes(image.raw_data)
                    if (image.width, image.height, len(raw)) != (
                        640,
                        384,
                        640 * 384 * 4,
                    ):
                        raise ValueError("BGRA layout")
                    path = Path(stream) / f"{number:08d}.bgra"
                    (args.output / path).parent.mkdir(exist_ok=True)
                    (args.output / path).write_bytes(raw)
                    entry[stream] = {
                        "path": str(path),
                        "sha256": hashlib.sha256(raw).hexdigest(),
                    }
                report["frames"].append(entry)
        if overflow:
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
        for actor in reversed(actors):
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
        report["overflow"] = overflow
        (args.output / "capture.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": report["status"],
                "frames": len(report["frames"]),
                "error": report.get("error"),
            }
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

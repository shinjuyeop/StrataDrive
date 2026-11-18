"""Inspect actual source/replica components while synchronous worlds are parked.

Preparation only: no native START, inference, control publication, or scene-fidelity
acceptance. The distinct server probe key is inherited, never written to evidence.
"""

import argparse
import hashlib
import json
import os
import queue
from pathlib import Path
import sys
import time
import traceback

import carla

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def inspect(args):
    args.output.mkdir(parents=True, exist_ok=False)
    client = carla.Client("127.0.0.1", args.port)
    client.set_timeout(10)
    actors = []
    camera = original = world = None
    arrivals = queue.Queue(maxsize=32)
    images = []
    report = dict(
        status="FAIL",
        role=args.role,
        inspected=[],
        errors=[],
        native_start=False,
        perception_publications=0,
        complete_scene_proof=False,
    )
    try:
        world = client.get_world()
        assert not any(
            a.type_id.startswith(("vehicle.", "walker.", "sensor."))
            for a in world.get_actors()
        )
        original = world.get_settings()
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        settings.no_rendering_mode = args.role == "owner"
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        for light in world.get_actors().filter("traffic.traffic_light"):
            light.set_state(carla.TrafficLightState.Red)
            light.freeze(True)
        road = world.get_map()
        points = road.get_spawn_points()
        if args.catalog:
            declared = json.loads(args.catalog.read_text())["actors"]
        else:
            declared = [
                dict(blueprint=model, attributes={}, spawn_index=index)
                for index, model in enumerate(
                    ("vehicle.lincoln.mkz_2020", "vehicle.tesla.model3")
                )
            ]
            declared.append(
                dict(
                    blueprint="walker.pedestrian.0001",
                    attributes={"is_invincible": "true"},
                    spawn_index=2,
                )
            )
        for item in declared:
            blueprint = world.get_blueprint_library().find(item["blueprint"])
            for name, value in item["attributes"].items():
                if (
                    blueprint.has_attribute(name)
                    and blueprint.get_attribute(name).is_modifiable
                ):
                    blueprint.set_attribute(name, value)
            if blueprint.has_attribute("role_name"):
                blueprint.set_attribute("role_name", "m10_visual_inspection")
            actor = world.spawn_actor(blueprint, points[item["spawn_index"]])
            actors.append(actor)
            actor.set_simulate_physics(False)
        ids = sorted(a.id for a in actors)
        report["actors"] = [
            dict(
                id=a.id,
                blueprint=a.type_id,
                attributes=dict(a.attributes),
                spawn_index=d["spawn_index"],
            )
            for a, d in zip(actors, declared)
        ]
        report.update(
            map=road.name,
            xodr_sha256=hashlib.sha256(road.to_opendrive().encode()).hexdigest(),
            world=world.id,
        )
        key = os.environ["STRATADRIVE_M10_VISUAL_INSPECT_KEY"]

        def request(actor_ids, secret=key):
            return json.loads(
                client.m7_nodrive(
                    json.dumps(dict(op="visual_inspect", key=secret, actors=actor_ids))
                )
            )

        rejected = request(ids, "0" * 64 if key != "0" * 64 else "1" * 64)
        assert rejected["ok"] is False and rejected["reason"] == "probe_key"
        malformed = request(["not-an-actor"])
        assert malformed["ok"] is False
        report["rejections"] = dict(wrong_key=rejected, malformed_actor=malformed)
        if args.role == "renderer":
            from endurance_recording_v1 import Zstd
            from PIL import Image

            codec = Zstd()
            bp = world.get_blueprint_library().find("sensor.camera.rgb")
            for name, value in dict(
                image_size_x="2560", image_size_y="1536", fov="90", sensor_tick=".1"
            ).items():
                bp.set_attribute(name, value)
            camera = world.spawn_actor(
                bp, carla.Transform(carla.Location(x=1.4, z=1.7)), attach_to=actors[0]
            )

            def received(image):
                try:
                    arrivals.put_nowait((time.monotonic_ns(), image))
                except queue.Full:
                    report["errors"].append("preparation image queue overflow")

            camera.listen(received)
            report["camera"] = dict(id=camera.id, attributes=dict(camera.attributes))
        for i in range(16):
            frame = world.tick()
            before = world.get_snapshot()
            value = request(ids)
            after = world.get_snapshot()
            assert value["ok"] and not value["complete_scene_proof"]
            assert before.frame == after.frame == frame == int(value["frame"])
            assert round(value["source_seconds"] * 1e9) == round(
                before.timestamp.elapsed_seconds * 1e9
            )
            assert all(a["present"] for a in value["actors"])
            name = f"frame-{frame}.json"
            write(args.output / name, value)
            report["inspected"].append(
                dict(
                    frame=frame,
                    source_seconds=value["source_seconds"],
                    path=name,
                    sha256=hashlib.sha256(
                        (args.output / name).read_bytes()
                    ).hexdigest(),
                    acquisition_ns=int(value["acquired_end_ns"])
                    - int(value["acquired_begin_ns"]),
                )
            )
            if camera:
                time.sleep(0.06)
        if camera:
            # Wait for readbacks already in flight while this frame stays parked.
            # A bounded UE render pipeline can retain its last images until another tick.
            time.sleep(0.35)
            camera.stop()
            inspected = {r["frame"]: r["source_seconds"] for r in report["inspected"]}
            while not arrivals.empty():
                callback_ns, image = arrivals.get_nowait()
                if (image.width, image.height) != (2560, 1536):
                    raise ValueError("unexpected camera layout")
                data = bytes(image.raw_data)
                if len(data) != image.width * image.height * 4:
                    raise ValueError("camera byte layout")
                path = args.output / f"{len(images):02d}-{image.frame}.bgra.zst"
                stored = codec.compress(data)
                with path.open("xb") as target:
                    target.write(stored)
                if codec.decompress(path.read_bytes(), len(data)) != data:
                    raise ValueError("lossless image readback mismatch")
                rgb = Image.frombytes(
                    "RGB", (image.width, image.height), data, "raw", "BGRX"
                ).tobytes()
                images.append(
                    dict(
                        frame=image.frame,
                        source_seconds=image.timestamp,
                        callback_ns=callback_ns,
                        width=image.width,
                        height=image.height,
                        rgb_sha256=hashlib.sha256(rgb).hexdigest(),
                        original_sha256=hashlib.sha256(data).hexdigest(),
                        stored_sha256=hashlib.sha256(stored).hexdigest(),
                        original_bytes=len(data),
                        stored_bytes=len(stored),
                        path=path.name,
                    )
                )
            frames = [image["frame"] for image in images]
            report["camera_frame_steps"] = [b - a for a, b in zip(frames, frames[1:])]
            if (
                not images
                or len(set(frames)) != len(frames)
                or any(
                    r["frame"] not in inspected
                    or abs(r["source_seconds"] - inspected[r["frame"]]) > 1e-6
                    for r in images
                )
            ):
                raise ValueError(
                    "camera exposures must match distinct observed engine frames and timestamps"
                )
        report["status"] = "PASS_READ_ONLY_PREPARATION_INSPECTION"
    except Exception:
        report["errors"].append(traceback.format_exc())
    finally:
        for actor in ([camera] if camera else []) + list(reversed(actors)):
            try:
                if actor == camera and camera.is_listening:
                    camera.stop()
                if not actor.destroy():
                    raise ValueError(f"actor {actor.id} cleanup failed")
            except Exception:
                report["errors"].append(traceback.format_exc())
        if original is not None:
            try:
                world.apply_settings(original)
            except Exception:
                report["errors"].append(traceback.format_exc())
        report["images"] = images
        if report["errors"]:
            report["status"] = "FAIL"
        write(args.output / "result.json", report)
    print(json.dumps({k: report[k] for k in ("status", "role", "errors")}), flush=True)
    return 0 if report["status"].startswith("PASS_") else 1


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--role", choices=("owner", "renderer"), required=True)
    p.add_argument("--port", type=int, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--catalog", type=Path)
    raise SystemExit(inspect(p.parse_args()))

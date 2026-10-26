#!/usr/bin/env python3
"""Rendered crash diagnostic: >=10 paired RGB/GT frames, no driving or AI input.

This bounded probe does not certify complete sensor delivery, calibration, or
native timing. Every received frame is recorded, including startup/end effects.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import threading
import time
import traceback

import carla


def settings(s):
    return {key: getattr(s, key) for key in ("synchronous_mode", "fixed_delta_seconds",
            "no_rendering_mode", "substepping", "max_substep_delta_time", "max_substeps")}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--expected-version", required=True)
    p.add_argument("--port", type=int, default=2200)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    r = dict(status="FAIL", started_utc=datetime.now(timezone.utc).isoformat(),
             executable=sys.executable, expected_version=args.expected_version,
             mode="RENDERED DIAGNOSTIC; ego physics disabled; GT evaluation only",
             image_config=dict(width=320, height=240, fov_deg=90, sensor_tick_s=.05))
    begun = time.monotonic()
    world = original = None
    touched = False
    actors, sensors = [], []
    images = {"rgb": [], "gt": []}
    overflow = {"rgb": 0, "gt": 0}
    lock = threading.Lock()
    states = {}

    def callback(name):
        def capture(image):
            with lock:
                if len(images[name]) >= 128:
                    overflow[name] += 1
                else:
                    images[name].append(image)
        return capture

    try:
        client = carla.Client("127.0.0.1", args.port)
        client.set_timeout(20)
        r["client_version"] = client.get_client_version()
        r["server_version"] = client.get_server_version()
        if not r["client_version"] == r["server_version"] == args.expected_version:
            raise RuntimeError("source identity mismatch")
        world = client.get_world()
        r["map"] = world.get_map().name
        if r["map"].rsplit("/", 1)[-1] != "Town03_Opt":
            raise RuntimeError("unexpected map")
        if list(world.get_actors().filter("vehicle.*")):
            raise RuntimeError("dedicated server requires empty initial vehicle registry")
        original = world.get_settings()
        r["settings_before"] = settings(original)
        if original.no_rendering_mode:
            raise RuntimeError("rendered path required; no-rendering fallback forbidden")
        desired = world.get_settings()
        desired.synchronous_mode = True
        desired.fixed_delta_seconds = .01
        desired.no_rendering_mode = False
        desired.substepping = True
        desired.max_substep_delta_time = .01
        desired.max_substeps = 10
        touched = True
        world.apply_settings(desired)
        r["settings_during"] = settings(world.get_settings())
        if r["settings_during"] != settings(desired):
            raise RuntimeError("rendered settings readback mismatch")
        bp = world.get_blueprint_library().find("vehicle.lincoln.mkz_2020")
        bp.set_attribute("role_name", "stratadrive_render_diagnostic")
        ego = world.spawn_actor(bp, world.get_map().get_spawn_points()[0])
        actors.append(ego)
        ego.set_simulate_physics(False)
        # Fresh ego is never registered with Traffic Manager.
        for name, kind in (("rgb", "sensor.camera.rgb"), ("gt", "sensor.camera.semantic_segmentation")):
            bp = world.get_blueprint_library().find(kind)
            for key, value in (("image_size_x", "320"), ("image_size_y", "240"),
                               ("fov", "90"), ("sensor_tick", "0.05")):
                bp.set_attribute(key, value)
            sensor = world.spawn_actor(bp, carla.Transform(carla.Location(x=1.6, z=1.7),
                                       carla.Rotation(pitch=-8)), attach_to=ego)
            actors.append(sensor)
            sensors.append(sensor)
            sensor.listen(callback(name))
        previous = None
        for _ in range(150):
            frame = world.tick(20)
            snapshot = world.get_snapshot()
            if frame != snapshot.frame or (previous is not None and frame != previous + 1):
                raise RuntimeError("extra/missing tick owner or snapshot mismatch")
            states[frame] = snapshot.timestamp.elapsed_seconds
            previous = frame
        time.sleep(.5)  # bounded callback drain; no new acquisition timestamps
        for sensor in sensors:
            sensor.stop()
        r["overflow"] = overflow
        r["tick_states"] = states
        r["frames"] = {}
        by_frame = {}
        for name, data in images.items():
            by_frame[name] = {}
            metadata = []
            for image in data:
                if image.frame in by_frame[name]:
                    raise RuntimeError("duplicate sensor frame")
                by_frame[name][image.frame] = image
                raw = bytes(image.raw_data)
                if image.width != 320 or image.height != 240 or len(raw) != 320*240*4:
                    raise RuntimeError("image dimensions/stride mismatch")
                entry = dict(frame=image.frame, timestamp=image.timestamp,
                             sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
                if name == "rgb":
                    colors = raw[0::4] + raw[1::4] + raw[2::4]
                    entry.update(color_min=min(colors), color_max=max(colors))
                else:
                    entry["label_histogram"] = dict(Counter(raw[2::4]))
                metadata.append(entry)
            r["frames"][name] = metadata
        paired = sorted(set(by_frame["rgb"]) & set(by_frame["gt"]) & set(states))
        r["paired_in_tick_window"] = paired
        r["unpaired_received"] = {name: sorted(set(data) - set(paired)) for name, data in by_frame.items()}
        if len(paired) < 10 or any(overflow.values()):
            raise RuntimeError("insufficient paired images or callback overflow")
        for frame in paired:
            for name in ("rgb", "gt"):
                if abs(by_frame[name][frame].timestamp - states[frame]) > 1e-6:
                    raise RuntimeError("original sensor timestamp does not match snapshot")
        rgb = by_frame["rgb"][paired[0]]
        gt = by_frame["gt"][paired[0]]
        colors = bytes(rgb.raw_data)[0::4] + bytes(rgb.raw_data)[1::4] + bytes(rgb.raw_data)[2::4]
        if max(colors) == min(colors) or len(set(bytes(gt.raw_data)[2::4])) < 2:
            raise RuntimeError("blank RGB or undifferentiated segmentation")
        rgb.save_to_disk(str(args.output / "first-rgb.png"))
        gt.save_to_disk(str(args.output / "first-gt-raw.png"))
        r["status"] = "PASS"
    except Exception:
        r["error"] = traceback.format_exc()
    finally:
        try:
            if world is not None:
                client.set_timeout(5)
                for sensor in sensors:
                    if sensor.is_alive and sensor.is_listening:
                        sensor.stop()
                r["destroy_returns"] = {actor.id: actor.destroy() for actor in reversed(actors) if actor.is_alive}
                if actors:
                    world.tick(5)
                    snapshot = world.get_snapshot()
                    current = world.get_actors()
                    r["remaining_owned"] = [a.id for a in actors if current.find(a.id) is not None or snapshot.find(a.id) is not None]
                    if r["remaining_owned"] or not all(r["destroy_returns"].values()):
                        raise RuntimeError("owned actor cleanup failed")
                if touched:
                    world.apply_settings(original)
                    r["settings_after"] = settings(world.get_settings())
                    if r["settings_after"] != r["settings_before"]:
                        raise RuntimeError("episode settings restore failed")
        except Exception:
            r["cleanup_error"] = traceback.format_exc()
            r["status"] = "FAIL"
        r["elapsed_wall_s"] = time.monotonic() - begun
        (args.output / "result.json").write_text(json.dumps(r, indent=2) + "\n")
        print(json.dumps(dict(status=r["status"], elapsed_wall_s=r["elapsed_wall_s"],
                              paired=len(r.get("paired_in_tick_window", [])), error=r.get("error"))))
    return 0 if r["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

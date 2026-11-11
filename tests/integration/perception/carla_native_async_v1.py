#!/usr/bin/env python3
"""Finite live4K camera observation; sole world tick owner, no vehicle control."""

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import threading
import time
import traceback
import zlib

import carla
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.async_native_v1 import AsyncNativePerception, WIDTH, HEIGHT
from physical_ai.perception.camera import CameraClock
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.native_preprocess_v1 import FastNativeBackend
from physical_ai.perception.provenance import runtime_identity
from physical_ai.perception.run import distribution
from probe_async_native_v1 import check_sources


def run(a):
    a.output.mkdir(parents=True, exist_ok=False)
    report = dict(
        schema="m10-carla-native-async-v1",
        status="FAIL",
        live_camera=True,
        actual_vehicle_control=False,
        runtime_promotion=False,
        quality_acceptance=False,
        live20Hz_acceptance=False,
        cold_calls_excluded=0,
        runtime=runtime_identity(),
        traces=dict(state=[], camera=[], consumer=[]),
        model_calls=[],
        errors=[],
        cleanup_errors=[],
        raw=[],
        recorder_capacity=64,
        recorder_overflow=[],
        clock="actual observed CARLA snapshots; no extrapolation",
        receipt_scope="worker.offer entry; SDK raw_data materialization before entry measured separately",
    )
    actors, captured = [], []
    world = original = sensor = worker = consumer_thread = None
    stop = threading.Event()
    callback_lock = threading.Lock()
    state_lock = threading.Lock()
    state = None
    try:
        report["freeze_sha256"] = check_sources(a.freeze)
        plan = json.loads(a.plan.read_text())
        report["plan_sha256"] = sha256_file(a.plan)
        part = plan["partitions"]["development"]
        if plan["map"] != "Town04_Opt" or part["spawn_point_index"] != 38:
            raise ValueError("consumed development site38 only")
        initializing = time.monotonic_ns()
        detector = FastNativeBackend(a.model, a.models, "cuda")
        report["model_initialization_wall_ns"] = time.monotonic_ns() - initializing
        report["providers"] = detector.detector.session.get_providers()
        report["provider_options"] = detector.detector.session.get_provider_options()
        client = carla.Client("127.0.0.1", a.port)
        client.set_timeout(20)
        report["client_version"] = client.get_client_version()
        report["server_version"] = client.get_server_version()
        if (
            report["client_version"] != "294096e-dirty"
            or report["server_version"] != "294096e-dirty"
        ):
            raise ValueError("SDK/server version")
        world = client.get_world()
        road = world.get_map()
        if road.name.rsplit("/", 1)[-1] != plan["map"]:
            raise ValueError("map mismatch")
        if any(
            list(world.get_actors().filter(kind))
            for kind in ("vehicle.*", "sensor.*", "walker.*")
        ):
            raise ValueError("isolated empty server required")
        report["xodr_sha256"] = hashlib.sha256(road.to_opendrive().encode()).hexdigest()
        if report["xodr_sha256"] != plan["xodr_sha256"]:
            raise ValueError("map identity")
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
        report["world_settings"] = {
            k: getattr(applied, k)
            for k in (
                "synchronous_mode",
                "fixed_delta_seconds",
                "no_rendering_mode",
                "substepping",
                "max_substep_delta_time",
                "max_substeps",
            )
        }
        if (
            not applied.synchronous_mode
            or applied.no_rendering_mode
            or abs(applied.fixed_delta_seconds - 0.01) > 1e-9
        ):
            raise ValueError("world readback")
        world.set_weather(carla.WeatherParameters.ClearNoon)
        library = world.get_blueprint_library()

        def explicit(p):
            return carla.Transform(
                carla.Location(**p["location"]), carla.Rotation(**p["rotation"])
            )

        # One existing development person placement; no GT/visible-mask input.
        fixture = part["cases"][0]
        report["fixture"] = dict(
            case=fixture["id"],
            site=38,
            camera_pose=part["camera_pose"],
            actors=fixture["actors"],
        )
        for item in fixture["actors"]:
            actor = world.spawn_actor(
                library.find(item["blueprint"]), explicit(item["pose"])
            )
            actors.append(actor)
            actor.set_simulate_physics(False)
        initial = world.get_snapshot()
        clock = CameraClock(world.id)
        initial_source = round(initial.timestamp.elapsed_seconds * 1e9)
        clock.update(initial.frame, initial_source)
        report.update(
            clock_instance=world.id,
            initial_frame=initial.frame,
            initial_source_ns=initial_source,
        )

        class Backend:
            def infer(self, packet):
                row = dict(
                    identity=asdict(packet.identity),
                    received_wall_ns=packet.received_wall_ns,
                    begin_wall_ns=time.monotonic_ns(),
                )
                try:
                    result = detector.infer(packet)
                    row["result"] = asdict(result)
                    return result
                except Exception as error:
                    row["error"] = f"{type(error).__name__}: {error}"
                    raise
                finally:
                    row["end_wall_ns"] = time.monotonic_ns()
                    report["model_calls"].append(row)

        worker = AsyncNativePerception(Backend(), clock)
        if not worker.start_session(1, initial_source):
            raise ValueError("native session init")
        state = dict(frame=initial.frame, source_ns=initial_source)

        def callback(image):
            row = dict(
                begin_wall_ns=time.monotonic_ns(),
                frame=image.frame,
                source_ns=round(image.timestamp * 1e9),
                width=image.width,
                height=image.height,
            )
            # The finite recorder stores the same immutable SDK bytes by reference.
            # No image conversion/hash/compression/disk work occurs in this callback.
            with callback_lock:
                try:
                    raw = bytes(image.raw_data)
                    row["offer_entry_wall_ns"] = time.monotonic_ns()
                    row["accepted"] = worker.offer(
                        image.frame, image.timestamp, image.width, image.height, raw
                    )
                    if len(captured) < 64:
                        captured.append((row, raw))
                    else:
                        report["recorder_overflow"].append(image.frame)
                        worker.invalidate("finite recorder overflow")
                except Exception:
                    row["error"] = traceback.format_exc()
                    report["errors"].append(row["error"])
                    worker.invalidate("SDK callback failure")
                row["end_wall_ns"] = time.monotonic_ns()
                report["traces"]["camera"].append(row)

        def consume():
            period = 20_000_000
            begin = time.monotonic_ns()
            scheduled = begin
            try:
                while not stop.is_set():
                    remaining = scheduled - time.monotonic_ns()
                    if remaining > 0 and stop.wait(remaining / 1e9):
                        break
                    started = time.monotonic_ns()
                    with state_lock:
                        sample = dict(state)
                    source = clock.now()
                    reading = time.monotonic_ns()
                    result = worker.snapshot()
                    row = dict(
                        begin_wall_ns=started,
                        scheduled_wall_ns=scheduled,
                        state=sample,
                        snapshot_read_source_ns=source,
                        snapshot_read_wall_ns=reading,
                        perception=asdict(result) if result else None,
                        end_wall_ns=time.monotonic_ns(),
                    )
                    following = max(
                        (row["end_wall_ns"] - begin) // period + 1,
                        (scheduled - begin) // period + 1,
                    )
                    row["skipped_slots"] = following - (scheduled - begin) // period - 1
                    report["traces"]["consumer"].append(row)
                    scheduled = begin + following * period
            except Exception:
                report["errors"].append(traceback.format_exc())
                stop.set()

        bp = library.find("sensor.camera.rgb")
        for k, v in (
            ("image_size_x", str(WIDTH)),
            ("image_size_y", str(HEIGHT)),
            ("fov", "90"),
            ("sensor_tick", "0.05"),
            ("role_name", "m7_frame5"),
            ("enable_postprocess_effects", "True"),
        ):
            bp.set_attribute(k, v)
        sensor = world.spawn_actor(bp, explicit(part["camera_pose"]))
        attrs = dict(sensor.attributes)
        report["sensor_attributes"] = attrs
        if (
            any(
                float(attrs.get(k, "nan")) != v
                for k, v in dict(
                    image_size_x=WIDTH, image_size_y=HEIGHT, fov=90, sensor_tick=0.05
                ).items()
            )
            or attrs.get("role_name") != "m7_frame5"
            or attrs.get("enable_postprocess_effects", "").lower() != "true"
        ):
            raise ValueError("camera attribute readback")
        consumer_thread = threading.Thread(
            target=consume, name="native-live-observer", daemon=True
        )
        consumer_thread.start()
        sensor.listen(callback)
        report["enabled_wall_ns"] = time.monotonic_ns()
        # 300..304 ticks, ending at modulo4: four source ticks after last frame5 acquisition.
        last_frame = initial.frame + 300
        last_frame += (4 - last_frame % 5) % 5
        report["last_planned_frame"] = last_frame
        for _ in range(initial.frame + 1, last_frame + 1):
            begun = time.monotonic_ns()
            frame_number = world.tick(20)
            snap = world.get_snapshot()
            source = round(snap.timestamp.elapsed_seconds * 1e9)
            if frame_number != snap.frame or not worker.observe_tick(
                frame_number, source
            ):
                raise ValueError("single authoritative world tick")
            with state_lock:
                state = dict(frame=frame_number, source_ns=source)
            report["traces"]["state"].append(
                dict(state, begin_wall_ns=begun, end_wall_ns=time.monotonic_ns())
            )
            if stop.is_set():
                raise ValueError("consumer failure")
        # Permit SDK delivery without advancing simulation or waiting in the consumer.
        time.sleep(0.2)
        sensor.stop()
        with callback_lock:
            report["sensor_stopped_wall_ns"] = time.monotonic_ns()
        # Source clock deliberately stops too. Original receipt expiry must still work.
        time.sleep(0.3)
        report["silence_end_wall_ns"] = time.monotonic_ns()
        stop.set()
        consumer_thread.join(2)
        if consumer_thread.is_alive() or not worker.drain(5):
            raise TimeoutError("finite owner cleanup")
        report["worker"] = worker.status()
        if (
            report["errors"]
            or report["recorder_overflow"]
            or report["worker"]["clock_fault"]
        ):
            raise ValueError("owner/recording fault")
        for name, rows in report["traces"].items():
            if len(rows) < 2:
                raise ValueError("owner made insufficient progress: " + name)
            report.setdefault("metrics", {})[name] = dict(
                jobs=len(rows),
                observed_hz=(len(rows) - 1)
                * 1e9
                / (rows[-1]["begin_wall_ns"] - rows[0]["begin_wall_ns"]),
                job_wall=distribution(
                    [r["end_wall_ns"] - r["begin_wall_ns"] for r in rows]
                ),
                interval_wall=distribution(
                    [
                        b["begin_wall_ns"] - a["begin_wall_ns"]
                        for a, b in zip(rows, rows[1:])
                    ]
                ),
            )
        calls = report["model_calls"]
        report["metrics"]["receipt_to_backend_return"] = distribution(
            [r["end_wall_ns"] - r["received_wall_ns"] for r in calls]
        )
        report["fresh_output_observed"] = report["worker"]["counters"]["published"] > 0
        report["unique_consumed_frames"] = len(
            {
                r["perception"]["identity"]["frame"]
                for r in report["traces"]["consumer"]
                if r["perception"]
            }
        )
        if check_sources(a.freeze) != report["freeze_sha256"]:
            raise ValueError("source changed during live run")
        report["status"] = "PASS"
    except Exception:
        report["error"] = traceback.format_exc()
    finally:
        stop.set()
        if sensor:
            try:
                if sensor.is_listening:
                    sensor.stop()
                if not sensor.destroy():
                    raise ValueError("sensor destroy")
            except Exception:
                report["cleanup_errors"].append(traceback.format_exc())
        if consumer_thread:
            consumer_thread.join(2)
        if worker:
            report["closed"] = worker.close(5)
            report["final_worker"] = worker.status()
            if not report["closed"]:
                report["cleanup_errors"].append("worker close timeout")
        for actor in reversed(actors):
            try:
                if not actor.destroy():
                    raise ValueError("actor destroy")
            except Exception:
                report["cleanup_errors"].append(traceback.format_exc())
        if world and original:
            try:
                world.apply_settings(original)
            except Exception:
                report["cleanup_errors"].append(traceback.format_exc())
        # Post-measurement only: retain ALL callback bytes, including first/late/failures.
        for row, raw in captured:
            try:
                data = zlib.compress(raw, 1)
                name = f"{row['frame']}.bgra.z"
                (a.output / name).write_bytes(data)
                rgb = Image.frombytes(
                    "RGB", (WIDTH, HEIGHT), raw, "raw", "BGRX"
                ).tobytes()
                report["raw"].append(
                    dict(
                        frame=row["frame"],
                        source_ns=row["source_ns"],
                        rgb_sha256=hashlib.sha256(rgb).hexdigest(),
                        bgra_sha256=hashlib.sha256(raw).hexdigest(),
                        path=name,
                        stored_sha256=hashlib.sha256(data).hexdigest(),
                        stored_bytes=len(data),
                        raw_bytes=len(raw),
                    )
                )
            except Exception:
                report["cleanup_errors"].append(traceback.format_exc())
        if report["cleanup_errors"]:
            report["status"] = "FAIL"
        if report["status"] == "PASS":
            try:
                from audit_carla_native_async_v1 import audit

                report["audit"] = audit(report)
            except Exception:
                report["status"] = "FAIL"
                report["audit_error"] = traceback.format_exc()
        (a.output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for k in ("plan", "model", "models", "freeze", "output"):
        p.add_argument("--" + k, type=Path, required=True)
    p.add_argument("--port", type=int, default=2300)
    a = p.parse_args()
    result = run(a)
    print(
        json.dumps({k: result.get(k) for k in ("status", "error", "metrics", "worker")})
    )
    return int(result["status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())

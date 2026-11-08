#!/usr/bin/env python3
"""Owned parked CARLA camera + concurrent real inference; no vehicle authority."""

import argparse
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import sys
import tarfile
import threading
import time
import traceback


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--boundary", type=Path, required=True)
    p.add_argument("--port", type=int, default=2300)
    p.add_argument("--execution", choices=("cpu", "cuda"), default="cuda")
    p.add_argument("--frames", type=int, default=300)
    p.add_argument(
        "--rgb-postprocess", choices=("disabled", "enabled"), default="disabled"
    )
    p.add_argument(
        "--camera-clock", choices=("frame5", "sensor-tick"), default="frame5"
    )
    p.add_argument(
        "--fault",
        choices=("none", "slow", "exception", "blackout", "silence"),
        default="none",
    )
    args = p.parse_args()
    if not 60 <= args.frames <= 1200:
        p.error("frames must be 60..1200")
    sys.path.insert(0, str(args.repo_root.resolve()))
    import carla
    from physical_ai.perception.camera import CameraClock, BgraCameraIngress
    from physical_ai.perception.contract import (
        MODEL_SHA256,
        LIFETIME_NS,
        sha256_file,
        carla_rgb_profile,
        CARLA_RGB_PROFILE_PATH,
    )
    from physical_ai.perception.worker import LatestFrameWorker
    from physical_ai.perception.yolox import YoloX
    from physical_ai.perception.tracking import ImageTracker
    from physical_ai.perception.provenance import runtime_identity
    from physical_ai.perception.replay import frame_line, run_boundary
    from physical_ai.perception.run import distribution

    args.output.mkdir(parents=True, exist_ok=False)
    report = dict(
        status="FAIL",
        mode="live parked RGB shadow; no actuator/GT input",
        execution=args.execution,
        fault=args.fault,
        requested_camera_frames=args.frames,
        seed=0,
        map="Town03_Opt",
        weather="ClearNoon",
        camera_period_ns=50_000_000,
        world_step_ns=10_000_000,
        camera_clock=args.camera_clock,
        rgb_postprocess=args.rgb_postprocess,
        rendering_quality="unqualified skydome/warning defects",
        quality_acceptance="NOT_SET",
        wall_acceptance="NOT_CLAIMED",
        runtime=runtime_identity(),
        model_sha256=MODEL_SHA256,
        callbacks=[],
        submissions=[],
        consumer=[],
        model_calls=[],
        ticks=[],
        cleanup_errors=[],
    )
    actors, sensor, worker, ingress, world, original = [], None, None, None, None, None
    callback_lock = threading.Lock()
    enable_frame = None
    clock = None
    trace_lock = threading.Lock()
    sensor_enabled = False
    sensor_phase = False
    starting = time.monotonic_ns()
    boundary_lines = []
    tracker = ImageTracker()
    last_consumed = 0
    saved = set()

    def pose(t):
        return {
            group: {k: getattr(getattr(t, group), k) for k in keys}
            for group, keys in (
                ("location", ("x", "y", "z")),
                ("rotation", ("pitch", "yaw", "roll")),
            )
        }

    def callback(image):
        nonlocal sensor_enabled
        wall = time.monotonic_ns()
        with callback_lock:
            row = dict(
                frame=image.frame,
                source_ns=round(image.timestamp * 1e9),
                callback_wall_ns=wall,
            )
            if not sensor_enabled or image.frame <= enable_frame:
                row["outcome"] = "before_enable"
            elif len(report["callbacks"]) >= args.frames + 200:
                # A misconfigured producer must not grow the diagnostic trace forever.
                row["outcome"] = "trace_bound"
                ingress.close()
                sensor_enabled = False
            elif (
                args.fault == "silence"
                and image.frame > enable_frame + args.frames * 5 // 2
            ):
                row["outcome"] = "injected_silence"
            else:
                raw = bytes(image.raw_data)
                if (
                    args.fault == "blackout"
                    and image.frame > enable_frame + args.frames * 5 // 2
                ):
                    raw = bytes(len(raw))
                    row["injected"] = "blackout"
                row["bgra_sha256"] = hashlib.sha256(raw).hexdigest()
                row["outcome"] = (
                    "offered"
                    if ingress.offer(
                        image.frame, image.timestamp, image.width, image.height, raw
                    )
                    else "rejected"
                )
            report["callbacks"].append(row)

    def pump():
        nonlocal last_consumed
        entry = ingress.pump(clock)
        if entry:
            packet, accepted = entry
            report["submissions"].append(
                dict(
                    identity=asdict(packet.identity),
                    received_wall_ns=packet.received_wall_ns,
                    pump_wall_ns=time.monotonic_ns(),
                    accepted=accepted,
                )
            )
            # Sparse original samples only; no IO occurs on the camera callback.
            bucket = (packet.identity.frame - enable_frame - 1) // 100
            if bucket not in saved:
                saved.add(bucket)
                path = args.output / f"sample-{packet.identity.frame:08d}.rgb"
                path.write_bytes(packet.camera().rgb)
                report.setdefault("samples", []).append(
                    dict(
                        path=path.name,
                        sha256=sha256_file(path),
                        identity=asdict(packet.identity),
                    )
                )
        snapshot = worker.snapshot()
        source = clock.now()
        wall = time.monotonic_ns()
        row = dict(source_now_ns=source, wall_ns=wall, frame=None)
        if snapshot:
            if not snapshot.identity.source_ns <= source < snapshot.expires_ns:
                raise ValueError("consumer saw stale source")
            row.update(
                frame=snapshot.identity.frame,
                source_ns=snapshot.identity.source_ns,
                expires_ns=snapshot.expires_ns,
            )
            if snapshot.identity.frame != last_consumed:
                row["detections"] = [asdict(d) for d in snapshot.detections]
                row["tracks"] = [asdict(t) for t in tracker.update(snapshot)]
                boundary_lines.append(frame_line(snapshot, source))
                last_consumed = snapshot.identity.frame
        report["consumer"].append(row)

    try:
        if args.rgb_postprocess == "enabled":
            if args.camera_clock != "frame5":
                raise ValueError("RGB renderer profile requires frame5")
            report["renderer_profile"] = carla_rgb_profile()
            report["renderer_profile_sha256"] = sha256_file(CARLA_RGB_PROFILE_PATH)
            report["rendering_quality"] = (
                "RGB postprocess enabled; observed sky/HUD correction; full ODD quality NOT_CLAIMED"
            )
        client = carla.Client("127.0.0.1", args.port)
        client.set_timeout(20)
        report["client_version"] = client.get_client_version()
        report["server_version"] = client.get_server_version()
        if (
            report["client_version"] != "294096e-dirty"
            or report["server_version"] != "294096e-dirty"
        ):
            raise ValueError("client/server identity")
        world = client.get_world()
        report["clock_instance"] = world.id
        if world.get_map().name.rsplit("/", 1)[-1] != "Town03_Opt":
            raise ValueError("map")
        if list(world.get_actors().filter("vehicle.*")) or list(
            world.get_actors().filter("sensor.*")
        ):
            raise ValueError("requires isolated empty server")
        original = world.get_settings()
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.01
        settings.no_rendering_mode = False
        settings.substepping = True
        settings.max_substep_delta_time = 0.01
        settings.max_substeps = 10
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        applied = world.get_settings()
        if (
            not applied.synchronous_mode
            or applied.no_rendering_mode
            or abs(applied.fixed_delta_seconds - 0.01) > 1e-9
        ):
            raise ValueError("world settings readback")
        report["xodr_sha256"] = hashlib.sha256(
            world.get_map().to_opendrive().encode()
        ).hexdigest()
        base = world.get_map().get_spawn_points()[0]
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
        person = world.spawn_actor(
            library.find("walker.pedestrian.0001"), transform(10, 2.5, 0.5, 180)
        )
        actors.append(person)
        person.set_simulate_physics(False)
        camera_pose = transform(0, 0, 1.7)
        camera_pose.rotation.pitch = -6
        report["camera_pose"] = pose(camera_pose)
        report["fixture_motion"] = (
            "parked vehicle; physics-disabled person moves laterally 2.5+sin(t*.8)*1m per simulation time"
        )
        bp = library.find("sensor.camera.rgb")
        for key, value in (
            ("image_size_x", "640"),
            ("image_size_y", "384"),
            ("fov", "90"),
            ("sensor_tick", ".05"),
            (
                "enable_postprocess_effects",
                "True" if args.rgb_postprocess == "enabled" else "False",
            ),
        ):
            bp.set_attribute(key, value)
        if args.camera_clock == "frame5":
            bp.set_attribute("role_name", "m7_frame5")
        sensor = world.spawn_actor(bp, camera_pose)
        actors.append(sensor)
        report["sensor_attributes"] = dict(sensor.attributes)
        if sensor.attributes["enable_postprocess_effects"] != (
            "true" if args.rgb_postprocess == "enabled" else "false"
        ):
            raise ValueError("RGB postprocess readback")
        if (
            args.camera_clock == "frame5"
            and sensor.attributes.get("role_name") != "m7_frame5"
        ):
            raise ValueError("camera scheduling role readback")
        clock = CameraClock(world.id)
        snapshot = world.get_snapshot()
        clock.update(snapshot.frame, round(snapshot.timestamp.elapsed_seconds * 1e9))
        sensor.listen(callback)
        for _ in range(50):
            number = world.tick(20)
            snapshot = world.get_snapshot()
            if number != snapshot.frame:
                raise ValueError("tick ownership")
            clock.update(number, round(snapshot.timestamp.elapsed_seconds * 1e9))
        time.sleep(0.2)
        model_start = time.monotonic_ns()
        detector = YoloX(args.model, execution=args.execution)
        report["model_initialization_wall_ns"] = time.monotonic_ns() - model_start
        report["providers"] = detector.session.get_providers()
        report["provider_options"] = detector.session.get_provider_options()

        class Backend:
            def infer(self, camera):
                begun = time.monotonic_ns()
                row = dict(
                    identity=asdict(camera.identity),
                    start_wall_ns=begun,
                    phase="sensor" if sensor_phase else "startup",
                )
                try:
                    if row["phase"] == "sensor":
                        if args.fault == "slow":
                            time.sleep(0.15)
                        if (
                            args.fault == "exception"
                            and camera.identity.frame
                            > enable_frame + args.frames * 5 // 2
                        ):
                            raise RuntimeError("injected live backend exception")
                    result = detector.infer(camera)
                    row.update(
                        preprocess_ns=result.preprocess_ns,
                        inference_ns=result.inference_ns,
                        postprocess_ns=result.postprocess_ns,
                        detections=[asdict(d) for d in result.detections],
                    )
                    return result
                except Exception as error:
                    row["error"] = f"{type(error).__name__}: {error}"
                    raise
                finally:
                    row["complete_wall_ns"] = time.monotonic_ns()
                    with trace_lock:
                        report["model_calls"].append(row)

        worker = LatestFrameWorker(Backend(), clock.now, require_preparation=True)
        if not worker.prepare() or not worker.wait_ready(11):
            raise ValueError("model preparation failed")
        report["preparation"] = worker.status()["preparation"]
        sensor_phase = True
        enable_frame = snapshot.frame
        report["enable_frame"] = enable_frame
        enable_ns = clock.now()
        report["enable_source_ns"] = enable_ns
        if not worker.start_session(1, world.id, enable_ns):
            raise ValueError("worker INIT")
        boundary_lines.append(f"S 1 {world.id} {enable_ns}")
        ingress = BgraCameraIngress(worker, 1, world.id, dict(sensor.attributes))
        with callback_lock:
            sensor_enabled = True
        begin = time.monotonic_ns()
        next_tick = begin
        report["stream_started_wall_ns"] = begin
        for index in range(args.frames * 5):
            # Pace a maximum100Hz. Missed wall slots are recorded, never hidden by catchup ticks.
            scheduled = next_tick
            now = time.monotonic_ns()
            if now < scheduled:
                time.sleep((scheduled - now) / 1e9)
            before = time.monotonic_ns()
            next_tick = before + 10_000_000
            if index % 5 == 0:
                person.set_transform(
                    transform(10, 2.5 + math.sin(index * 0.01 * 0.8), 0.5, 180)
                )
            number = world.tick(20)
            snapshot = world.get_snapshot()
            if number != snapshot.frame:
                raise ValueError("tick owner mismatch")
            source_ns = round(snapshot.timestamp.elapsed_seconds * 1e9)
            clock.update(number, source_ns)
            report["ticks"].append(
                dict(
                    frame=number,
                    source_ns=source_ns,
                    scheduled_wall_ns=scheduled,
                    begin_wall_ns=before,
                    end_wall_ns=time.monotonic_ns(),
                )
            )
            pump()
        report["stream_finished_wall_ns"] = time.monotonic_ns()
        # Delayed callback drain with a paused source clock; no hidden simulation tick.
        tail = time.monotonic() + 0.5
        while time.monotonic() < tail:
            pump()
            time.sleep(0.005)
        with callback_lock:
            sensor_enabled = False
        sensor.stop()
        if not worker.drain(5):
            raise TimeoutError("worker drain")
        if worker.snapshot() is not None:
            raise ValueError("paused camera/source retained wall-stale availability")
        report["worker"] = worker.status()
        report["ingress"] = ingress.status()
        calls = [r for r in report["model_calls"] if r["phase"] == "sensor"]
        counts = report["worker"]["counters"]
        incoming = report["ingress"]["counters"]
        if (
            counts["submitted"]
            != counts["started"] + counts["overwritten"] + counts["cancelled"]
            or counts["started"] != counts["completed"]
            or counts["completed"]
            != sum(counts[k] for k in ("published", "late", "errors", "obsolete"))
            or len(calls) != counts["started"]
            or incoming["accepted"]
            != incoming["overwritten"]
            + incoming["submitted"]
            + incoming["rejected"]
            + incoming["cancelled"]
            or incoming["submitted"] != counts["submitted"]
        ):
            raise ValueError("bounded queue/completion accounting")
        enabled = [
            r
            for r in report["callbacks"]
            if r["frame"] > enable_frame and r["outcome"] != "before_enable"
        ]
        if len(enabled) != args.frames or any(
            b["frame"] - a["frame"] != 5 for a, b in zip(enabled, enabled[1:])
        ):
            raise ValueError("camera cadence/denominator")
        if args.fault == "none" and (counts["errors"] or not counts["published"]):
            raise ValueError("unexpected model error or no live publication")
        if args.fault == "slow" and (counts["published"] or not counts["late"]):
            raise ValueError("slow result admitted or fault not exercised")
        if args.fault in ("exception", "blackout") and not counts["errors"]:
            raise ValueError("error fault not exercised")
        submitted = {
            r["identity"]["frame"]: r["received_wall_ns"]
            for r in report["submissions"]
            if r["accepted"]
        }
        report["receipt_to_completion"] = distribution(
            [r["complete_wall_ns"] - submitted[r["identity"]["frame"]] for r in calls]
        )
        report["tick_wall"] = distribution(
            [r["end_wall_ns"] - r["begin_wall_ns"] for r in report["ticks"]]
        )
        report["camera_callback_intervals"] = distribution(
            [
                b["callback_wall_ns"] - a["callback_wall_ns"]
                for a, b in zip(enabled, enabled[1:])
            ]
        )
        report["actual_camera_hz"] = (
            (len(enabled) - 1)
            * 1e9
            / (enabled[-1]["callback_wall_ns"] - enabled[0]["callback_wall_ns"])
        )
        report["simulation_to_wall_ratio"] = (
            args.frames * 50_000_000 / (report["stream_finished_wall_ns"] - begin)
        )
        report["unique_consumed"] = len(boundary_lines) - 1
        # Validate the actual consumed output at the independent C++ boundary offline.
        boundary_lines.append(f"P {clock.now() + LIFETIME_NS}")
        (args.output / "boundary-input.txt").write_text(
            "\n".join(boundary_lines) + "\n"
        )
        received = run_boundary(args.boundary, boundary_lines)
        (args.output / "boundary-output.json").write_text(
            json.dumps(received, indent=2) + "\n"
        )
        if (
            not all(row["accepted"] for row in received[:-1])
            or received[-1]["available"]
        ):
            raise ValueError("C++ live observation replay mismatch")
        report["boundary"] = dict(
            status="PASS",
            mode="post-run typed replay, not IPC/control",
            binary_sha256=sha256_file(args.boundary),
            observations=len(boundary_lines) - 2,
        )
        report["status"] = "PASS"
    except Exception:
        report["error"] = traceback.format_exc()
    finally:
        with callback_lock:
            sensor_enabled = False
        if sensor is not None:
            try:
                if sensor.is_listening:
                    sensor.stop()
            except Exception as error:
                report["cleanup_errors"].append(str(error))
        if ingress:
            ingress.close()
            report["final_ingress"] = ingress.status()
        if worker:
            report["closed"] = worker.close(5)
            report["final_worker"] = worker.status()
            if not report["closed"]:
                report["cleanup_errors"].append("inference thread still running")
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
        report["total_wall_ns"] = time.monotonic_ns() - starting
        (args.output / "live.json").write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n"
        )
        with tarfile.open(args.output / "samples.tar.gz", "w:gz") as archive:
            for path in sorted(args.output.glob("sample-*.rgb")):
                archive.add(path, arcname=path.name)
    print(
        json.dumps(
            {
                k: report.get(k)
                for k in (
                    "status",
                    "error",
                    "preparation",
                    "worker",
                    "ingress",
                    "actual_camera_hz",
                    "receipt_to_completion",
                    "boundary",
                )
            }
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Matched fixed-step world modes; asynchronous state/camera/observer ownership."""

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
from physical_ai.perception.async_native_v1 import WIDTH, HEIGHT
from physical_ai.perception.world_async_v1 import (
    ObservedWorldClock,
    WorldAsyncPerception,
)
from physical_ai.perception.availability_v1 import availability
from native_memory_recorder_v1 import MemoryRecorder
from physical_ai.perception.native_kernel_v1 import KernelNativeBackend
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.provenance import runtime_identity
from physical_ai.perception.run import distribution
from probe_async_native_v1 import check_sources


def run(a):
    a.output.mkdir(parents=True, exist_ok=False)
    report = dict(
        schema="m10-carla-world-async-v1",
        condition=a.condition,
        status="FAIL",
        live_camera=True,
        actual_vehicle_control=False,
        runtime_promotion=False,
        quality_acceptance=False,
        live20Hz_acceptance=False,
        cold_calls_excluded=0,
        runtime=runtime_identity(),
        traces=dict(state=[], camera=[], consumer=[], tick_requests=[]),
        model_calls=[],
        preparation_calls=[],
        errors=[],
        cleanup_errors=[],
        raw=[],
        recorder_capacity=240,
        recorder_overflow=[],
        clock="actual observed CARLA snapshots; no extrapolation",
        receipt_scope="worker.offer entry; SDK raw_data materialization before entry measured separately",
    )
    actors = []
    recorder = None
    world = original = sensor = worker = consumer_thread = None
    stop = threading.Event()
    callback_lock = threading.Lock()
    state_lock = threading.Lock()
    state = None
    tick_callback_id = None
    done = threading.Event()
    session_started = False
    accepting = True
    observing = True
    try:
        report["freeze_sha256"] = check_sources(a.freeze)
        plan = json.loads(a.plan.read_text())
        report["plan_sha256"] = sha256_file(a.plan)
        part = plan["partitions"]["development"]
        if plan["map"] != "Town04_Opt" or part["spawn_point_index"] != 38:
            raise ValueError("consumed development site38 only")
        profile_path = (
            Path(__file__).resolve().parents[3]
            / "profiles/perception-world-async-v1.json"
        )
        profile = json.loads(profile_path.read_text())
        report["kernel_profile_sha256"] = sha256_file(profile_path)
        initializing = time.monotonic_ns()
        if (
            a.condition not in profile["live_conditions"]
            or profile["live_ticks_min"] != 500
        ):
            raise ValueError("native startup live profile")
        detector = KernelNativeBackend(
            a.model, a.models, a.library, profile["native_library_sha256"]
        )
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
        clock = ObservedWorldClock(world.id)
        report["clock_instance"] = world.id

        preparing = True

        class Backend:
            def infer(self, packet):
                row = dict(
                    identity=asdict(packet.identity),
                    owner_thread_id=threading.get_ident(),
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
                    report["preparation_calls" if preparing else "model_calls"].append(
                        row
                    )

        worker = WorldAsyncPerception(Backend(), clock)
        if not worker.prepare() or not worker.wait_prepared(10):
            report["preparation"] = worker.preparation_status()
            raise ValueError("native preparation did not become READY")
        report["preparation"] = worker.preparation_status()
        preparing = False
        recorder = MemoryRecorder(a.output / "raw", profile["live_recorder_capacity"])

        def observed(snap):
            nonlocal state, session_started
            row = dict(
                begin_wall_ns=time.monotonic_ns(),
                frame=snap.frame,
                source_ns=round(snap.timestamp.elapsed_seconds * 1e9),
                delta_ns=round(snap.timestamp.delta_seconds * 1e9),
                world_id=snap.id,
            )
            with state_lock:
                if not observing:
                    return
                try:
                    row["disposition"] = worker.observe_snapshot(
                        row["world_id"],
                        row["frame"],
                        row["source_ns"],
                        row["delta_ns"],
                        row["begin_wall_ns"],
                    )
                    if row["disposition"] == "fault":
                        raise ValueError("observed world snapshot fault")
                    if row["disposition"] == "accepted":
                        state = dict(frame=row["frame"], source_ns=row["source_ns"])
                        if not session_started:
                            if not worker.start_observed_session(1):
                                raise ValueError("observed native session init")
                            session_started = True
                            last = row["frame"] + 499
                            last += (4 - last % 5) % 5
                            report.update(
                                initial_frame=row["frame"],
                                initial_source_ns=row["source_ns"],
                                last_planned_frame=last,
                            )
                        if (
                            row["frame"] >= report["last_planned_frame"]
                            and not done.is_set()
                        ):
                            report["primary_end_wall_ns"] = time.monotonic_ns()
                            report["primary_end_frame"] = row["frame"]
                            done.set()
                    row["end_wall_ns"] = time.monotonic_ns()
                    if len(report["traces"]["state"]) >= 4096:
                        raise ValueError("state trace capacity")
                    report["traces"]["state"].append(row)
                except Exception:
                    report["errors"].append(traceback.format_exc())
                    stop.set()
                    done.set()

        def callback(image):
            row = dict(
                begin_wall_ns=time.monotonic_ns(),
                frame=image.frame,
                source_ns=round(image.timestamp * 1e9),
                width=image.width,
                height=image.height,
            )
            # Keep finite immutable references in memory; no normal measured disk I/O.
            # Overflow fails and spills unexpected extra bytes to the original recorder.
            with callback_lock:
                try:
                    raw = bytes(image.raw_data)
                    row["offer_entry_wall_ns"] = time.monotonic_ns()
                    row["offered"] = accepting
                    row["accepted"] = (
                        worker.offer(
                            image.frame, image.timestamp, image.width, image.height, raw
                        )
                        if accepting
                        else False
                    )
                    if not recorder.offer(row, raw):
                        report["recorder_overflow"].append(image.frame)
                        worker.invalidate("finite recorder overflow")
                        stop.set()
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
                    sample = worker.observation()
                    row = dict(
                        begin_wall_ns=started,
                        scheduled_wall_ns=scheduled,
                        state=sample["state"],
                        snapshot_read_source_ns=sample["source_ns"],
                        snapshot_read_wall_ns=sample["wall_ns"],
                        perception=asdict(sample["result"])
                        if sample["result"]
                        else None,
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
        # No cached setup snapshot is represented as a new state receipt.
        report["enabled_wall_ns"] = time.monotonic_ns()
        consumer_thread.start()
        tick_callback_id = world.on_tick(observed)
        sensor.listen(callback)
        asynchronous = a.condition.startswith("async-")
        settings.synchronous_mode = not asynchronous
        report["mode_switch_begin_wall_ns"] = time.monotonic_ns()
        world.apply_settings(settings)
        applied = world.get_settings()
        report["active_settings"] = {
            k: getattr(applied, k) for k in report["world_settings"]
        }
        if (
            applied.synchronous_mode == asynchronous
            or abs(applied.fixed_delta_seconds - 0.01) > 1e-9
        ):
            raise ValueError("active mode readback")

        def tick():
            row = dict(begin_wall_ns=time.monotonic_ns())
            row["frame"] = world.tick(20)
            row["end_wall_ns"] = time.monotonic_ns()
            report["traces"]["tick_requests"].append(row)

        deadline = time.monotonic() + 30
        while not done.is_set() and not stop.is_set():
            if time.monotonic() >= deadline:
                raise TimeoutError("finite primary world progress")
            if asynchronous:
                done.wait(0.01)
            else:
                tick()
        if stop.is_set():
            raise ValueError("asynchronous owner failure")
        sensor.stop()
        with callback_lock:
            accepting = False
            report["sensor_stopped_wall_ns"] = time.monotonic_ns()
        # State continues during the no-camera tail in both world modes.
        until = time.monotonic() + 0.3
        while time.monotonic() < until:
            if asynchronous:
                stop.wait(0.01)
            else:
                tick()
        report["silence_end_wall_ns"] = time.monotonic_ns()
        world.remove_on_tick(tick_callback_id)
        tick_callback_id = None
        with state_lock:
            observing = False
        stop.set()
        consumer_thread.join(2)
        if consumer_thread.is_alive() or not worker.drain(5):
            raise TimeoutError("finite owner cleanup")
        report["worker"] = worker.status()
        report["decisions"] = worker.decision_trace()
        report["world_observation"] = worker.world_status()
        if (
            report["errors"]
            or report["recorder_overflow"]
            or report["worker"]["clock_fault"]
        ):
            raise ValueError("owner/recording fault")
        for name in ("state", "camera", "consumer"):
            rows = sorted(report["traces"][name], key=lambda r: r["begin_wall_ns"])
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
        report["availability"] = {
            name: availability(
                report["traces"]["consumer"], calls, report["enabled_wall_ns"], end
            )
            for name, end in (
                ("active_ticks", report["primary_end_wall_ns"]),
                ("including_delivery_tail", report["sensor_stopped_wall_ns"]),
            )
        }
        accepted_states = [
            x
            for x in report["traces"]["state"]
            if x["disposition"] == "accepted"
            and x["frame"] <= report["primary_end_frame"]
        ]
        first, last = accepted_states[0], accepted_states[-1]
        report["metrics"]["simulation_realtime_factor"] = (
            last["source_ns"] - first["source_ns"]
        ) / (last["begin_wall_ns"] - first["begin_wall_ns"])
        report["metrics"]["observed_world_hz"] = (
            (len(accepted_states) - 1)
            * 1e9
            / (last["begin_wall_ns"] - first["begin_wall_ns"])
        )
        primary_camera = [
            x
            for x in report["traces"]["camera"]
            if report["enabled_wall_ns"]
            <= x["begin_wall_ns"]
            < report["primary_end_wall_ns"]
        ]
        report["metrics"]["primary_camera_hz"] = (
            (len(primary_camera) - 1)
            * 1e9
            / (primary_camera[-1]["begin_wall_ns"] - primary_camera[0]["begin_wall_ns"])
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
        if world and tick_callback_id is not None:
            try:
                world.remove_on_tick(tick_callback_id)
                with state_lock:
                    observing = False
            except Exception:
                report["cleanup_errors"].append(traceback.format_exc())
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
            report.setdefault("worker", report["final_worker"])
            report.setdefault("decisions", worker.decision_trace())
            report.setdefault("world_observation", worker.world_status())
            report["preparation_final"] = worker.preparation_status()
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
        # Post-measurement compression; retain ALL original frames, including failures.
        if recorder:
            if not recorder.close(30):
                report["cleanup_errors"].append("raw recorder close timeout")
            report["recorder"] = recorder.report()
            if report["recorder"]["errors"]:
                report["cleanup_errors"].extend(report["recorder"]["errors"])
        for row, raw in (
            recorder.iter_raw() if recorder and report["recorder"]["stopped"] else []
        ):
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
                from audit_carla_world_async_v1 import audit

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
    p.add_argument(
        "--condition", choices=("sync-01", "async-01", "async-02"), required=True
    )
    p.add_argument("--library", type=Path, required=True)
    p.add_argument("--port", type=int, default=2300)
    a = p.parse_args()
    result = run(a)
    print(
        json.dumps({k: result.get(k) for k in ("status", "error", "metrics", "worker")})
    )
    return int(result["status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())

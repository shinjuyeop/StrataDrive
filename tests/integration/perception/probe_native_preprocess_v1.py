#!/usr/bin/env python3
"""Finite native4K media SIL component probe with independent periodic owners.

This is recorded development-media playback, not a live camera, vehicle
controller, ROS integration, new quality test or real-time qualification.
"""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import threading
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.async_native_v1 import (
    AsyncNativePerception,
    CANDIDATE,
    HEIGHT,
    MODEL_SHA256,
    WIDTH,
)
from physical_ai.perception.native_preprocess_v1 import FastNativeBackend
from physical_ai.perception.camera import CameraClock
from physical_ai.perception.camera_resolution_v1 import NativeDataset, unpack
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import read_json
from physical_ai.perception.provenance import runtime_identity
from physical_ai.perception.run import distribution

PROFILE = (
    Path(__file__).resolve().parents[3]
    / "profiles/perception-native-preprocess-v1.json"
)


def check_sources(path):
    root = Path(__file__).resolve().parents[3]
    source = read_json(path)
    if not source["files"] or any(
        sha256_file(root / name) != digest for name, digest in source["files"].items()
    ):
        raise ValueError("async source freeze mismatch")
    return sha256_file(path)


def run(args):
    args.output.mkdir(parents=True, exist_ok=False)
    report = dict(
        schema="m10-async-native-probe-v1",
        status="FAIL",
        fault=args.fault,
        duration_seconds=args.seconds,
        candidate=CANDIDATE,
        model_sha256=MODEL_SHA256,
        mode="recorded development BGRA playback with independent observational owners",
        actual_vehicle_control=False,
        live_camera=False,
        runtime_promotion=False,
        quality_acceptance=False,
        live20Hz_acceptance=False,
        cold_calls_excluded=0,
        runtime=runtime_identity(),
        clock="observed synthetic10ms world steps; monotonic wall measured separately",
        periods_ns=dict(state=10_000_000, camera=50_000_000, control=20_000_000),
        traces=dict(state=[], camera=[], control=[]),
        model_calls=[],
        thread_errors=[],
    )
    worker = None
    stop, unblock = threading.Event(), threading.Event()
    state_lock, trace_lock = threading.Lock(), threading.Lock()
    threads = []
    try:
        report["source_freeze_sha256"] = check_sources(args.freeze)
        profile = read_json(PROFILE)
        if (
            profile["candidate"] != CANDIDATE
            or profile["model_sha256"] != MODEL_SHA256
            or profile["source_bgra"] != [WIDTH, HEIGHT, 4]
            or args.seconds != profile["probe_seconds_per_fault"]
            or args.fault not in profile["faults"]
            or profile["periods_ns"] != report["periods_ns"]
            or profile["source_lifetime_ns"] != 100_000_000
            or profile["receipt_to_completion_budget_ns"] != 100_000_000
            or any(
                profile[k] != 1
                for k in (
                    "pending_capacity",
                    "active_inference_capacity",
                    "snapshot_capacity",
                )
            )
        ):
            raise ValueError("async executable/profile mismatch")
        report["profile_sha256"] = sha256_file(PROFILE)
        # Never open GT or holdout. Restore SDK packets before measured playback.
        data = NativeDataset(args.media)
        if (
            data.scale != 6
            or len(data.manifest["frames"]) != 3
            or data.manifest["phase"] != "pilot"
        ):
            raise ValueError(
                "exactly three recorded development4K pilot frames required"
            )
        media = [
            (row, unpack(args.media.parent, row["rgb_raw"], WIDTH, HEIGHT))
            for row in data.manifest["frames"]
        ]
        report["media"] = dict(
            manifest_sha256=sha256_file(args.media),
            partition="development",
            preloaded_before_measurement=True,
            excluded_costs="disk/decompression, simulator rendering and SDK transport/copy before offer",
            originals=[
                dict(
                    frame=r["frame"],
                    source_ns=r["source_ns"],
                    rgb_sha256=r["rgb_sha256"],
                    bgra_sha256=r["rgb_raw"]["sha256"],
                )
                for r, _ in media
            ],
        )
        initializing = time.monotonic_ns()
        detector = FastNativeBackend(args.model, args.models, args.execution)
        report["model_initialization_wall_ns"] = time.monotonic_ns() - initializing
        report["providers"] = detector.detector.session.get_providers()
        report["provider_options"] = detector.detector.session.get_provider_options()
        clock = CameraClock(77)
        clock.update(1, 10_000_000)

        class Backend:
            def infer(self, packet):
                row = dict(
                    identity=asdict(packet.identity),
                    received_wall_ns=packet.received_wall_ns,
                    begin_wall_ns=time.monotonic_ns(),
                )
                try:
                    if args.fault == "slow":
                        time.sleep(0.15)
                        row["injected_delay_ns"] = 150_000_000
                    if args.fault == "blocked":
                        row["injected_block"] = True
                        if not unblock.wait(10):
                            raise TimeoutError("finite injected block was not released")
                    if args.fault == "exception":
                        time.sleep(0.025)
                        row["injected_delay_ns"] = 25_000_000
                        raise RuntimeError("injected native perception exception")
                    result = detector.infer(packet)
                    row["result"] = asdict(result)
                    return result
                except Exception as error:
                    row["error"] = f"{type(error).__name__}: {error}"
                    raise
                finally:
                    row["end_wall_ns"] = time.monotonic_ns()
                    with trace_lock:
                        report["model_calls"].append(row)

        worker = AsyncNativePerception(Backend(), clock)
        if not worker.start_session(1, 10_000_000):
            raise ValueError("native session INIT")
        state = dict(
            frame=1, source_ns=10_000_000, received_wall_ns=time.monotonic_ns()
        )
        begin = time.monotonic_ns() + 100_000_000
        end = begin + round(args.seconds * 1e9)
        report.update(begin_wall_ns=begin, end_wall_ns=end)

        def state_job(index):
            nonlocal state
            number = index + 2
            source = number * 10_000_000
            if not worker.observe_tick(number, source):
                raise ValueError("observed playback world tick")
            sample = dict(
                frame=number, source_ns=source, received_wall_ns=time.monotonic_ns()
            )
            with state_lock:
                state = sample
            return sample

        def camera_job(index):
            with state_lock:
                sample = dict(state)
            original, raw = media[index % len(media)]
            accepted = worker.offer(
                sample["frame"], sample["source_ns"] / 1e9, WIDTH, HEIGHT, raw
            )
            return dict(
                frame=sample["frame"],
                source_ns=sample["source_ns"],
                accepted=accepted,
                original_frame=original["frame"],
                original_source_ns=original["source_ns"],
                original_bgra_sha256=original["rgb_raw"]["sha256"],
            )

        def control_job(index):
            # Observational consumer only. No command, default scene or actuator output.
            with state_lock:
                sample = dict(state)
            read_wall = time.monotonic_ns()
            read_source = clock.now()
            result = worker.snapshot()
            return dict(
                state=sample,
                snapshot_read_wall_ns=read_wall,
                snapshot_read_source_ns=read_source,
                perception=asdict(result) if result else None,
            )

        def periodic(name, job):
            period, scheduled, index = report["periods_ns"][name], begin, 0
            try:
                while scheduled < end and not stop.is_set():
                    remaining = scheduled - time.monotonic_ns()
                    if remaining > 0 and stop.wait(remaining / 1e9):
                        break
                    started = time.monotonic_ns()
                    if started >= end:
                        break
                    row = dict(
                        index=index, scheduled_wall_ns=scheduled, begin_wall_ns=started
                    )
                    row.update(job(index))
                    row["end_wall_ns"] = time.monotonic_ns()
                    # Keep every missed wall slot visible; no catch-up execution.
                    following = max(
                        (row["end_wall_ns"] - begin) // period + 1,
                        (scheduled - begin) // period + 1,
                    )
                    row["skipped_slots"] = following - (scheduled - begin) // period - 1
                    with trace_lock:
                        report["traces"][name].append(row)
                    scheduled = begin + following * period
                    index += 1
            except Exception:
                with trace_lock:
                    report["thread_errors"].append(
                        dict(owner=name, error=traceback.format_exc())
                    )
                stop.set()

        for name, job in (
            ("state", state_job),
            ("camera", camera_job),
            ("control", control_job),
        ):
            thread = threading.Thread(
                target=periodic,
                args=(name, job),
                name=f"native-probe-{name}",
                daemon=True,
            )
            threads.append(thread)
            thread.start()
        for thread in threads:
            thread.join(args.seconds + 2)
        if any(t.is_alive() for t in threads):
            raise TimeoutError("periodic owner failed to stop independently")
        report["before_backend_release"] = worker.status()
        if args.fault == "blocked":
            # State/camera/control all finished while the first backend was still blocked.
            if not report["before_backend_release"]["busy"] or report["model_calls"]:
                raise ValueError(
                    "blocked inference did not span the periodic-owner run"
                )
        unblock.set()
        if not worker.drain(5):
            raise TimeoutError("native owner finite drain")
        report["worker"] = worker.status()
        c = report["worker"]["counters"]
        camera_rows = report["traces"]["camera"]
        calls = report["model_calls"]
        if report["thread_errors"] or report["worker"]["clock_fault"]:
            raise ValueError("periodic owner or clock failure")
        if (
            not calls
            or c["offered"] != len(camera_rows)
            or c["accepted"] != sum(r["accepted"] for r in camera_rows)
            or c["accepted"]
            != sum(
                c[k] for k in ("started", "overwritten", "cancelled", "expired_pending")
            )
            or c["started"] != c["completed"]
            or c["started"] != len(calls)
            or c["completed"]
            != sum(c[k] for k in ("published", "late", "errors", "obsolete"))
        ):
            raise ValueError("bounded input/completion accounting")
        if args.fault == "exception":
            if c["errors"] != len(calls) or c["published"]:
                raise ValueError("exception fault admission")
        elif c["errors"]:
            raise ValueError("unexpected native backend error")
        if args.fault in ("slow", "blocked") and (
            c["published"] or not c["late"] or not c["overwritten"]
        ):
            raise ValueError("late/overload fault was not exercised or was admitted")
        overlap = dict(state=0, control=0)
        for name in overlap:
            overlap[name] = sum(
                any(
                    call["begin_wall_ns"] <= r["begin_wall_ns"] < call["end_wall_ns"]
                    for call in calls
                )
                for r in report["traces"][name]
            )
        if min(overlap.values()) == 0:
            raise ValueError("no independent state/control work during inference")
        report["overlap_jobs_during_backend"] = overlap
        report["metrics"] = {}
        for name, rows in report["traces"].items():
            report["metrics"][name] = dict(
                jobs=len(rows),
                skipped_slots=sum(r["skipped_slots"] for r in rows),
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
        report["metrics"]["receipt_to_backend_return"] = distribution(
            [r["end_wall_ns"] - r["received_wall_ns"] for r in calls]
        )
        report["unique_consumed_frames"] = len(
            {
                r["perception"]["identity"]["frame"]
                for r in report["traces"]["control"]
                if r["perception"]
            }
        )
        report["fresh_output_observed"] = c["published"] > 0
        report["preprocessing_revision"] = "m10-native-preprocess-v1"
        if args.fault == "none" and not (
            c["published"] > 0 and report["unique_consumed_frames"] > 0
        ):
            raise ValueError("normal probe requires fresh publication and consumption")
        if check_sources(args.freeze) != report["source_freeze_sha256"]:
            raise ValueError("sources changed during finite run")
        report["status"] = "PASS"
    except Exception:
        report["error"] = traceback.format_exc()
    finally:
        stop.set()
        unblock.set()
        for thread in threads:
            thread.join(2)
        if worker is not None:
            report["closed"] = worker.close(5)
            report["final_worker"] = worker.status()
            if not report["closed"]:
                report["status"] = "FAIL"
        (args.output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--media", type=Path, required=True)
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--models", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--freeze", type=Path, required=True)
    p.add_argument("--seconds", type=float, default=6)
    p.add_argument("--execution", choices=("cpu", "cuda"), default="cuda")
    p.add_argument(
        "--fault", choices=("none", "slow", "exception", "blocked"), default="none"
    )
    args = p.parse_args()
    if not 3 <= args.seconds <= 8:
        p.error("finite probe seconds must be3..8")
    result = run(args)
    print(
        json.dumps(
            {
                k: result.get(k)
                for k in ("status", "fault", "metrics", "worker", "error")
            }
        )
    )
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

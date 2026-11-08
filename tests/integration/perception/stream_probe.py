#!/usr/bin/env python3
"""Finite 20Hz media playback into the real bounded worker; no camera latency claim."""

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import FrameIdentity, sha256_file, PROFILE_PATH
from physical_ai.perception.dataset import RgbDataset
from physical_ai.perception.worker import LatestFrameWorker
from physical_ai.perception.yolox import YoloX
from physical_ai.perception.run import distribution
from physical_ai.perception.provenance import runtime_identity


def run(dataset, model_path, output, fault, execution="cpu", prepare=False, repeats=1):
    if type(repeats) is not int or not 1 <= repeats <= 20:
        raise ValueError("repeats must be 1..20")
    output.mkdir(parents=True, exist_ok=False)
    # Materialize a bounded 60-frame dataset before measured work. Playback is
    # explicitly a new simulated source, original frame/source remain in trace.
    media = list(RgbDataset(dataset).frames())
    if len(media) != 60:
        raise ValueError("probe requires frozen60 input frames")
    media *= repeats
    initializing = time.monotonic_ns()
    detector = YoloX(model_path, execution=execution)
    initialization_ns = time.monotonic_ns() - initializing
    model_calls = []
    sensor_phase = not prepare

    class Backend:
        def infer(self, camera):
            started = time.monotonic_ns()
            call = {
                "frame": camera.identity.frame,
                "source_ns": camera.identity.source_ns,
                "start_wall_ns": started,
                "phase": "sensor" if sensor_phase else "startup",
            }
            try:
                if sensor_phase and fault == "slow":
                    time.sleep(0.15)
                if (
                    sensor_phase
                    and fault == "exception"
                    and camera.identity.frame >= 10
                ):
                    raise RuntimeError(
                        "injected backend exception from playback frame10"
                    )
                return detector.infer(camera)
            finally:
                call["complete_wall_ns"] = time.monotonic_ns()
                model_calls.append(call)

    begun = time.monotonic_ns()

    def source_now():
        return time.monotonic_ns() - begun

    worker = LatestFrameWorker(Backend(), source_now, require_preparation=prepare)
    report = {
        "status": "FAIL",
        "fault": fault,
        "execution": execution,
        "providers": detector.session.get_providers(),
        "provider_options": detector.session.get_provider_options(),
        "source_clock": "simulated media playback elapsed ns",
        "wall_clock": "host monotonic ns; camera acquisition latency NOT MEASURED",
        "dataset_sha256": sha256_file(dataset),
        "profile_sha256": sha256_file(PROFILE_PATH),
        "requested_period_ns": 50_000_000,
        "input_frames": len(media),
        "dataset_repeats": repeats,
        "explicit_preparation": prepare,
        "model_initialization_wall_ns": initialization_ns,
        "runtime": runtime_identity(),
        "submitted": [],
        "consumer": [],
    }
    try:
        if prepare:
            if not worker.prepare() or not worker.wait_ready(11):
                raise ValueError("explicit startup preparation failed")
            report["preparation"] = worker.status()["preparation"]
            sensor_phase = True
            begun = time.monotonic_ns()
        if not worker.start_session(1, 77, 0):
            raise ValueError("worker INIT")
        index = 0
        next_consumer = 0
        while index < len(media):
            now = source_now()
            if now >= next_consumer:
                snapshot = worker.snapshot()
                checked = source_now()
                if (
                    snapshot
                    and not snapshot.identity.source_ns <= checked < snapshot.expires_ns
                ):
                    raise ValueError("expired snapshot consumed")
                report["consumer"].append(
                    {
                        "now_ns": checked,
                        "frame": snapshot.identity.frame if snapshot else None,
                        "source_ns": snapshot.identity.source_ns if snapshot else None,
                        "expires_ns": snapshot.expires_ns if snapshot else None,
                    }
                )
                next_consumer = (now // 20_000_000 + 1) * 20_000_000
            scheduled = index * 50_000_000
            if now >= scheduled:
                row, original = media[index]
                # Missed input slots are counted as skipped, never replayed late.
                if now - scheduled >= 50_000_000:
                    report["submitted"].append(
                        {"frame": index + 1, "scheduled_ns": scheduled, "skipped": True}
                    )
                else:
                    camera = replace(
                        original, identity=FrameIdentity(1, 77, index + 1, scheduled)
                    )
                    before = time.monotonic_ns()
                    accepted = worker.submit(camera)
                    report["submitted"].append(
                        {
                            "frame": index + 1,
                            "scheduled_ns": scheduled,
                            "submitted_wall_ns": before,
                            "original_frame": original.identity.frame,
                            "original_source_ns": original.identity.source_ns,
                            "accepted": accepted,
                            "skipped": False,
                        }
                    )
                index += 1
            else:
                time.sleep(min(0.001, (scheduled - now) / 1e9))
        if not worker.drain(10):
            raise TimeoutError("finite worker drain")
        report["worker"] = worker.status()
        report["model_calls"] = model_calls
        sensor_calls = [row for row in model_calls if row["phase"] == "sensor"]
        counters = report["worker"]["counters"]
        if (
            counters["submitted"]
            != counters["started"] + counters["overwritten"] + counters["cancelled"]
        ):
            raise ValueError("input accounting")
        if counters["started"] != counters["completed"] or counters["completed"] != sum(
            counters[k] for k in ("published", "late", "errors", "obsolete")
        ):
            raise ValueError("completion accounting")
        if len(sensor_calls) != counters["started"]:
            raise ValueError("backend denominator")
        if fault == "slow" and (
            counters["published"] or not counters["late"] or not counters["overwritten"]
        ):
            raise ValueError("slow backend admitted or overload not exercised")
        if fault == "exception" and not counters["errors"]:
            raise ValueError("exception not exercised")
        if fault == "none" and counters["errors"]:
            raise ValueError("unexpected backend error")
        submitted = {
            r["frame"]: r["submitted_wall_ns"]
            for r in report["submitted"]
            if not r["skipped"]
        }
        report["submit_to_backend_completion"] = distribution(
            [r["complete_wall_ns"] - submitted[r["frame"]] for r in sensor_calls]
        )
        report["status"] = "PASS"
    finally:
        report["closed"] = worker.close()
        report["final_worker"] = worker.status()
        if not report["closed"]:
            report["status"] = "FAIL"
        report["elapsed_wall_ns"] = time.monotonic_ns() - begun
        (output / "stream.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--fault", choices=("none", "slow", "exception"), default="none")
    p.add_argument("--execution", choices=("cpu", "cuda"), default="cpu")
    p.add_argument("--prepare", action="store_true")
    p.add_argument("--repeats", type=int, default=1)
    a = p.parse_args()
    report = run(
        a.dataset, a.model, a.output, a.fault, a.execution, a.prepare, a.repeats
    )
    print(json.dumps({k: report[k] for k in ("status", "fault", "worker", "closed")}))

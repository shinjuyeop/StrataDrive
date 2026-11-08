#!/usr/bin/env python3
"""Independent offline audit of live camera lineage, deadlines and denominators."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import FrameIdentity, Detection, uint, sha256_file
from physical_ai.perception.dataset import read_json


def require(value, reason):
    if not value:
        raise ValueError(reason)


def audit_preparation(report):
    require(report["state"] == "READY", "startup not ready")
    start, finish = report["started_wall_ns"], report["finished_wall_ns"]
    require(
        uint(start) and uint(finish) and 0 <= finish - start < 10_000_000_000,
        "startup budget",
    )
    require(len(report["calls"]) == 3, "startup denominator")
    prior = start
    for number, call in enumerate(report["calls"], 1):
        require(call["number"] == number and not call.get("error"), "startup call")
        stamp, elapsed = call["started_wall_ns"], call["elapsed_wall_ns"]
        require(
            uint(stamp)
            and uint(elapsed)
            and prior <= stamp <= stamp + elapsed <= finish,
            "startup clocks",
        )
        require(number == 1 or elapsed < 100_000_000, "settled call budget")
        prior = stamp + elapsed


def audit(report):
    if report.get("rgb_postprocess") == "enabled":
        require(
            report["sensor_attributes"]["enable_postprocess_effects"] == "true",
            "RGB postprocess readback",
        )
        require(
            report["renderer_profile"]["schema"] == "m10-perception-carla-rgb-host-v1"
            and report["renderer_profile"]["server_quality"] == "Low"
            and report["renderer_profile"]["enable_postprocess_effects"] is True,
            "RGB renderer descriptor",
        )
        require(
            report["renderer_profile_sha256"]
            == report["runtime"]["source_files_sha256"][
                "profiles/perception-carla-rgb-host-v1.json"
            ],
            "renderer descriptor hash",
        )
    require(
        report["status"] == "PASS"
        and report["closed"]
        and not report["cleanup_errors"],
        "run/cleanup status",
    )
    audit_preparation(report["preparation"])
    require(
        report["preparation"]["finished_wall_ns"] <= report["stream_started_wall_ns"],
        "sensor before readiness",
    )
    require(
        report["final_worker"]["stopped"] and not report["final_worker"]["busy"],
        "backend still active",
    )
    count = report["requested_camera_frames"]
    require(uint(count, 1200, True), "camera denominator type")
    epoch_clock = (1, report["clock_instance"])
    enable_frame = report["enable_frame"]
    ticks = report["ticks"]
    require(len(ticks) == count * 5, "tick denominator")
    tick_map = {}
    last_source = report["enable_source_ns"]
    for index, tick in enumerate(ticks, 1):
        require(tick["frame"] == enable_frame + index, "tick ownership")
        require(
            abs(tick["source_ns"] - last_source - 10_000_000) <= 1000,
            "tick source cadence",
        )
        require(
            tick["scheduled_wall_ns"] <= tick["begin_wall_ns"] <= tick["end_wall_ns"],
            "tick wall chronology",
        )
        tick_map[tick["frame"]] = tick
        last_source = tick["source_ns"]
    enabled = [
        r
        for r in report["callbacks"]
        if r["frame"] > enable_frame and r["outcome"] != "before_enable"
    ]
    require(len(enabled) == count, "camera callback denominator")
    if report.get("camera_clock") == "frame5":
        require(
            report["sensor_attributes"]["role_name"] == "m7_frame5",
            "camera scheduling role",
        )
        require(
            all(row["frame"] % 5 == 0 for row in enabled),
            "camera acquisition frame gate",
        )
    callbacks = {}
    for index, row in enumerate(enabled):
        require(
            row["frame"] in tick_map and row["frame"] not in callbacks, "camera lineage"
        )
        require(
            abs(row["source_ns"] - tick_map[row["frame"]]["source_ns"]) <= 1000,
            "camera source rewrite",
        )
        require(
            row["outcome"] in ("offered", "rejected", "injected_silence"),
            "camera outcome",
        )
        if index:
            require(
                row["frame"] - enabled[index - 1]["frame"] == 5
                and row["callback_wall_ns"] >= enabled[index - 1]["callback_wall_ns"],
                "camera cadence",
            )
        callbacks[row["frame"]] = row
    submissions = {}
    for row in report["submissions"]:
        identity = FrameIdentity(**row["identity"])
        identity.validate()
        number = identity.frame
        require(number in callbacks and number not in submissions, "submission lineage")
        require(
            (identity.epoch, identity.clock_instance) == epoch_clock,
            "submission session",
        )
        require(
            identity.source_ns == callbacks[number]["source_ns"],
            "submission timestamp rewrite",
        )
        require(callbacks[number]["outcome"] == "offered", "unoffered submission")
        require(
            callbacks[number]["callback_wall_ns"]
            <= row["received_wall_ns"]
            <= row["pump_wall_ns"],
            "receipt chronology",
        )
        submissions[number] = row
    calls = {}
    startup = [r for r in report["model_calls"] if r["phase"] == "startup"]
    require(len(startup) == 3, "startup backend denominator")
    for probe, call in zip(report["preparation"]["calls"], startup):
        require(
            call["identity"]
            == dict(
                epoch=1,
                clock_instance=1,
                frame=probe["number"],
                source_ns=0,
                camera_id=1,
                calibration_revision=1,
            ),
            "startup identity",
        )
        require(
            not call.get("error")
            and probe["started_wall_ns"]
            <= call["start_wall_ns"]
            <= call["complete_wall_ns"]
            <= probe["started_wall_ns"] + probe["elapsed_wall_ns"],
            "startup raw chronology",
        )
    for row in report["model_calls"]:
        if row["phase"] == "startup":
            continue
        require(row["phase"] == "sensor", "unknown call phase")
        number = row["identity"]["frame"]
        require(
            number in submissions
            and number not in calls
            and submissions[number]["accepted"],
            "backend lineage",
        )
        require(
            row["identity"] == submissions[number]["identity"],
            "backend identity rewrite",
        )
        require(
            submissions[number]["received_wall_ns"]
            <= row["start_wall_ns"]
            <= row["complete_wall_ns"],
            "backend wall chronology",
        )
        if "error" not in row:
            require(len(row["detections"]) <= 100, "detection bound")
            for d in row["detections"]:
                Detection(d["class_id"], d["score"], tuple(d["box"])).validate()
        calls[number] = row
    unique = set()
    previous_frame = 0
    for row in report["consumer"]:
        number = row["frame"]
        if number is None:
            continue
        require(
            number in calls and "error" not in calls[number],
            "consumer used missing/failed inference",
        )
        call, receipt = calls[number], submissions[number]["received_wall_ns"]
        source = call["identity"]["source_ns"]
        require(
            row["source_ns"] == source and row["expires_ns"] == source + 100_000_000,
            "consumer provenance/expiry",
        )
        require(
            source <= row["source_now_ns"] < source + 100_000_000,
            "stale source publication",
        )
        require(
            call["complete_wall_ns"] <= row["wall_ns"] < receipt + 100_000_000,
            "stale wall publication",
        )
        require(number >= previous_frame, "consumer replay")
        if number != previous_frame:
            require(
                row.get("detections") == call["detections"],
                "consumer detections changed",
            )
            unique.add(number)
        previous_frame = number
    worker, ingress = report["worker"]["counters"], report["ingress"]["counters"]
    require(
        all(uint(v) for v in worker.values())
        and all(uint(v) for v in ingress.values()),
        "counter type",
    )
    require(
        worker["submitted"]
        == sum(r["accepted"] for r in submissions.values())
        == ingress["submitted"],
        "submission denominator",
    )
    require(
        worker["started"] == worker["completed"] == len(calls), "completion denominator"
    )
    require(
        worker["submitted"]
        == worker["started"] + worker["overwritten"] + worker["cancelled"],
        "worker queue accounting",
    )
    require(
        worker["completed"]
        == sum(worker[k] for k in ("published", "late", "errors", "obsolete")),
        "worker result accounting",
    )
    require(
        ingress["accepted"]
        == sum(
            ingress[k] for k in ("overwritten", "submitted", "rejected", "cancelled")
        ),
        "ingress queue accounting",
    )
    require(
        len(unique) == report["unique_consumed"] <= worker["published"],
        "consumed denominator",
    )
    require(
        not report["ingress"]["pending"] and not report["worker"]["pending"],
        "unfinished queue",
    )
    cutoff = enable_frame + count * 5 // 2
    if report["fault"] == "slow":
        require(not worker["published"] and worker["late"] > 0, "slow fault admission")
    elif report["fault"] in ("blackout", "exception"):
        require(
            worker["errors"] > 0 and not any(n > cutoff for n in unique),
            "fault result admission",
        )
    elif report["fault"] == "silence":
        require(
            any(r["outcome"] == "injected_silence" for r in enabled)
            and not any(n > cutoff for n in calls),
            "silence injection",
        )
    elif report["fault"] == "none":
        require(
            not worker["errors"] and worker["published"] > 0, "normal inference failure"
        )
    else:
        raise ValueError("unknown fault")
    # Source is deliberately paused for500ms at the end. The final observations
    # must be unavailable even though their simulation timestamp stopped moving.
    require(
        any(
            r["wall_ns"] >= report["stream_finished_wall_ns"] + 400_000_000
            for r in report["consumer"]
        ),
        "paused source not exercised",
    )
    require(
        not any(
            r["frame"] is not None
            for r in report["consumer"]
            if r["wall_ns"] >= report["stream_finished_wall_ns"] + 200_000_000
        ),
        "paused source retained output",
    )
    return dict(
        status="PASS",
        camera_frames=count,
        backend_calls=len(calls),
        unique_consumed=len(unique),
        startup_calls=3,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run", type=Path)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    live = read_json(args.run)
    result = audit(live)
    server_path = args.run.parent.parent / "server.json"
    server = read_json(server_path)
    require(
        server["status"] == "PASS"
        and server["server_exit"] == 130
        and not server.get("forced_stop"),
        "owned server cleanup",
    )
    require(
        sha256_file(server_path.parent / "capture-probe.py") == server["probe_sha256"],
        "executed probe hash",
    )
    if live.get("camera_clock") == "frame5":
        require(
            "-StrataM7SensorFrame5" in server["argv"]
            and "-StrataM7NativeProbe" in server["argv"],
            "camera scheduler enable flags",
        )
    if live.get("rgb_postprocess") == "enabled":
        require("-quality-level=Low" in server["argv"], "renderer quality argv")
    result["server_sha256"] = sha256_file(server_path)
    result["live_sha256"] = sha256_file(args.run)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result))

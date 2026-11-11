#!/usr/bin/env python3
"""Independently replay native async traces without GPU, simulator or ground truth."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.async_native_v1 import NativeDetection, NativeResult
from physical_ai.perception.contract import FrameIdentity, LIFETIME_NS, sha256_file


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def validate_result(row):
    value = dict(row)
    value["identity"] = FrameIdentity(**value["identity"])
    value["detections"] = tuple(
        NativeDetection(d["class_id"], d["score"], tuple(d["box"]))
        for d in value["detections"]
    )
    result = NativeResult(**value)
    result.validate()
    return result


def audit(report):
    require(report["status"] == "PASS" and report["closed"], "component run/close")
    require(
        not any(
            report[k]
            for k in (
                "actual_vehicle_control",
                "live_camera",
                "runtime_promotion",
                "quality_acceptance",
                "live20Hz_acceptance",
                "cold_calls_excluded",
            )
        ),
        "scope/cold-call preservation",
    )
    state, camera, control = (
        report["traces"][k] for k in ("state", "camera", "control")
    )
    calls = report["model_calls"]
    c = report["worker"]["counters"]
    require(
        not report["thread_errors"] and not report["worker"]["clock_fault"],
        "owner clocks",
    )
    require(
        c["offered"] == len(camera) == c["accepted"] + c["rejected"]
        and c["accepted"] == sum(r["accepted"] for r in camera)
        and c["accepted"]
        == sum(c[k] for k in ("started", "overwritten", "cancelled", "expired_pending"))
        and c["started"] == c["completed"] == len(calls)
        and c["completed"]
        == sum(c[k] for k in ("published", "late", "errors", "obsolete")),
        "input/completion denominators",
    )
    require(
        report["fresh_output_observed"] == (c["published"] > 0),
        "fresh-output disclosure",
    )
    for rows in (state, camera, control):
        require(len(rows) > 1, "periodic owner progress")
        for a, b in zip(rows, rows[1:]):
            require(
                a["begin_wall_ns"] <= a["end_wall_ns"] <= b["begin_wall_ns"],
                "serial owner jobs",
            )
            require(a["index"] + 1 == b["index"], "owner job sequence")
    for index, row in enumerate(state):
        require(
            row["frame"] == index + 2 and row["source_ns"] == (index + 2) * 10_000_000,
            "observed10ms clock",
        )
    offered = {r["frame"]: r for r in camera if r["accepted"]}
    original_hashes = {r["bgra_sha256"] for r in report["media"]["originals"]}
    require(len(offered) == c["accepted"], "unique accepted input frames")
    by_frame = {}
    for call in calls:
        identity = FrameIdentity(**call["identity"])
        identity.validate()
        require(
            identity.frame not in by_frame and identity.frame in offered,
            "one call per accepted packet",
        )
        by_frame[identity.frame] = call
        source = offered[identity.frame]
        require(
            identity.source_ns == source["source_ns"]
            and identity.epoch == 1
            and identity.clock_instance == 77
            and source["original_bgra_sha256"] in original_hashes
            and source["begin_wall_ns"]
            <= call["received_wall_ns"]
            <= source["end_wall_ns"]
            and call["received_wall_ns"]
            <= call["begin_wall_ns"]
            <= call["end_wall_ns"],
            "original packet identity/receipt/provenance",
        )
        if "result" in call:
            result = validate_result(call["result"])
            require(
                asdict(result.identity) == call["identity"],
                "unchanged completion acquisition",
            )
    overlap = {
        name: sum(
            any(
                call["begin_wall_ns"] <= r["begin_wall_ns"] < call["end_wall_ns"]
                for call in calls
            )
            for r in rows
        )
        for name, rows in (("state", state), ("control", control))
    }
    require(
        overlap == report["overlap_jobs_during_backend"] and min(overlap.values()) > 0,
        "independent progress during inference",
    )
    consumed = set()
    for row in control:
        if row["perception"] is None:
            continue
        result = validate_result(row["perception"])
        call = by_frame[result.identity.frame]
        require(
            call["result"] == row["perception"], "consumer used the original result"
        )
        require(
            call["end_wall_ns"] <= row["end_wall_ns"]
            and row["snapshot_read_wall_ns"] < call["received_wall_ns"] + LIFETIME_NS
            and result.identity.source_ns
            <= row["snapshot_read_source_ns"]
            < result.expires_ns,
            "snapshot read bracket within original source/receipt lifetimes",
        )
        consumed.add(result.identity.frame)
    require(
        len(consumed) == report["unique_consumed_frames"] <= c["published"],
        "consumer denominator",
    )
    fault = report["fault"]
    if fault == "exception":
        require(
            c["errors"] == len(calls)
            and not c["published"]
            and all("error" in r for r in calls),
            "exception admission",
        )
    else:
        require(
            c["errors"] == 0 and all("result" in r for r in calls),
            "normal backend results",
        )
    if fault in ("slow", "blocked"):
        require(
            c["late"] > 0 and c["overwritten"] > 0 and c["published"] == 0,
            "late overload admission",
        )
    if fault == "blocked":
        require(
            report["before_backend_release"]["busy"],
            "backend still blocked at periodic-owner completion",
        )
        require(
            all(
                rows[-1]["end_wall_ns"] <= calls[0]["end_wall_ns"]
                for rows in (state, camera, control)
            ),
            "all owners completed before first blocked result",
        )
    return dict(
        status="PASS",
        fault=fault,
        calls=len(calls),
        consumed=len(consumed),
        overlap=overlap,
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("reports", type=Path, nargs="+")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    rows = []
    for path in args.reports:
        row = audit(json.loads(path.read_text()))
        row.update(path=str(path), sha256=sha256_file(path))
        rows.append(row)
    args.output.write_text(json.dumps(dict(status="PASS", rows=rows), indent=2) + "\n")
    print(json.dumps(dict(status="PASS", runs=len(rows))))


if __name__ == "__main__":
    main()

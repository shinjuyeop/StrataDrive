#!/usr/bin/env python3
"""Replay live camera/observed tick/consumer traces without CARLA or inference."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import FrameIdentity, LIFETIME_NS
from audit_async_native_v1 import require, validate_result
from audit_native_decisions_v1 import audit_decisions


def audit(r):
    require(
        r["status"] == "PASS" and r["closed"] and r["live_camera"], "live capture/close"
    )
    require(
        not any(
            r[k]
            for k in (
                "actual_vehicle_control",
                "runtime_promotion",
                "quality_acceptance",
                "live20Hz_acceptance",
                "cold_calls_excluded",
            )
        ),
        "live scope/cold calls",
    )
    require(
        not r["errors"] and not r["cleanup_errors"] and not r["recorder_overflow"],
        "no silent capture loss",
    )
    ticks, camera, consumers = (r["traces"][k] for k in ("state", "camera", "consumer"))
    calls = r["model_calls"]
    c = r["worker"]["counters"]
    require(
        not r["worker"]["clock_fault"]
        and not r["worker"]["busy"]
        and not r["worker"]["pending"],
        "clock/drain",
    )
    require(
        180 <= len(ticks) <= 184 and len(camera) <= r["recorder_capacity"] == 40,
        "finite actual tick/camera run",
    )
    require(
        c["offered"] == len(camera) == c["accepted"] + c["rejected"]
        and c["accepted"] == sum(x["accepted"] for x in camera)
        and c["accepted"]
        == sum(c[k] for k in ("started", "overwritten", "cancelled", "expired_pending"))
        and c["started"] == c["completed"] == len(calls)
        and c["completed"]
        == sum(c[k] for k in ("published", "late", "errors", "obsolete")),
        "complete input/call accounting",
    )
    prior_frame, prior_source = r["initial_frame"], r["initial_source_ns"]
    by_tick = {}
    for tick in ticks:
        require(
            tick["frame"] == prior_frame + 1
            and abs(tick["source_ns"] - prior_source - 10_000_000) <= 1000,
            "observed10ms tick continuity",
        )
        by_tick[tick["frame"]] = tick
        prior_frame, prior_source = tick["frame"], tick["source_ns"]
    require(
        prior_frame == r["last_planned_frame"] and prior_frame % 5 == 4,
        "last planned tick",
    )
    expected = [f for f in by_tick if f % 5 == 0]
    require(
        [x["frame"] for x in camera] == expected == [x["frame"] for x in r["raw"]],
        "all scheduled frame5 acquisitions recorded",
    )
    for x in camera:
        require(
            abs(x["source_ns"] - by_tick[x["frame"]]["source_ns"]) <= 1000
            and (x["width"], x["height"]) == (3840, 2304)
            and x["begin_wall_ns"] <= x["offer_entry_wall_ns"] <= x["end_wall_ns"],
            "actual acquisition identity/callback",
        )
    offered = {x["frame"]: x for x in camera if x["accepted"]}
    by_call = {}
    for call in calls:
        identity = FrameIdentity(**call["identity"])
        identity.validate()
        require(
            identity.frame in offered and identity.frame not in by_call,
            "one call per original packet",
        )
        by_call[identity.frame] = call
        image = offered[identity.frame]
        require(
            identity.clock_instance == r["clock_instance"]
            and identity.epoch == 1
            and identity.source_ns == image["source_ns"]
            and image["offer_entry_wall_ns"]
            <= call["received_wall_ns"]
            <= image["end_wall_ns"]
            and call["received_wall_ns"]
            <= call["begin_wall_ns"]
            <= call["end_wall_ns"],
            "unchanged original identity/receipt",
        )
        if "result" in call:
            require(
                asdict(validate_result(call["result"]).identity) == call["identity"],
                "completion source",
            )
        else:
            require("error" in call, "explicit failed model call")
    overlap = {
        name: sum(
            any(
                call["begin_wall_ns"] <= x["begin_wall_ns"] < call["end_wall_ns"]
                for call in calls
            )
            for x in rows
        )
        for name, rows in (("state", ticks), ("consumer", consumers))
    }
    require(
        min(overlap.values()) > 0,
        "independent observed tick and consumer progress during inference",
    )
    consumed = set()
    for row in consumers:
        if row["perception"] is None:
            continue
        result = validate_result(row["perception"])
        call = by_call[result.identity.frame]
        require(
            call["result"] == row["perception"]
            and call["end_wall_ns"] <= row["end_wall_ns"]
            and row["snapshot_read_wall_ns"] < call["received_wall_ns"] + LIFETIME_NS
            and result.identity.source_ns
            <= row["snapshot_read_source_ns"]
            < result.expires_ns,
            "consumer original result and exclusive dual expiry",
        )
        consumed.add(result.identity.frame)
    require(
        len(consumed) == r["unique_consumed_frames"] <= c["published"]
        and r["fresh_output_observed"] == (c["published"] > 0),
        "fresh denominator",
    )
    require(r["condition"] in ("baseline", "kernel"), "declared live condition")
    if r["condition"] == "kernel":
        require(len(consumed) > 0, "live kernel fresh output consumption")
    decisions = audit_decisions(r)
    silence = [
        x
        for x in consumers
        if x["snapshot_read_wall_ns"] >= r["sensor_stopped_wall_ns"] + LIFETIME_NS
    ]
    require(
        len(silence) >= 5
        and all(
            x["perception"] is None and x["snapshot_read_source_ns"] == prior_source
            for x in silence
        ),
        "wall expiry with stopped source clock",
    )
    return dict(
        status="PASS",
        actual_ticks=len(ticks),
        images=len(camera),
        calls=len(calls),
        consumed=len(consumed),
        overlap=overlap,
        silence_reads=len(silence),
        decisions=decisions,
        acceptance="fresh_output" if r["condition"] == "kernel" else "diagnostic_only",
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("report", type=Path)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    result = audit(json.loads(a.report.read_text()))
    a.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()

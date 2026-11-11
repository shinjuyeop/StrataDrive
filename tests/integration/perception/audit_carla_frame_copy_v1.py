"""Independent provenance, finite copy accounting and backend stage joins."""

from audit_async_native_v1 import require
from audit_carla_readback_pool_v1 import audit_capture as parent_capture
from audit_carla_readback_pool_v1 import audit_readback as parent_readback
from physical_ai.perception.run import distribution

CONDITIONS = ("copy-baseline-01", "copy-prefault-01", "copy-prefault-02")
STAGES = ("begin", "gray", "health", "resize", "tensor", "inference", "decode", "end")


def normalized(report):
    require(
        report["condition"] in CONDITIONS
        and report["schema"] == "m10-carla-frame-copy-v1",
        "copy condition/schema",
    )
    return dict(
        report, condition="pool-baseline-01", schema="m10-carla-readback-pool-v1"
    )


def audit_details(r):
    normalized(r)
    require(not r["copy_errors"], "no copy fallback or overflow")
    prep = r["copy_preparation"]
    final = r["copy_final"]
    require(
        prep["begin_wall_ns"] <= prep["end_wall_ns"] <= r["enabled_wall_ns"]
        and prep["end_wall_ns"] - prep["begin_wall_ns"] < 10_000_000_000,
        "copy allocation before enable",
    )
    images = r["traces"]["camera"]
    if r["condition"].startswith("copy-prefault-"):
        require(
            prep["mode"] == "prefault"
            and prep["pool"]["capacity"] == 120
            and prep["pool"]["reserved"] == prep["pool"]["completed"] == 0
            and prep["pool"]["allocated_bytes"] == 120 * 3840 * 2304 * 4
            and 0
            < prep["pool"]["allocation_ns"]
            <= prep["end_wall_ns"] - prep["begin_wall_ns"],
            "finite prefaulted preparation",
        )
        require(
            final["reserved"] == final["completed"] == len(images)
            and final["capacity"] == 120
            and final["allocated_bytes"] == prep["pool"]["allocated_bytes"]
            and final["allocation_ns"] == prep["pool"]["allocation_ns"],
            "one new immutable slot per callback",
        )
    else:
        require(
            prep["mode"] == "baseline" and prep["pool"] is None and final is None,
            "matched baseline copy",
        )
    fields = (
        "begin_wall_ns",
        "view_ready_wall_ns",
        "copy_end_wall_ns",
        "offer_entry_wall_ns",
        "offer_end_wall_ns",
        "end_wall_ns",
    )
    for row in images:
        require(
            all(type(row[k]) is int and row[k] > 0 for k in fields)
            and all(row[b] >= row[a] for a, b in zip(fields, fields[1:])),
            "ordered callback stages",
        )
    calls = r["preparation_calls"] + r["model_calls"]
    stages = r["backend_stages"]
    require(
        len(calls) == len(stages) <= 4096, "all preparation and sensor stages retained"
    )
    for call, row in zip(calls, stages):
        require(
            call["identity"] == row["identity"]
            and call["owner_thread_id"] == row["owner_thread_id"]
            and "error" not in row
            and call["begin_wall_ns"]
            <= row["begin"]
            <= row["end"]
            <= call["end_wall_ns"],
            "stage identity and original owner",
        )
        require(
            all(type(row[k]) is int and row[k] > 0 for k in STAGES)
            and all(row[b] >= row[a] for a, b in zip(STAGES, STAGES[1:])),
            "ordered backend stages",
        )
        result = call["result"]
        require(
            result["convert_ns"] == 0
            and result["preprocess_ns"] == row["tensor"] - row["begin"]
            and result["inference_ns"] == row["inference"] - row["tensor"]
            and result["postprocess_ns"] == row["decode"] - row["inference"],
            "unchanged result timing provenance",
        )
    sensor = stages[len(r["preparation_calls"]) :]
    metrics = {
        b: distribution([x[b] - x[a] for x in sensor])
        for a, b in zip(STAGES, STAGES[1:])
    }
    callbacks = {
        b: distribution([x[b] - x[a] for x in images])
        for a, b in zip(fields, fields[1:])
    }
    return dict(
        sensor_stages=len(sensor),
        preparation_stages=len(r["preparation_calls"]),
        stages=metrics,
        callback=callbacks,
        copy_preparation=prep,
    )


def audit_capture(report):
    details = audit_details(report)
    result = parent_capture(normalized(report))
    return dict(result, copy=details)


def audit_readback(report, log):
    return parent_readback(normalized(report), log)

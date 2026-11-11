"""Audit explicit native preparation and sampled availability without GPU."""

from dataclasses import asdict
from physical_ai.perception.availability_v1 import availability
from audit_async_native_v1 import require, validate_result, audit as audit_replay
from audit_native_decisions_v1 import audit_decisions


def audit_preparation(r):
    prep = r["preparation"]
    rows, calls = prep["calls"], r["preparation_calls"]
    require(prep["state"] == "READY" and not prep["error"], "preparation READY")
    require(len(rows) == len(calls) == 3, "all three cold preparation calls")
    require(
        0 <= prep["finished_wall_ns"] - prep["started_wall_ns"] < 10_000_000_000,
        "exclusive preparation budget",
    )
    owners = set()
    prior = prep["started_wall_ns"]
    for index, (row, call) in enumerate(zip(rows, calls), 1):
        require(
            row["number"] == index and row["synthetic"] and not row["published"],
            "synthetic isolation",
        )
        require("error" not in row and "error" not in call, "preparation exception")
        require(
            prior
            <= row["begin_wall_ns"]
            == call["received_wall_ns"]
            <= call["begin_wall_ns"]
            <= call["end_wall_ns"]
            <= row["end_wall_ns"]
            <= prep["finished_wall_ns"],
            "preparation complete call timing",
        )
        require(
            row["elapsed_wall_ns"] == row["end_wall_ns"] - row["begin_wall_ns"],
            "preparation elapsed",
        )
        if index > 1:
            require(row["elapsed_wall_ns"] < 100_000_000, "settled exclusive budget")
        identity = dict(
            epoch=1,
            clock_instance=1,
            frame=index,
            source_ns=0,
            camera_id=1,
            calibration_revision=1,
        )
        require(
            call["identity"]
            == identity
            == asdict(validate_result(row["result"]).identity)
            and call["result"] == row["result"],
            "synthetic native identity/result",
        )
        require(row["owner_thread_id"] == call["owner_thread_id"], "preparation owner")
        owners.add(call["owner_thread_id"])
        prior = row["end_wall_ns"]
    for call in r["model_calls"]:
        require(call["begin_wall_ns"] >= prep["finished_wall_ns"], "sensor after READY")
        owners.add(call["owner_thread_id"])
    require(
        len(owners) == 1 and r["model_calls"], "same preparation and inference owner"
    )
    require(
        r["preparation_final"]["state"] == "CANCELLED"
        and r["preparation_final"]["calls"] == rows,
        "bounded shutdown keeps all cold calls",
    )
    consumers = r["traces"]["consumer" if r["live_camera"] else "control"]
    require(
        all(
            x["perception"] is None or x["perception"]["identity"]["source_ns"] != 0
            for x in consumers
        ),
        "no synthetic publication",
    )
    return dict(
        status="PASS",
        startup_calls=3,
        sensor_calls=len(r["model_calls"]),
        total_backend_calls=3 + len(r["model_calls"]),
        same_owner=True,
        startup_elapsed_ns=prep["finished_wall_ns"] - prep["started_wall_ns"],
    )


def audit(r):
    result = audit_replay(r)
    require(
        r["requested_camera_hz"] in (10, 13, 20)
        and r["periods_ns"]
        == dict(
            state=10_000_000,
            camera=round(1e9 / r["requested_camera_hz"]),
            control=20_000_000,
        )
        and r["duration_seconds"] == 6
        and r["fault"] == "none",
        "declared replay rate",
    )
    measured = availability(
        r["traces"]["control"], r["model_calls"], r["begin_wall_ns"], r["end_wall_ns"]
    )
    require(measured == r["availability"], "recomputed sampled availability")
    result.update(
        preparation=audit_preparation(r),
        decisions=audit_decisions(r),
        availability=measured,
        requested_camera_hz=r["requested_camera_hz"],
    )
    return result

"""Replay original owner semantics and independently join renderer/camera traces."""

import json
import math

from audit_async_native_v1 import require
from audit_carla_world_async_v1 import audit as audit_world
from physical_ai.perception.run import distribution

CONDITIONS = ("baseline-01", "deferred-01", "deferred-02", "baseline-02")
PREFIX = "STRATA_READBACK_V1 "
STAGES = (
    "capture",
    "render",
    "copy",
    "flush",
    "query",
    "worker",
    "ready",
    "lock",
    "send",
    "end",
)


def audit_capture(report):
    require(report["condition"] in CONDITIONS, "readback condition")
    require(report["schema"] == "m10-carla-readback-v1", "readback schema")
    # Reuse the frozen state/deadline auditor through a shallow identity adapter.
    # No experimental report is edited; all four conditions are actually async.
    return audit_world(dict(report, condition="async-01"))


def parse_trace(log, deferred):
    rows = []
    for line in log.splitlines():
        if PREFIX not in line:
            continue
        require(line.startswith(PREFIX), "unambiguous readback line")
        row = json.loads(line[len(PREFIX) :])
        require(
            set(row)
            == set(STAGES)
            | {"frame", "timestamp", "deferred", "serial", "inflight", "error"},
            "trace schema",
        )
        require(
            row["deferred"] is deferred and row["error"] == "",
            "mode or readback failure",
        )
        for key in (*STAGES, "frame", "serial", "inflight"):
            require(type(row[key]) is int and row[key] > 0, "integer trace value")
        require(
            isinstance(row["timestamp"], (int, float))
            and math.isfinite(row["timestamp"])
            and row["timestamp"] > 0,
            "source timestamp",
        )
        require(
            1 <= row["inflight"] <= 3 and row["frame"] % 5 == 0, "bounded acquisition"
        )
        require(
            all(row[b] >= row[a] for a, b in zip(STAGES, STAGES[1:])), "stage order"
        )
        require(
            not deferred or row["flush"] == row["query"],
            "deferred has no blocking query",
        )
        rows.append(row)
    require(0 < len(rows) <= 4096, "bounded complete trace")
    require(len({r["frame"] for r in rows}) == len(rows), "duplicate capture")
    require(
        sorted(r["serial"] for r in rows) == list(range(1, len(rows) + 1)),
        "trace serial coverage",
    )
    # Resource slots last from game-thread admission until GPU resource release.
    events = sorted([(r["capture"], 1) for r in rows] + [(r["end"], -1) for r in rows])
    outstanding = peak = 0
    for _, delta in events:
        outstanding += delta
        peak = max(peak, outstanding)
    require(outstanding == 0 and peak <= 3, "bounded resource lifetime")
    return sorted(rows, key=lambda r: r["frame"])


def audit_readback(report, log):
    require(report["condition"] in CONDITIONS, "readback condition")
    rows = parse_trace(log, report["condition"].startswith("deferred-"))
    images = {x["frame"]: x for x in report["traces"]["camera"]}
    rendered = {x["frame"]: x for x in rows}
    require(set(images) <= set(rendered), "received frame without GPU trace")
    for frame, image in images.items():
        row = rendered[frame]
        require(
            abs(round(row["timestamp"] * 1e9) - image["source_ns"]) <= 1,
            "original capture timestamp",
        )
        require(
            row["lock"] <= image["begin_wall_ns"],
            "same host monotonic clock and delivery order",
        )
    stage_pairs = {
        "capture_to_render": ("capture", "render"),
        "copy_enqueue": ("render", "copy"),
        "rhi_flush_or_submit": ("copy", "flush"),
        "blocking_query": ("flush", "query"),
        "task_dispatch": ("query", "worker"),
        "fence_wait": ("worker", "ready"),
        "map": ("ready", "lock"),
        "buffer_copy_and_send": ("lock", "send"),
        "capture_to_send": ("capture", "send"),
    }
    metrics = {
        k: distribution([x[b] - x[a] for x in rows])
        for k, (a, b) in stage_pairs.items()
    }
    metrics["capture_to_callback"] = distribution(
        [x["begin_wall_ns"] - rendered[f]["capture"] for f, x in images.items()]
    )
    return dict(
        trace_rows=len(rows),
        received=len(images),
        captured_without_callback=sorted(set(rendered) - set(images)),
        inflight_peak=max(x["inflight"] for x in rows),
        metrics=metrics,
    )

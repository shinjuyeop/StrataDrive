#!/usr/bin/env python3
"""Post-capture audit tests; never changes acquisition or acceptance settings."""

from copy import deepcopy
import json
from pathlib import Path
import sys

sys.path.insert(
    0, str(Path(__file__).resolve().parents[4] / "tests/integration/perception")
)
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from audit_carla_world_async_v1 import audit
from physical_ai.perception.run import distribution


def metrics(r):
    expected = {}
    for name in ("state", "camera", "consumer"):
        rows = sorted(r["traces"][name], key=lambda x: x["begin_wall_ns"])
        expected[name] = dict(
            jobs=len(rows),
            observed_hz=(len(rows) - 1)
            * 1e9
            / (rows[-1]["begin_wall_ns"] - rows[0]["begin_wall_ns"]),
            job_wall=distribution(
                [x["end_wall_ns"] - x["begin_wall_ns"] for x in rows]
            ),
            interval_wall=distribution(
                [
                    b["begin_wall_ns"] - a["begin_wall_ns"]
                    for a, b in zip(rows, rows[1:])
                ]
            ),
        )
    expected["receipt_to_backend_return"] = distribution(
        [x["end_wall_ns"] - x["received_wall_ns"] for x in r["model_calls"]]
    )
    states = [
        x
        for x in r["traces"]["state"]
        if x["disposition"] == "accepted" and x["frame"] <= r["primary_end_frame"]
    ]
    first, last = states[0], states[-1]
    expected["simulation_realtime_factor"] = (
        last["source_ns"] - first["source_ns"]
    ) / (last["begin_wall_ns"] - first["begin_wall_ns"])
    expected["observed_world_hz"] = (
        (len(states) - 1) * 1e9 / (last["begin_wall_ns"] - first["begin_wall_ns"])
    )
    images = [
        x
        for x in r["traces"]["camera"]
        if r["enabled_wall_ns"] <= x["begin_wall_ns"] < r["primary_end_wall_ns"]
    ]
    expected["primary_camera_hz"] = (
        (len(images) - 1)
        * 1e9
        / (images[-1]["begin_wall_ns"] - images[0]["begin_wall_ns"])
    )
    if expected != r["metrics"]:
        raise ValueError("independently recomputed timing metrics")


def verify(r):
    if audit(r) != r["audit"]:
        raise ValueError("recomputed audit")
    metrics(r)


def mutate(r, case):
    sample = next(x for x in r["traces"]["consumer"] if x["perception"])
    if case == "world_mode":
        r["active_settings"]["synchronous_mode"] = not r["active_settings"][
            "synchronous_mode"
        ]
    elif case == "physics_interval":
        r["traces"]["state"][1]["delta_ns"] = 20_000_000
    elif case == "world_episode":
        r["traces"]["state"][1]["world_id"] += 1
    elif case == "source_gap_fabrication":
        r["traces"]["state"].pop(5)
    elif case == "state_receipt_renewal":
        sample["state"]["received_wall_ns"] += 1
    elif case == "state_result_race":
        sample["snapshot_read_source_ns"] += 10_000_000
    elif case == "original_receipt_renewal":
        r["model_calls"][0]["received_wall_ns"] += 1
    elif case == "raw_omission":
        r["raw"].pop()
    elif case == "published_clock_renewal":
        next(x for x in r["decisions"]["rows"] if x["outcome"] == "published")[
            "decision_wall_ns"
        ] += 100_000_000
    elif case == "unavailable_as_fresh":
        r["availability"]["active_ticks"]["available_samples"] += 1
    elif case == "rate_claim":
        r["metrics"]["primary_camera_hz"] += 1
    elif case == "hidden_tick_request":
        if r["condition"].startswith("async-"):
            r["traces"]["tick_requests"].append(dict(frame=1))
        else:
            r["traces"]["tick_requests"] = []


def main():
    e = Path(sys.argv[1])
    output = Path(sys.argv[2])
    results = {}
    if output.exists():
        raise ValueError("new output required")
    runs = json.loads((e / "runs.json").read_text())
    cases = (
        "world_mode",
        "physics_interval",
        "world_episode",
        "source_gap_fabrication",
        "state_receipt_renewal",
        "state_result_race",
        "original_receipt_renewal",
        "raw_omission",
        "published_clock_renewal",
        "unavailable_as_fresh",
        "rate_claim",
        "hidden_tick_request",
    )
    for name in runs["conditions"].values():
        r = json.loads((e / name / "capture/result.json").read_text())
        verify(r)
        rejected = []
        for case in cases:
            altered = deepcopy(r)
            mutate(altered, case)
            try:
                verify(altered)
            except (ValueError, KeyError, TypeError, AssertionError):
                rejected.append(case)
            else:
                raise AssertionError("undetected mutation: " + case)
        results[name] = dict(
            status="PASS", metrics_recomputed=True, rejected_mutations=rejected
        )
    result = dict(
        status="PASS",
        conditions=results,
        mutation_count=sum(len(x["rejected_mutations"]) for x in results.values()),
    )
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()

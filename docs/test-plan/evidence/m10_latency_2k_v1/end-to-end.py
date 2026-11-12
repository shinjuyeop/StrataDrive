"""Join original GPU capture and final model/consumer timestamps on this Host."""

from audit_carla_readback_v1 import parse_trace
from physical_ai.perception.run import distribution


def end_to_end(report, log):
    gpu = {x["frame"]: x for x in parse_trace(log, report["variant"] == "balanced")}
    calls = {x["identity"]["frame"]: x for x in report["model_calls"]}
    reads = {}
    for row in report["traces"]["consumer"]:
        if row["perception"]:
            frame = row["perception"]["identity"]["frame"]
            reads[frame] = min(
                reads.get(frame, row["snapshot_read_wall_ns"]),
                row["snapshot_read_wall_ns"],
            )
    decisions = {x["identity"]["frame"]: x for x in report["decisions"]["rows"]}
    complete = [x["end_wall_ns"] - gpu[f]["capture"] for f, x in calls.items()]
    publish = [
        x["decision_wall_ns"] - gpu[f]["capture"]
        for f, x in decisions.items()
        if x["outcome"] == "published"
    ]
    consumed = [wall - gpu[f]["capture"] for f, wall in reads.items()]
    queue = [x["begin_wall_ns"] - x["received_wall_ns"] for x in calls.values()]
    assert all(x >= 0 for x in complete + publish + consumed + queue)
    return dict(
        capture_to_backend_return=distribution(complete),
        capture_to_publication=distribution(publish),
        capture_to_first_consumption=distribution(consumed),
        offer_to_backend_start=distribution(queue),
        scope="Host monotonic wall intervals; all calls and original capture identity; not accuracy",
    )

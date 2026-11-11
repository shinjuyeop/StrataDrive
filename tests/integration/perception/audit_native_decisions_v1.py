"""Recompute completion disposition from the original source and receipt clocks."""

from collections import Counter

from audit_async_native_v1 import require
from physical_ai.perception.contract import LIFETIME_NS


def audit_decisions(report):
    trace = report["decisions"]
    calls = {x["identity"]["frame"]: x for x in report["model_calls"]}
    rows = trace["rows"]
    counts = report["worker"]["counters"]
    require(
        not trace["overflow"] and len(rows) == len(calls) == counts["completed"],
        "complete bounded decision trace",
    )
    seen, causes, outcomes = set(), Counter(), Counter()
    for row in rows:
        frame = row["identity"]["frame"]
        require(frame in calls and frame not in seen, "one decision per call")
        seen.add(frame)
        call = calls[frame]
        require(
            row["identity"] == call["identity"]
            and row["received_wall_ns"] == call["received_wall_ns"],
            "original decision dependency",
        )
        outcome = row["outcome"]
        require(
            outcome in ("published", "late", "errors", "obsolete"),
            "decision disposition",
        )
        outcomes[outcome] += 1
        require(
            row["received_wall_ns"]
            <= row["started_wall_ns"]
            <= call["begin_wall_ns"]
            <= call["end_wall_ns"]
            <= row["backend_return_monotonic_ns"],
            "queue and backend timeline",
        )
        if outcome == "obsolete":
            require(
                row["decision_source_ns"] is None and row["decision_wall_ns"] is None,
                "obsolete result has no admission clock",
            )
            continue
        source, wall = row["decision_source_ns"], row["decision_wall_ns"]
        require(
            row["started_source_ns"] <= source
            and row["backend_return_monotonic_ns"] <= wall,
            "actual decision clocks",
        )
        source_expired = source >= row["identity"]["source_ns"] + LIFETIME_NS
        receipt_expired = wall >= row["received_wall_ns"] + LIFETIME_NS
        require(
            row["source_expired"] == source_expired
            and row["receipt_expired"] == receipt_expired,
            "unmodified exclusive deadline decision",
        )
        if outcome == "late":
            require(source_expired or receipt_expired, "late cause required")
            causes[
                "both"
                if source_expired and receipt_expired
                else "source_only"
                if source_expired
                else "receipt_only"
            ] += 1
        elif outcome == "published":
            require(
                not source_expired and not receipt_expired and "result" in call,
                "fresh publication required",
            )
    require(
        all(
            outcomes[k] == counts[k]
            for k in ("published", "late", "errors", "obsolete")
        ),
        "decision counters",
    )
    consumers = report["traces"].get("consumer", report["traces"].get("control"))
    published = {r["identity"]["frame"]: r for r in rows if r["outcome"] == "published"}
    for item in consumers:
        if item["perception"]:
            frame = item["perception"]["identity"]["frame"]
            require(
                frame in published
                and published[frame]["decision_wall_ns"] <= item["end_wall_ns"],
                "consumer used a published result",
            )
    return dict(
        status="PASS",
        decisions=len(rows),
        outcomes=dict(outcomes),
        late_causes=dict(causes),
    )

"""Prospective bounded development selection;20Hz is never an eligibility gate."""


def eligibility(baseline, candidate):
    b = baseline["end_to_end"]["capture_to_backend_return"]
    c = candidate["end_to_end"]["capture_to_backend_return"]
    checks = dict(
        baseline_valid=baseline["status"] == "PASS" and baseline["raw_verified"],
        candidate_valid=candidate["status"] == "PASS" and candidate["raw_verified"],
        mean_improves_three_ms=c["mean_ms"] <= b["mean_ms"] - 3,
        p95_within_five_percent=c["p95_ms"] <= b["p95_ms"] * 1.05,
        camera_retains_ninety_five_percent=candidate["camera_hz"]
        >= baseline["camera_hz"] * 0.95,
        availability_within_five_points=candidate["fresh_fraction"]
        >= baseline["fresh_fraction"] - 0.05,
        paced_not_faster_than_real_time=candidate["variant"] != "balanced"
        or candidate["realtime_factor"] <= 1.05,
    )
    return dict(eligible=all(checks.values()), checks=checks)


def select(baseline, candidates):
    outcomes = {r["variant"]: eligibility(baseline, r) for r in candidates}
    eligible = [r for r in candidates if outcomes[r["variant"]]["eligible"]]
    eligible.sort(
        key=lambda r: (
            r["end_to_end"]["capture_to_backend_return"]["mean_ms"],
            r["end_to_end"]["capture_to_backend_return"]["p95_ms"],
        )
    )
    selected = eligible[0]["variant"] if eligible else None
    if len(eligible) == 2:
        gap = abs(
            eligible[0]["end_to_end"]["capture_to_backend_return"]["mean_ms"]
            - eligible[1]["end_to_end"]["capture_to_backend_return"]["mean_ms"]
        )
        if gap < 3:
            selected = "tensor"
    return dict(
        schema="m10-latency-selection-v1",
        selected_variant=selected,
        eligible=outcomes,
        mandatory20Hz=False,
        runtime_promotion=False,
    )

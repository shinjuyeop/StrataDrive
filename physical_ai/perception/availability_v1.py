"""Sampled availability/age diagnostics; no extrapolation, interpolation or gate change."""

from .run import distribution


def availability(rows, calls, begin_ns, end_ns):
    if not begin_ns < end_ns:
        raise ValueError("nonempty observation window")
    by_frame = {r["identity"]["frame"]: r for r in calls}
    selected = [r for r in rows if begin_ns <= r["snapshot_read_wall_ns"] < end_ns]
    if not selected:
        raise ValueError("observation samples required")
    if any(
        b["snapshot_read_wall_ns"] <= a["snapshot_read_wall_ns"]
        for a, b in zip(selected, selected[1:])
    ):
        raise ValueError("strict observation wall order")
    fresh, gaps, active_gap, source_ages, receipt_ages = [], [], [], [], []
    for row in selected:
        result = row["perception"]
        if result is None:
            active_gap.append(row["snapshot_read_wall_ns"])
        else:
            if active_gap:
                gaps.append(active_gap)
                active_gap = []
            frame = result["identity"]["frame"]
            call = by_frame[frame]
            source_age = (
                row["snapshot_read_source_ns"] - result["identity"]["source_ns"]
            )
            receipt_age = row["snapshot_read_wall_ns"] - call["received_wall_ns"]
            if not 0 <= source_age < 100_000_000 or not 0 <= receipt_age < 100_000_000:
                raise ValueError("stale observation cannot count as available")
            fresh.append(frame)
            source_ages.append(source_age)
            receipt_ages.append(receipt_age)
    if active_gap:
        gaps.append(active_gap)
    return dict(
        samples=len(selected),
        available_samples=len(fresh),
        sampled_available_fraction=len(fresh) / len(selected),
        unique_frames=len(set(fresh)),
        unavailable_runs=len(gaps),
        longest_unavailable_sample_run=max((len(g) for g in gaps), default=0),
        longest_unavailable_first_to_last_ns=max(
            (g[-1] - g[0] for g in gaps), default=0
        ),
        source_age=distribution(source_ages) if source_ages else None,
        receipt_age=distribution(receipt_ages) if receipt_ages else None,
        interpretation="sampled reads and first-to-last sample spans; not exact continuous-time availability",
    )


def ideal_single_clock(period_ns, delay_ns, lifetime_ns=100_000_000):
    """Ideal lossless constant-delay sample/hold example, not a vehicle acceptance test."""
    if period_ns <= 0 or delay_ns < 0 or lifetime_ns <= 0:
        raise ValueError("positive periods/lifetime and nonnegative delay")
    valid = min(period_ns, max(0, lifetime_ns - delay_ns))
    return dict(
        period_ns=period_ns,
        delay_ns=delay_ns,
        lifetime_ns=lifetime_ns,
        available_fraction=valid / period_ns,
        gap_per_period_ns=period_ns - valid,
    )

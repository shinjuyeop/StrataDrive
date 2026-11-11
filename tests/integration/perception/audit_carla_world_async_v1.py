"""Independent replay of asynchronous world/state/perception observation evidence."""

from collections import Counter
from dataclasses import asdict

from audit_async_native_v1 import require, validate_result
from audit_native_startup_v1 import audit_preparation
from physical_ai.perception.availability_v1 import availability
from physical_ai.perception.contract import LIFETIME_NS
from physical_ai.perception.world_async_v1 import ObservedWorldClock


def audit(r):
    require(
        r["status"] == "PASS" and r["closed"] and r["live_camera"], "capture and close"
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
        "scope",
    )
    require(
        not r["errors"] and not r["cleanup_errors"] and not r["recorder_overflow"],
        "no hidden loss",
    )
    condition = r["condition"]
    require(condition in ("sync-01", "async-01", "async-02"), "declared condition")
    settings = r["active_settings"]
    require(
        settings["synchronous_mode"] == (condition == "sync-01")
        and abs(settings["fixed_delta_seconds"] - 0.01) < 1e-9
        and not settings["no_rendering_mode"],
        "actual fixed-step mode",
    )
    states, images, reads = (r["traces"][k] for k in ("state", "camera", "consumer"))
    requests = r["traces"]["tick_requests"]
    require(
        bool(requests) == (condition == "sync-01"),
        "async world has no client tick calls",
    )
    clock = ObservedWorldClock(r["clock_instance"])
    accepted = {}
    for x in states:
        disposition = clock.observe(
            x["world_id"],
            x["frame"],
            x["source_ns"],
            x["delta_ns"],
            x["begin_wall_ns"],
            x["end_wall_ns"],
        )
        require(disposition == x["disposition"], "snapshot disposition replay")
        if disposition == "accepted":
            accepted[x["frame"]] = x
    observation = r["world_observation"]
    require(
        clock.status() == observation["clock"] and not observation["overflow"],
        "observed clock replay",
    )
    require(
        not r["worker"]["clock_fault"]
        and not r["worker"]["busy"]
        and not r["worker"]["pending"],
        "owner drained without clock fault",
    )
    first, last = r["initial_frame"], r["last_planned_frame"]
    require(
        500 <= last - first + 1 <= 504
        and last % 5 == 4
        and r["primary_end_frame"] >= last,
        "finite predeclared source window",
    )
    require(
        states[0]["frame"] == first
        and first in accepted
        and r["primary_end_frame"] in accepted,
        "actual observed boundaries",
    )
    require(
        r["primary_end_wall_ns"] - r["mode_switch_begin_wall_ns"] < 30_000_000_000,
        "finite wall progress",
    )
    image_frames = [x["frame"] for x in images]
    require(len(image_frames) == len(set(image_frames)), "unique raw acquisition names")
    expected = set(range(first + (-first % 5), last + 1, 5))
    missing = sorted(expected - set(image_frames))
    extra = sorted(set(image_frames) - expected)
    raw = {x["frame"]: x for x in r["raw"]}
    require(
        set(raw) == set(image_frames) and len(raw) == len(r["raw"]),
        "all received raw retained",
    )
    offered = {}
    for x in images:
        require(
            x["frame"] % 5 == 0
            and (x["width"], x["height"]) == (3840, 2304)
            and x["begin_wall_ns"] <= x["offer_entry_wall_ns"] <= x["end_wall_ns"],
            "camera provenance",
        )
        require(
            raw[x["frame"]]["source_ns"] == x["source_ns"]
            and raw[x["frame"]]["raw_bytes"] == 3840 * 2304 * 4,
            "original raw identity",
        )
        if x["accepted"]:
            require(x["offered"], "accepted only actual offer")
            offered[x["frame"]] = x
    counts = r["worker"]["counters"]
    calls = r["model_calls"]
    require(
        counts["offered"]
        == sum(x["offered"] for x in images)
        == counts["accepted"] + counts["rejected"]
        and counts["accepted"]
        == len(offered)
        == sum(
            counts[k]
            for k in ("started", "overwritten", "cancelled", "expired_pending")
        )
        and counts["started"]
        == counts["completed"]
        == len(calls)
        == sum(counts[k] for k in ("published", "late", "errors", "obsolete")),
        "input/call accounting",
    )
    by_call = {}
    for call in calls:
        ident = validate_result(
            call["result"]
        ).identity  # backend exceptions fail this probe
        image = offered[ident.frame]
        require(
            asdict(ident) == call["identity"]
            and ident.epoch == 1
            and ident.clock_instance == r["clock_instance"]
            and ident.frame not in by_call
            and ident.frame in accepted
            and ident.source_ns == image["source_ns"]
            and abs(ident.source_ns - accepted[ident.frame]["source_ns"]) <= 1000
            and image["offer_entry_wall_ns"]
            <= call["received_wall_ns"]
            <= image["end_wall_ns"]
            and call["received_wall_ns"]
            <= call["begin_wall_ns"]
            <= call["end_wall_ns"],
            "unaltered original input and actual snapshot match",
        )
        by_call[ident.frame] = call
    decisions = r["decisions"]
    require(
        not decisions["overflow"] and len(decisions["rows"]) == len(calls),
        "complete decisions",
    )
    outcomes, causes, published, seen = Counter(), Counter(), {}, set()
    for row in decisions["rows"]:
        frame = row["identity"]["frame"]
        require(frame not in seen and frame in by_call, "one decision per call")
        seen.add(frame)
        call = by_call[frame]
        require(
            row["identity"] == call["identity"]
            and row["received_wall_ns"] == call["received_wall_ns"]
            and row["received_wall_ns"]
            <= row["started_wall_ns"]
            <= call["begin_wall_ns"]
            <= call["end_wall_ns"]
            <= row["backend_return_monotonic_ns"],
            "decision provenance",
        )
        outcome = row["outcome"]
        require(outcome in ("published", "late", "errors", "obsolete"), "disposition")
        outcomes[outcome] += 1
        if outcome == "obsolete":
            require(
                row["decision_source_ns"] is None and row["decision_wall_ns"] is None,
                "obsolete has no admission",
            )
            continue
        if outcome == "errors" and row["decision_wall_ns"] is None:
            require(
                row["decision_source_ns"] is None
                and any(
                    x["kind"] == "stale_read"
                    and x["completed"] == len(seen)
                    and x["wall_ns"] >= row["backend_return_monotonic_ns"]
                    and x["wall_ns"] >= x["received_wall_ns"] + LIFETIME_NS
                    for x in observation["rows"]
                ),
                "explicit state silence invalidation",
            )
            continue
        source, wall = row["decision_source_ns"], row["decision_wall_ns"]
        require(
            row["started_source_ns"] <= source
            and row["backend_return_monotonic_ns"] <= wall,
            "decision clocks",
        )
        se = source >= row["identity"]["source_ns"] + LIFETIME_NS
        re = wall >= row["received_wall_ns"] + LIFETIME_NS
        require(
            se == row["source_expired"] and re == row["receipt_expired"],
            "exclusive dual deadlines",
        )
        if outcome == "late":
            require(se or re, "late cause")
            causes[
                "both" if se and re else "source_only" if se else "receipt_only"
            ] += 1
        elif outcome == "published":
            require(
                not se
                and not re
                and any(
                    x["source_ns"] == source
                    and x["begin_wall_ns"] <= wall < x["begin_wall_ns"] + LIFETIME_NS
                    for x in accepted.values()
                ),
                "fresh result and recent actual state",
            )
            published[frame] = row
        else:
            require(False, "unexpected backend error")
    require(
        all(
            outcomes[k] == counts[k]
            for k in ("published", "late", "errors", "obsolete")
        ),
        "decision counters",
    )
    consumed = set()
    for row in reads:
        if row["perception"] is None:
            continue
        result = validate_result(row["perception"])
        frame = result.identity.frame
        call = by_call[frame]
        state, wall = row["state"], row["snapshot_read_wall_ns"]
        require(
            frame in published
            and call["result"] == row["perception"]
            and published[frame]["decision_wall_ns"] <= wall
            and state["frame"] in accepted
            and state["source_ns"] == row["snapshot_read_source_ns"]
            and state["received_wall_ns"] == accepted[state["frame"]]["begin_wall_ns"]
            and 0 <= wall - state["received_wall_ns"] < LIFETIME_NS
            and result.identity.source_ns
            <= row["snapshot_read_source_ns"]
            < result.expires_ns
            and call["received_wall_ns"]
            <= wall
            < call["received_wall_ns"] + LIFETIME_NS,
            "atomic consumer sample with original dual deadlines and recent actual state",
        )
        consumed.add(frame)
    require(
        len(consumed) == r["unique_consumed_frames"] <= counts["published"]
        and r["fresh_output_observed"] == (counts["published"] > 0),
        "fresh denominator",
    )
    segments = [
        len(consumed & set(range(first + i, first + i + 100)))
        for i in range(0, 500, 100)
    ]
    require(min(segments) > 0, "fresh consumption in each of five source segments")
    overlap = {
        key: sum(
            any(
                call["begin_wall_ns"] <= x["begin_wall_ns"] < call["end_wall_ns"]
                for call in calls
            )
            for x in rows
        )
        for key, rows in (("state", states), ("consumer", reads))
    }
    require(
        min(overlap.values()) > 0, "independent state and observer during inference"
    )
    recorder = r["recorder"]
    require(
        recorder["stopped"]
        and not recorder["errors"]
        and not recorder["overflow"]
        and recorder["offered"] == len(images)
        and recorder["capacity"] == 240
        and recorder["mode"] == "finite-memory"
        and recorder["disk_frames_during_measurement"] == 0
        and recorder["peak_memory_frames"] == len(images)
        and recorder["peak_raw_bytes"] == len(images) * 3840 * 2304 * 4
        and [x["frame"] for x in recorder["records"]] == image_frames,
        "all finite raw recording",
    )
    measured = {
        name: availability(reads, calls, r["enabled_wall_ns"], end)
        for name, end in (
            ("active_ticks", r["primary_end_wall_ns"]),
            ("including_delivery_tail", r["sensor_stopped_wall_ns"]),
        )
    }
    require(measured == r["availability"], "all-window availability recomputed")
    silence = [
        x
        for x in reads
        if x["snapshot_read_wall_ns"] >= r["sensor_stopped_wall_ns"] + LIFETIME_NS
    ]
    require(
        len(silence) >= 5 and all(x["perception"] is None for x in silence),
        "camera silence expiry",
    )
    require(
        any(x["begin_wall_ns"] > r["sensor_stopped_wall_ns"] for x in states),
        "state continues during tail",
    )
    prep = audit_preparation(r)
    require(
        r["enabled_wall_ns"] >= r["preparation"]["finished_wall_ns"],
        "camera after preparation",
    )
    return dict(
        status="PASS",
        observed_snapshots=len(states),
        images=len(images),
        calls=len(calls),
        consumed=len(consumed),
        consumed_per100source_frames=segments,
        missing_scheduled_camera_frames=missing,
        extra_boundary_camera_frames=extra,
        state_counters=clock.status()["counters"],
        tick_requests=len(requests),
        overlap=overlap,
        decisions=dict(outcomes=outcomes, late_causes=causes),
        preparation=prep,
        availability=measured,
        silence_reads=len(silence),
        acceptance="finite_observational_integration_not_realtime_or_driving_qualification",
    )

#!/usr/bin/env python3
"""Recheck saved source-build smoke JSON/CSV; no simulator access or mutation."""
import argparse
import csv
import json
import math
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("attempt", type=Path)
    args = parser.parse_args()
    r = json.loads((args.attempt / "result.json").read_text())
    with (args.attempt / "ticks.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    checks = {}
    checks["lifecycle_status"] = r["status"] == "PASS" and all(c["status"] == "PASS" for c in r["cases"])
    checks["exact_source_identity"] = r["client_version"] == r["server_version"] == r["expected_version"]
    checks["map_identity"] = r["map"].rsplit("/", 1)[-1] == r["expected_map"]
    checks["no_remaining_vehicles"] = r["initial_vehicle_ids"] == r["remaining_vehicle_ids"] == []
    checks["settings_restored"] = r["settings_before"] == r["settings_after"]
    checks["10ms_settings"] = r["settings_during"]["synchronous_mode"] and r["settings_during"]["fixed_delta_seconds"] == .01
    checks["explicit_render_scope"] = not r["requested_no_rendering"] or r["settings_during"]["no_rendering_mode"]
    cases = {c["name"]: c for c in r["cases"]}
    names = ("normal_cleanup", "injected_exception_cleanup")
    checks["two_distinct_egos"] = len(cases) == 2 and len({c["actor_id"] for c in cases.values()}) == 2
    checks["expected_exception"] = "expected_exception" in cases["injected_exception_cleanup"]
    summaries = {}
    for name, count in zip(names, (100, 2)):
        data = [row for row in rows if row["case"] == name]
        checks[name + "/count"] = len(data) == count == cases[name]["ticks"]
        frames = [int(row["tick_frame"]) for row in data]
        times = [float(row["elapsed_seconds"]) for row in data]
        differences = [b - a for a, b in zip(times, times[1:])]
        checks[name + "/indices"] = [int(row["index"]) for row in data] == list(range(count))
        checks[name + "/frame_snapshot"] = all(int(row["tick_frame"]) == int(row["snapshot_frame"]) for row in data)
        checks[name + "/frame_continuity"] = all(b == a + 1 for a, b in zip(frames, frames[1:]))
        checks[name + "/simulation_dt"] = all(math.isfinite(d) and abs(d - .01) <= 1e-6 for d in differences)
        checks[name + "/reported_dt"] = all(abs(float(row["delta_seconds"]) - .01) <= 1e-6 for row in data)
        checks[name + "/wall_order"] = all(int(row["received_monotonic_ns"]) >= int(row["request_monotonic_ns"]) for row in data)
        observations = cases[name]["cleanup_observations"]
        checks[name + "/cleanup"] = cases[name]["destroy_return"] and not observations[-1]["registry_present"] and not observations[-1]["snapshot_present"]
        summaries[name] = dict(ticks=len(data), first_frame=frames[0], last_frame=frames[-1],
                               simulation_dt_min_s=min(differences), simulation_dt_max_s=max(differences),
                               wall_tick_max_ms=max((int(row["received_monotonic_ns"]) - int(row["request_monotonic_ns"])) / 1e6 for row in data))
    checks["no_extra_trace_rows"] = len(rows) == 102
    report = dict(status="PASS" if all(checks.values()) else "FAIL", checks=checks, cases=summaries,
                  scope="source server connection, physics-disabled ego lifecycle, 10ms logical ticks",
                  wall_deadline_acceptance="NOT RUN", normal_actuation="NOT RUN")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if all(checks.values()) else 1)


if __name__ == "__main__":
    main()

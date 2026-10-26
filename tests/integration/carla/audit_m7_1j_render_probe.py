#!/usr/bin/env python3
"""Audit saved rendered diagnostic metadata; no CARLA import or RPC.

This checks bounded image reception, not complete 20Hz delivery, rendering
quality, native wall deadlines, reset handling, or normal actuation.
"""
import argparse
import json
import math
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("attempt", type=Path)
    args = parser.parse_args()
    r = json.loads((args.attempt / "result.json").read_text())
    states = {int(k): v for k, v in r["tick_states"].items()}
    frames = sorted(states)
    checks = {
        "probe_completed": r["status"] == "PASS" and "error" not in r and "cleanup_error" not in r,
        "source_identity": r["client_version"] == r["server_version"] == r["expected_version"],
        "rendered_10ms": r["settings_during"]["synchronous_mode"]
            and r["settings_during"]["fixed_delta_seconds"] == .01
            and not r["settings_during"]["no_rendering_mode"],
        "150_continuous_states": len(frames) == 150 and frames == list(range(frames[0], frames[0] + 150)),
        "original_state_dt": all(math.isfinite(states[b] - states[a])
            and abs(states[b] - states[a] - .01) <= 1e-6 for a, b in zip(frames, frames[1:])),
        "no_callback_overflow": all(v == 0 for v in r["overflow"].values()),
        "settings_restored": r["settings_before"] == r["settings_after"],
        "owned_actors_removed": len(r["destroy_returns"]) == 3
            and all(r["destroy_returns"].values()) and r["remaining_owned"] == [],
    }
    streams = {}
    summary = {}
    for name in ("rgb", "gt"):
        rows = r["frames"][name]
        streams[name] = {x["frame"]: x for x in rows}
        checks[name + "/unique_frames"] = len(rows) == len(streams[name])
        checks[name + "/dimensions"] = all(x["bytes"] == 320 * 240 * 4 for x in rows)
        indices = [x["frame"] for x in rows]
        gaps = [b - a for a, b in zip(indices, indices[1:])]
        summary[name] = dict(received=len(rows), first_frame=indices[0], last_frame=indices[-1],
                             frame_gaps=gaps, complete_20hz_delivery="NOT ACCEPTED BY THIS PROBE")
    paired = sorted(streams["rgb"].keys() & streams["gt"].keys() & states.keys())
    checks["paired_original_frames"] = len(paired) >= 10 and paired == r["paired_in_tick_window"]
    checks["original_timestamp_join"] = all(
        math.isfinite(streams[name][f]["timestamp"])
        and abs(streams[name][f]["timestamp"] - states[f]) <= 1e-6
        for name in streams for f in paired)
    checks["rgb_nonblank"] = all(streams["rgb"][f]["color_max"] > streams["rgb"][f]["color_min"] for f in paired)
    checks["gt_has_labels"] = all(len(streams["gt"][f]["label_histogram"]) >= 2
        and sum(streams["gt"][f]["label_histogram"].values()) == 320 * 240 for f in paired)
    report = dict(status="PASS" if all(checks.values()) else "FAIL", checks=checks,
                  paired=len(paired), streams=summary,
                  scope="saved bounded reception/timestamps/lifecycle metadata; not renderer crash closure")
    print(json.dumps(report, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())

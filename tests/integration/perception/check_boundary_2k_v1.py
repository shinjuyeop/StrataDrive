#!/usr/bin/env python3
"""Cross-language original-clock checks and replay of retained2K observations.

No new camera frames, model calls, holdout consumption or latency measurements.
The archived owner remains authoritative for unavailable events. The new C++
receiver independently expires source/receipt/state and validates every result.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.async_native_2k_v1 import NativeDetection, NativeResult
from physical_ai.perception.boundary_2k_v1 import BoundaryObservation, Publication, ReplayCursor, frame_line
from physical_ai.perception.contract import Detection, FrameIdentity, PerceptionResult, LIFETIME_NS
from physical_ai.perception.replay import run_boundary
from physical_ai.perception.tracking import ImageTracker


def typed(row):
    values = dict(row)
    values["identity"] = FrameIdentity(**values["identity"])
    values["detections"] = tuple(NativeDetection(d["class_id"], d["score"], tuple(d["box"])) for d in row["detections"])
    result = NativeResult(**values)
    result.validate()
    return result


def mutations(binary):
    r = NativeResult(FrameIdentity(1, 7, 5, 50_000_000), (NativeDetection(2, .8, (10, 20, 2560, 1536)),))
    p = Publication(r, 8, 1_000_000_000, 1_100_000_000)
    start = "S 1 7 8 0 900000000"
    good = frame_line(p, 60_000_000, 1_010_000_000, 1_005_000_000)
    changes = {
        1: 150_000_000, 2: 1_100_000_000, 3: 900_000_000,
        4: 2, 5: 2, 6: 2, 7: 9, 8: 9, 9: 0,
        10: 60_000_001, 11: 150_000_001, 12: 1_000_000_001, 13: 1_100_000_001,
        14: 2, 15: 2, 16: 3840, 17: 2304, 18: 0, 19: "0" * 64,
        21: 4, 22: .59, 23: 2560, 24: 1536, 25: 2561, 26: 1537,
    }
    for column, value in changes.items():
        fields = good.split();fields[column] = str(value)
        rows = run_boundary(binary, [start, good, " ".join(fields)])
        assert rows[1]["available"] and not rows[2]["accepted"] and not rows[2]["available"], (column, rows)
        assert not rows[2]["tracks"]
    for column, value in ((1, "-1"), (20, "101"), (22, "nan"), (22, "inf"), (19, "z" * 64)):
        fields = good.split();fields[column] = value
        run = subprocess.run([str(binary)], input=start + "\n" + " ".join(fields) + "\n", text=True, capture_output=True, timeout=10)
        assert run.returncode == 2, (column, value, run)
    rows = run_boundary(binary, [start, good, "P 60000000 1099999999 1099999999", "P 60000000 1100000000 1100000000"])
    assert rows[2]["available"] and rows[2]["received_wall_ns"] == p.received_wall_ns
    assert not rows[3]["available"] and rows[3]["reason"] == 6
    rows = run_boundary(binary, [start, good, "U 60000000 1010000000 1005000000", good])
    assert not rows[-1]["available"] and rows[-1]["reason"] == 7
    return dict(semantic_mutations=len(changes), parser_mutations=5, original_wall_expiry=True, no_resurrection=True)


def replay(binary, report_path, output=None):
    original = report_path.read_bytes()
    report = json.loads(original)
    calls = {r["identity"]["frame"]: r for r in report["model_calls"]}
    assert len(calls) == len(report["model_calls"])
    states = [r for r in report["traces"]["state"] if r["disposition"] == "accepted"]
    first = states[0]
    clock = report["clock_instance"]
    # Trusted identity for this archived Host wall domain; no clock subtraction
    # or mapping to a remote host. All actual timestamps remain byte-exact ints.
    wall_clock = 9710
    lines = [f"S 1 {clock} {wall_clock} {first['source_ns']} {first['begin_wall_ns']}"]
    cursor = ReplayCursor()
    observations = []
    preinit = 0
    for row in report["traces"]["consumer"]:
        state = row["state"]
        if not state["initialized"]:
            assert row["perception"] is None
            preinit += 1
            continue
        assert not state["failed"]
        source = row["snapshot_read_source_ns"]
        if source is None:
            assert row["perception"] is None
            source = state["source_ns"]  # Last actual state, still carries its old receipt.
        else:
            assert source == state["source_ns"]
        publication = None
        if row["perception"] is not None:
            result = typed(row["perception"])
            call = calls[result.identity.frame]
            assert row["perception"] == call["result"]
            receipt = call["received_wall_ns"]
            publication = Publication(result, wall_clock, receipt, receipt + LIFETIME_NS)
        observation = BoundaryObservation(publication, source, row["snapshot_read_wall_ns"], state["received_wall_ns"])
        lines.append(cursor.line(observation));observations.append(observation)
    rows = run_boundary(binary, lines)
    assert rows[0]["accepted"]
    tracker = ImageTracker()
    active_ids = {}
    used_ids = set()
    previous = None
    fresh = accepted = polls = resets = 0
    expected_tracks = ()
    for line, obs, actual in zip(lines[1:], observations, rows[1:]):
        p = obs.publication
        assert actual["available"] == (p is not None), (report_path, line[:180], actual)
        if p is None:
            assert not actual["tracks"]
            tracker = ImageTracker();active_ids = {};previous = None;expected_tracks = ();resets += 1
            continue
        fresh += 1
        assert actual["frame"] == p.result.identity.frame
        assert actual["source_ns"] == p.result.identity.source_ns
        assert actual["expires_ns"] == p.result.expires_ns
        assert actual["received_wall_ns"] == p.received_wall_ns
        assert actual["wall_expires_ns"] == p.wall_expires_ns
        if line.startswith("F "):
            assert actual["accepted"]
            accepted += 1
            if previous and (obs.source_ns >= previous.result.expires_ns or obs.wall_ns >= previous.wall_expires_ns):
                tracker = ImageTracker();active_ids = {};resets += 1
            canonical = PerceptionResult(p.result.identity, tuple(Detection(d.class_id, d.score, tuple(v / 4 for v in d.box)) for d in p.result.detections), 0, 0, 0)
            expected_tracks = tracker.update(canonical)
            previous = p
        else:
            polls += 1
            assert not actual["accepted"]
        assert len(actual["tracks"]) == len(expected_tracks)
        for actual_track, expected in zip(actual["tracks"], expected_tracks):
            if expected.track_id not in active_ids:
                assert actual_track["id"] not in used_ids
                active_ids[expected.track_id] = actual_track["id"];used_ids.add(actual_track["id"])
            assert actual_track["id"] == active_ids[expected.track_id]
            assert len(actual_track["history"]) == len(expected.observations)
            for a, e in zip(actual_track["history"], expected.observations):
                assert (a["frame"], a["source_ns"], a["score"], a["class_id"], tuple(a["box"])) == (e.frame, e.source_ns, e.score, expected.class_id, tuple(v * 4 for v in e.box))
    if output:
        output.mkdir(parents=True, exist_ok=True)
        (output / "input.txt").write_text("\n".join(lines) + "\n")
        (output / "output.json").write_text(json.dumps(rows, indent=2) + "\n")
    return dict(report=str(report_path), sha256=hashlib.sha256(original).hexdigest(), consumer_rows=len(report["traces"]["consumer"]),
                preinit_unavailable=preinit, replayed=len(observations), fresh_reads=fresh, accepted_frames=accepted,
                repeated_polls=polls, unavailable_or_expired_resets=resets, original_availability_exact=True, tracking_reference_exact=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    parser.add_argument("--reports", nargs="*", type=Path, default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    summary = dict(status="PASS", mutations=mutations(args.binary), retained_replays=[])
    for p in args.reports:
        summary["retained_replays"].append(replay(args.binary, p, args.output / p.parent.parent.name if args.output else None))
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

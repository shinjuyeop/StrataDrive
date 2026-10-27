#!/usr/bin/env python3
"""Compare same-input saved default/20-subdivision V1 runs; no CARLA import."""
import argparse
import hashlib
import json
from pathlib import Path

from audit_m7_1m_effort import audit
from audit_m7_1k_server_probe import require


def load(path):
    return (json.loads((path/"result.json").read_text()),
            [json.loads(line) for line in (path/"receipts.jsonl").read_text().splitlines()])


def canonical_input(entries):
    return [(e["phase"], e["requested"], e["receipt"]["original_actual"],
             e["receipt"]["logical_begin_ns"], e["receipt"]["logical_end_ns"]) for e in entries]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory", type=Path)
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--previous", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    model_data = a.model.read_bytes()
    model, model_hash = json.loads(model_data), hashlib.sha256(model_data).hexdigest()
    report = dict(status="FAIL", normal_driving_enabled=False, interval_work_valid=False)
    try:
        runs = {name: load(a.directory/name) for name in ("baseline", "substeps20a", "substeps20b")}
        previous, old_entries = load(a.previous)
        reports = {name: audit(r, es, model, model_hash) for name, (r, es) in runs.items()}
        base_result, base_entries = runs["baseline"]
        original_input = canonical_input(base_entries)
        require(canonical_input(old_entries) == original_input, "changed previous/default input")
        for name, (r, es) in runs.items():
            require(canonical_input(es) == original_input, "changed candidate input")
            require(r["settings"] == base_result["settings"] and r["map"] == base_result["map"], "changed world/map")
            require(r["expected_vehicle_substeps"] == (0 if name == "baseline" else 20), "wrong numerical profile")
        require(reports["baseline"]["native_forward_unavailable_frames"] > 0, "default failure not reproduced")
        report["runs"] = reports
        report["same_original_input_stream"] = True
        report["input_sha256"] = hashlib.sha256(json.dumps(original_input, sort_keys=True).encode()).hexdigest()
        fields = ("body_world_position_m", "com_velocity_world_m_s", "body_quaternion_xyzw", "wheels")
        def same_physics(xs, ys):
            # Excludes frame/session/run identities and added numerical telemetry.
            return sum(all(x["receipt"]["physics"][f] == y["receipt"]["physics"][f] for f in fields) for x, y in zip(xs, ys))
        report["previous_default_identical_physics_receipts"] = same_physics(old_entries, base_entries)
        report["candidate_repeat_identical_physics_receipts"] = same_physics(runs["substeps20a"][1], runs["substeps20b"][1])
        report["candidate_no_negative_in_sampled_cases"] = all(reports[name]["raw_negative_wheel_samples"] == 0 for name in ("substeps20a", "substeps20b"))
        report["candidate_normal_acceptance"] = "NOT ACCEPTED; isolated numerical candidate only"
        report["status"] = "PASS_CONTROLLED_COMPARISON_ONLY"
    except Exception as exc:
        report["error"] = str(exc)
    a.output.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report))
    return 0 if report["status"] == "PASS_CONTROLLED_COMPARISON_ONLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())

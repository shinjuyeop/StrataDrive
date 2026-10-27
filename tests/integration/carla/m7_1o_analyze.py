#!/usr/bin/env python3
"""Audit saved M7-1o observations; scope is isolated numerical diagnosis only."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess

from audit_m7_1m_effort import audit, read_receipts
from audit_m7_1k_server_probe import require
from m7_1n_compare import canonical_input


def motion(entries):
    fields = ("body_world_position_m", "com_velocity_world_m_s", "angular_velocity_world_rad_s",
              "body_quaternion_xyzw", "body_forward_velocity_m_s", "sleeping")
    return [([e["receipt"]["physics"][k] for k in fields],
             [w["omega_rad_s"] for w in e["receipt"]["physics"]["wheels"]]) for e in entries]


def response_audit(entries, fixture):
    """Replay physical response acquisition, independently of CARLA and saved values."""
    groups = {}
    for entry in entries:
        r = entry["receipt"]
        groups.setdefault((r["run"], r["session"]), []).append(entry)
    for es in groups.values():
        lines = []
        for e in es:
            target = e["model_target"]
            lines.append(" ".join([e["receipt"]["logical_begin_ns"]] +
                         [str(target[k]) for k in ("torque_nm", "pressure_pa", "angle_left_rad", "kind")]))
        out = subprocess.run([str(fixture)], input="\n".join(lines)+"\n", text=True,
                             capture_output=True, check=True, timeout=10)
        acquired = [json.loads(line) for line in out.stdout.splitlines()]
        require(len(acquired) == len(es), "model acquisition count")
        for e, m in zip(es, acquired):
            require(e["model_measurement"] == m, "model acquisition differs from replay")
            require(m["source_ns"] == e["receipt"]["logical_begin_ns"] and m["model_epoch"] == 7,
                    "model acquisition source")
            # Independent nearest-codec-step comparison; physics is not clamped here.
            for role, field, step in (("drive", "torque_nm", .1), ("brake", "pressure_pa", 1000),
                                      ("steering", "angle_left_rad", .0001)):
                payload = bytes.fromhex(e["receipt"]["original_actual"][role]["payload"])
                raw = int.from_bytes(payload[:2], "little", signed=role != "brake")
                value = m[field]/step
                rounded = math.floor(value+.5) if value >= 0 else math.ceil(value-.5)
                require(raw == rounded, "model acquisition / wire quantization")
    return dict(acquisitions=len(entries), sessions=len(groups), physical_step_ns=1000000,
                energy_or_native_authority=False)


def callbacks(entries):
    count = negatives = 0
    negatives_by_wheel = [0, 0, 0, 0]
    minimum = None
    recurrence_checks = 0
    max_error = 0
    first = None
    for e in entries:
        ph = e["receipt"]["physics"]
        ts = ph.get("tire_callbacks", [])
        count += len(ts)
        for t in ts:
            x = t["omega_before_rad_s"]
            negatives += x < 0
            negatives_by_wheel[t["wheel"]] += x < 0
            minimum = x if minimum is None else min(minimum, x)
        # Complete per-wheel callback sequence at non-braking launch is sufficient
        # to check this interval's recurrence. Missing callbacks are never filled in.
        if e["requested"]["pressure_pa"] != 0:
            continue
        n = ph["vehicle_substeps_low"]
        for w in ph["wheels"]:
            wt = [t for t in ts if t["wheel"] == w["index"]]
            if len(wt) != n:
                continue
            for i, t in enumerate(wt):
                # This fork's public getWheelRotationSpeed returns mCorrectedWheelSpeeds.
                # Under zero drive/brake it may blend rolling speed for rendering.
                # Intermediate callbacks expose internal omega; a driven endpoint
                # is unblended. Do not compare an unpowered public endpoint to raw integration.
                if i+1 == n and w["set_drive_nm"] == 0 and "solver_omega_rad_s" not in w:
                    continue
                after = wt[i+1]["omega_before_rad_s"] if i+1 < n else w.get("solver_omega_rad_s", w["omega_rad_s"])
                h = .01/n/w["inertia_kg_m2"]
                predicted = (t["omega_before_rad_s"]+h*(t["tire_torque_nm"]+w["set_drive_nm"]))/(1+h*w["damping_nm_s"])
                error = abs(predicted-after)
                # Float32 operation allowance, not an omega validity allowance.
                require(error <= 2e-6*max(1, abs(after), abs(predicted)), "NoDrive recurrence")
                recurrence_checks += 1
                max_error = max(max_error, error)
                if first is None and t["omega_before_rad_s"] > 0 and after < 0:
                    first = dict(phase=e["phase"], frame=e["receipt"]["frame"], wheel=w["index"],
                                 ordinal=i, before=t, drive_nm=w["set_drive_nm"], predicted_after=predicted,
                                 actual_after=after, dt_s=.01/n)
    return dict(callbacks=count, negative_callback_samples=negatives, min_callback_omega_rad_s=minimum,
                negative_callbacks_by_wheel=negatives_by_wheel,
                recurrence_checks=recurrence_checks, max_recurrence_error_rad_s=max_error,
                first_positive_to_negative=first, solver_work_coverage=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory", type=Path)
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--response-fixture", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    data = a.model.read_bytes()
    model, sha = json.loads(data), hashlib.sha256(data).hexdigest()
    report = dict(status="FAIL", normal_driving_enabled=False, interval_work_valid=False)
    try:
        loaded = {}
        reports = {}
        for directory in sorted(a.directory.glob("substeps*")):
            result = json.loads((directory/"result.json").read_text())
            entries = read_receipts(directory)
            item = audit(result, entries, model, sha)
            item["callbacks"] = callbacks(entries)
            if result.get("input_profile") == "response-model-fixture":
                item["response_replay"] = response_audit(entries, a.response_fixture)
                damaged = copy.deepcopy(entries)
                damaged[0]["model_measurement"]["source_ns"] = "0"
                try:
                    response_audit(damaged, a.response_fixture)
                except ValueError:
                    item["response_source_corruption_rejected"] = True
                else:
                    raise ValueError("accepted corrupted response acquisition")
            # Recompute all settle summaries from retained raw receipts.
            item["settling"] = {}
            for phase in ("settle_hold", "left_settle", "right_settle"):
                states = [e["receipt"]["physics"] for e in entries if e["phase"] == phase]
                last = states[-1]
                summary = next(v for v in result["phases"] if v["label"] == phase)
                require(summary["count"] == len(states) and summary["first"] == states[0] and summary["last"] == last,
                        "settle summary")
                if result.get("settle_mode") == "sleep":
                    require(last["sleeping"] and last["com_velocity_world_m_s"] == [0, 0, 0] and
                            last["angular_velocity_world_rad_s"] == [0, 0, 0] and
                            all(w["omega_rad_s"] == 0 for w in last["wheels"]), "sleep witness")
                item["settling"][phase] = dict(ticks=len(states), sleeping=last["sleeping"],
                                               velocity_m_s=last["com_velocity_world_m_s"])
            loaded[directory.name] = (result, entries)
            reports[directory.name] = item
        require(len(loaded) >= 8, "incomplete comparison")
        reference = loaded["substeps20-trace"][1]
        # Every fixed step-input numerical profile uses the same CAN/P05 bytes,
        # original timestamps, expiry and complete interval sequence.
        for name, (r, es) in loaded.items():
            if r.get("input_profile", "step-fixture") == "step-fixture" and r.get("settle_mode") == "fixed100":
                require(canonical_input(es) == canonical_input(reference), "changed stress input")
                require(r["settings"] == loaded["substeps20-trace"][0]["settings"], "changed world")
        old = read_receipts(a.directory.parent/"m7_carla_1n/substeps20a")
        require(canonical_input(old) == canonical_input(reference), "changed 1n stress input")
        require(motion(old) == motion(reference), "instrumentation changed 20-substep physics")
        report["instrumented20_matches_1n_all_physics"] = len(reference)
        report["same_original_stress_input"] = True
        damaged = copy.deepcopy(reference)
        next(e for e in damaged if e["phase"] == "launch")["receipt"]["physics"]["tire_callbacks"][0]["tire_torque_nm"] += 100
        try:
            callbacks(damaged)
        except ValueError:
            report["tire_callback_corruption_rejected"] = True
        else:
            raise ValueError("accepted corrupted tire callback")
        deltas = {}
        for low, high in ((160, 320), (320, 640)):
            xs = loaded[f"substeps{low}-fixed"][1]
            ys = loaded[f"substeps{high}-fixed"][1]
            speed = wheel = position = 0
            for x, y in zip(xs, ys):
                u, v = x["receipt"]["physics"], y["receipt"]["physics"]
                speed = max(speed, abs(u["body_forward_velocity_m_s"]-v["body_forward_velocity_m_s"]))
                wheel = max(wheel, *(abs(c["omega_rad_s"]-d["omega_rad_s"]) for c, d in zip(u["wheels"], v["wheels"])))
                position = max(position, math.dist(u["body_world_position_m"], v["body_world_position_m"]))
            deltas[f"{low}_vs_{high}"] = dict(max_forward_m_s=speed, max_wheel_rad_s=wheel, max_position_m=position)
        report["numerical_deltas_not_acceptance_tolerances"] = deltas
        if "substeps320-repeat" in loaded:
            require(canonical_input(loaded["substeps320-repeat"][1]) == canonical_input(loaded["substeps320-fixed"][1]), "repeat input")
            require(motion(loaded["substeps320-repeat"][1]) == motion(loaded["substeps320-fixed"][1]), "repeat motion")
            report["candidate_repeat_identical_physics"] = len(loaded["substeps320-fixed"][1])
        if "substeps320-rawa" in loaded and "substeps320-rawb" in loaded:
            xs, ys = loaded["substeps320-rawa"][1], loaded["substeps320-rawb"][1]
            require(canonical_input(xs) == canonical_input(ys) and motion(xs) == motion(ys), "raw repeat input/motion")
            raw = lambda es: [[w["solver_omega_rad_s"] for w in e["receipt"]["physics"]["wheels"]] for e in es]
            require(raw(xs) == raw(ys), "raw solver repeat")
            require(motion(xs) == motion(loaded["substeps320-fixed"][1]), "readout changed motion")
            report["direct_solver_repeat_identical_physics"] = len(xs)
            report["direct_readout_did_not_change_prior_motion"] = True
        report["runs"] = reports
        report["status"] = "PASS_CAUSE_AND_COMPARISON_AUDIT_ONLY"
    except Exception as exc:
        report["error"] = str(exc)
    a.output.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps({k: v for k, v in report.items() if k != "runs"}))
    return 0 if report["status"] == "PASS_CAUSE_AND_COMPARISON_AUDIT_ONLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())

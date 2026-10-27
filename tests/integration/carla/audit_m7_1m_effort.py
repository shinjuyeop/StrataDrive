#!/usr/bin/env python3
"""Independent SI/float32/CRC/provenance/interval audit of V1 physics receipts.

Does not import CARLA, server mapping code or change raw wheel observations.
Mapping can pass while dynamic/forward-native criteria fail; report both.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import struct

from audit_m7_1k_server_probe import IDS, crc, require


def f32(value):
    return struct.unpack("f", struct.pack("f", value))[0]


def audit(result, entries, model, model_hash):
    require(result["status"] in ("PASS_RECEIPT_RUN", "DYNAMIC_CRITERIA_FAIL"), "runtime incomplete")
    require(not result["normal_driving_enabled"] and not result["interval_work_valid"], "scope")
    require(result["model_sha256"] == model_hash and model["approval"] == "ACCEPTED_VIRTUAL_MODEL_ONLY", "model")
    require(all(c["status"] == "PASS" for c in result["cases"]), "runtime check")
    require(result["original_settings"] == result["restored_settings"] and not result["remaining_vehicle_ids"], "cleanup")
    identities = {(b["run"], b["session"], b["actor"]): b for b in result["bindings"]}
    cursors, tickets = {}, set()
    negative = rear_negative = nonzero = 0
    phase_counts = {}
    for entry in entries:
        r = entry["receipt"]
        key = r["run"], r["session"], r["actor"]
        require(key in identities and r["physics_generation"] == identities[key]["physics"]["generation"], "identity/generation")
        token = key, r["ticket"]
        require(token not in tickets, "ticket reused")
        tickets.add(token)
        require(r["model_sha256"] == model_hash and r["model_id"] == model["id"] and
                r["effort_profile"] == "virtual-ev-v1-diagnostic", "model receipt")
        require(not r["interval_work_valid"] and not r["solver_substep_work_observed"] and
                r["inputs_cleared_after_physics"], "work/clear")
        begin, end, frame = int(r["logical_begin_ns"]), int(r["logical_end_ns"]), int(r["frame"])
        require(end-begin == 10000000 and abs(r["simulation_end_seconds"]-r["simulation_begin_seconds"]-.01) < 1e-6, "interval")
        require(r["clock_domain"] == "m7-zero-probe-logical-frame" and "NOT native authority" in r["source_identity"], "provenance")
        if key in cursors:
            last = cursors[key]
            require(frame == last[0]+1 and begin == last[1] and abs(r["simulation_begin_seconds"]-last[2]) < 1e-9, "cursor gap")
        sources, sequences, actual = [], [], {}
        for role, (can_id, data_id, size) in IDS.items():
            item = r["original_actual"][role]
            b = bytes.fromhex(item["payload"])
            require(int(item["can_id"]) == can_id and item["is_fd"] and int(item["fd_flags"]) == 0 and len(b) == size, "envelope")
            require(int.from_bytes(b[29:31], "little") == crc(b[:29]+b[31:]+data_id.to_bytes(2, "little")), "CRC")
            # Original schema2/valid + local Normal/origin NormalPath; no field restamping.
            protection = role == "brake" and entry["requested"].get("kind") == "brake-protection"
            require(b[2:4] == b"\x02\x01" and b[24:26] == (b"\x03\x02" if protection else b"\x01\x01") and
                    b[26:29] == b"\x00"*3, "Actual metadata")
            require(int.from_bytes(b[8:12], "little") == int(r["session"]), "epoch")
            source, oldest, expiry = int.from_bytes(b[12:20], "little"), int(item["oldest_ns"]), int(item["exclusive_expiry_ns"])
            require(oldest <= source <= begin and end-oldest <= 30000000 and expiry > end, "source/expiry")
            sources.append(source)
            sequences.append(int.from_bytes(b[4:8], "little"))
            require(int.from_bytes(b[20:24], "little") == sequences[-1] and b[31] == sequences[-1] % 256, "causal/P05 counter")
            raw = int.from_bytes(b[:2], "little", signed=role != "brake")
            actual[role] = raw * {"steering": .0001, "brake": 1000, "drive": .1}[role]
        require(sources == [begin]*3 and sequences == [sequences[0]]*3, "source/sequence")
        require(sequences[0] == (cursors[key][3]+1 if key in cursors else 0), "sequence progression")
        cursors[key] = frame, end, r["simulation_end_seconds"], sequences[0]
        req = entry["requested"]
        require(actual == dict(steering=req["angle_left_rad"], brake=req["pressure_pa"], drive=req["torque_nm"]), "original differs from request")
        wheels = r["physics"]["wheels"]
        require(r["physics"]["nodrive"] and len(wheels) == 4, "NoDrive")
        if "expected_vehicle_substeps" in result:
            count = result["expected_vehicle_substeps"]
            require(r["physics"]["numerical_profile"] == ("vehicle20-diagnostic-v1" if count else "asset-default") and
                    r["physics"]["vehicle_substeps_low"] == (20 if count else 3) and
                    r["physics"]["vehicle_substeps_high"] == (20 if count else 1) and
                    r["physics"]["vehicle_substeps_threshold_m_s"] == 5, "numerical profile")
        L = model["wheels"][0]["offset_x_m"] - model["wheels"][2]["offset_x_m"]
        H = (model["wheels"][1]["offset_y_right_m"] - model["wheels"][0]["offset_y_right_m"]) / 2
        t = math.tan(actual["steering"])
        steer = [-math.atan2(L*t, L-H*t), -math.atan2(L*t, L+H*t), 0, 0]
        is_zero = not any(actual.values())
        require(r["applied_zero_effort"] == is_zero and r["physics"]["inputs_zero"] == is_zero, "zero flag")
        nonzero += not is_zero
        for i, w in enumerate(wheels):
            require(w["index"] == i and w["bone"] == model["wheels"][i]["bone"], "wheel order")
            drive = actual["drive"]*model["motor_fractions"][i]
            brake = actual["brake"]*model["aggregate_friction_nm_per_pa"]*model["brake_fractions"][i]
            require(w["set_drive_nm"] == f32(drive*10000)/10000 and w["set_friction_nm"] == f32(brake*10000)/10000, "Nm/UE effort")
            # atan2 implementations may differ by one output float32 ULP; use an operation budget only.
            budget = 2**-22 * max(1, abs(steer[i]))
            require(abs(w["set_steer_right_rad"]-f32(steer[i])) <= budget, "Ackermann sign/SI")
            require(abs(w["set_steer_right_rad"]) <= w["max_steer_rad"] and w["set_friction_nm"] <= w["max_brake_nm"], "limits")
            require(math.isfinite(w["omega_rad_s"]), "wheel finite")
            negative += w["omega_rad_s"] < 0
        rear_negative += any(w["omega_rad_s"] < 0 for w in wheels[2:])
        for field in ("body_world_position_m", "com_velocity_world_m_s", "angular_velocity_world_rad_s", "body_quaternion_xyzw"):
            require(all(math.isfinite(v) for v in r["physics"][field]), "body finite")
        phase_counts[entry["phase"]] = phase_counts.get(entry["phase"], 0)+1
    require(len(entries) == sum(p["count"] for p in result["phases"]), "receipt count")
    require(phase_counts == {p["label"]: p["count"] for p in result["phases"]}, "phase counts")
    phases = {name: [e["receipt"]["physics"] for e in entries if e["phase"] == name] for name in phase_counts}
    launch, regen, brake, hold = (phases[k] for k in ("launch", "negative_motor", "friction_stop", "hold"))
    dynamics = {
        "forward_launch": launch[-1]["body_forward_velocity_m_s"] > launch[0]["body_forward_velocity_m_s"] and launch[-1]["body_forward_velocity_m_s"] > 0,
        "negative_motor_decelerates_forward": regen[0]["body_forward_velocity_m_s"] > 0 and regen[-1]["body_forward_velocity_m_s"] < regen[0]["body_forward_velocity_m_s"],
        "friction_reaches_exact_wheel_zero": any(all(w["omega_rad_s"] == 0 for w in d["wheels"]) for d in brake),
        "hold_exact_wheel_zero": all(all(w["omega_rad_s"] == 0 for w in d["wheels"]) for d in hold),
    }
    for name, angle in (("left", .2), ("right", -.2)):
        dynamics[name+"_yaw_sign"] = sum(d["angular_velocity_world_rad_s"][2]*.01 for d in phases[name+"_turn"])*angle < 0
    require(result["dynamic_checks"] == dynamics, "dynamic summary mismatch")
    return dict(receipts=len(entries), sessions=len(cursors), nonzero_receipts=nonzero,
                raw_negative_wheel_samples=negative, native_forward_unavailable_frames=rear_negative,
                native_forward_gate="FAIL_RAW_NEGATIVE_UNAVAILABLE" if rear_negative else "NO_NEGATIVE_IN_THIS_RUN_ONLY",
                runtime_dynamic_checks=result["dynamic_checks"], normal_driving_enabled=False, interval_work_valid=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory", type=Path)
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    result = json.loads((a.directory/"result.json").read_text())
    entries = [json.loads(line) for line in (a.directory/"receipts.jsonl").read_text().splitlines()]
    data = a.model.read_bytes()
    model, sha = json.loads(data), hashlib.sha256(data).hexdigest()
    report = dict(status="FAIL")
    try:
        report.update(audit(result, entries, model, sha))
        faults = {
            "wrong_model": lambda es: es[0]["receipt"].update(model_sha256="0"*64),
            "wrong_actor": lambda es: es[0]["receipt"].update(actor="999999"),
            "source_CRC": lambda es: es[0]["receipt"]["original_actual"]["drive"].update(payload="01"+es[0]["receipt"]["original_actual"]["drive"]["payload"][2:]),
            "expiry_at_end": lambda es: es[0]["receipt"]["original_actual"]["drive"].update(exclusive_expiry_ns=es[0]["receipt"]["logical_end_ns"]),
            "clear_missing": lambda es: es[0]["receipt"].update(inputs_cleared_after_physics=False),
            "Nm_unit": lambda es: es[0]["receipt"]["physics"]["wheels"][0].update(set_friction_nm=3750000),
            "energy_promoted": lambda es: es[0]["receipt"].update(interval_work_valid=True),
            "wheel_nan": lambda es: es[0]["receipt"]["physics"]["wheels"][2].update(omega_rad_s=float("nan")),
            "steer_sign": lambda es: next(e for e in es if e["phase"] == "left_turn")["receipt"]["physics"]["wheels"][0].update(set_steer_right_rad=.2),
        }
        if "expected_vehicle_substeps" in result:
            faults["numerical_profile"] = lambda es: es[0]["receipt"]["physics"].update(vehicle_substeps_low=19)
        report["corruption_rejections"] = {}
        for name, damage in faults.items():
            corrupted = copy.deepcopy(entries)
            damage(corrupted)
            try:
                audit(result, corrupted, model, sha)
            except ValueError as exc:
                report["corruption_rejections"][name] = str(exc)
            else:
                raise ValueError("accepted corruption: "+name)
        report["status"] = "PASS_MAPPING_AUDIT_ONLY"
    except Exception as exc:
        report["error"] = str(exc)
    a.output.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report))
    return 0 if report["status"] == "PASS_MAPPING_AUDIT_ONLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Independent saved-receipt audit, including original P05 bytes and fault vectors."""
import argparse
import copy
import json
import math
from pathlib import Path

IDS = dict(steering=(0x280, 0x1002, 32), brake=(0x281, 0x1102, 32), drive=(0x282, 0x1202, 64))


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def crc(data):
    value = 0xffff
    for byte in data:
        value ^= byte << 8
        for _ in range(8):
            value = ((value << 1) ^ (0x1021 if value & 0x8000 else 0)) & 0xffff
    return value


def audit(result):
    require(result["status"] == "PASS_LIMITED_ZERO_PROBE", "runtime failed")
    require(not result["normal_driving_enabled"] and not result["interval_work_valid"], "scope promoted")
    require(result["cases"] and all(c["status"] == "PASS" for c in result["cases"]), "case failed")
    require(result["restored_settings"] == result["original_settings"] and not result["remaining_vehicle_ids"], "cleanup")
    require(result["close"]["ok"] and not result["close"]["locked"], "close")
    require(len(result["bindings"]) == 2 and len(result["receipts"]) == 13, "bounded run size")
    reset_checked = "generation" in result["receipts"][0]["physics"]
    if reset_checked:
        require("reset" in result and result["reset"]["ok"] and result["reset"]["latched"] and
                not result["reset"]["staged"] and result["reset"]["physics"]["inputs_zero"], "reset containment")
        require(int(result["reset"]["physics"]["generation"]) >
                int(result["receipts"][-1]["physics"]["generation"]), "reset did not recreate physics")
    if "legacy_denials" in result:
        denied = result["legacy_denials"]["denied_legacy_rpc"]
        require(all(int(denied.get(name, "0")) >= 1 for name in (
            "apply_control_to_vehicle", "set_actor_target_velocity", "set_actor_transform",
            "set_actor_simulate_physics", "apply_batch", "tick_cue", "set_episode_settings",
            "load_new_episode")), "direct writer not rejected at server")
    tickets = set()
    cursor = {}
    negative = 0
    for r in result["receipts"]:
        identity = r["run"], r["session"], r["actor"]
        ticket = (*identity, r["ticket"])
        require(ticket not in tickets, "duplicate receipt")
        tickets.add(ticket)
        begin, end = int(r["logical_begin_ns"]), int(r["logical_end_ns"])
        frame = int(r["frame"])
        require(end-begin == 10000000, "logical interval")
        require(abs(r["simulation_end_seconds"]-r["simulation_begin_seconds"]-.01) < 1e-6, "physics interval")
        require(r["applied_zero_effort"] and not r["interval_work_valid"] and
                not r["solver_substep_work_observed"], "applied/work scope")
        require(r["physics"]["nodrive"] and r["physics"]["inputs_zero"], "NoDrive/clear")
        if identity in cursor:
            last = cursor[identity]
            require(frame == last[0]+1 and begin == last[1], "frame gap or restamped clock")
            require(abs(r["simulation_begin_seconds"]-last[2]) < 1e-9, "simulation gap")
        sources = []
        sequences = []
        for role, (can_id, data_id, size) in IDS.items():
            item = r["original_actual"][role]
            payload = bytes.fromhex(item["payload"])
            require(int(item["can_id"]) == can_id and item["is_fd"] and int(item["fd_flags"]) == 0 and len(payload) == size, "envelope")
            expected = crc(payload[:29]+payload[31:]+data_id.to_bytes(2, "little"))
            require(int.from_bytes(payload[29:31], "little") == expected, "original P05 CRC")
            require(payload[:2] == b"\x00\x00", "nonzero fixture applied")
            source = int.from_bytes(payload[12:20], "little")
            epoch = int.from_bytes(payload[8:12], "little")
            seq = int.from_bytes(payload[4:8], "little")
            oldest = int(item["oldest_ns"])
            expiry = int(item["exclusive_expiry_ns"])
            require(epoch == int(r["session"]), "epoch")
            require(oldest <= source <= begin and end-oldest <= 30000000 and expiry > end, "source coverage")
            sources.append(source)
            sequences.append(seq)
        require(max(sources)-min(sources) <= 10000000 and sources == [begin]*3, "source changed")
        require(sequences == [sequences[0]]*3, "fixture sequences")
        require(sequences[0] == (cursor[identity][3]+1 if identity in cursor else 0), "sequence progression")
        cursor[identity] = frame, end, r["simulation_end_seconds"], sequences[0]
        wheels = r["physics"]["wheels"]
        require(len(wheels) == 4 and [w["index"] for w in wheels] == list(range(4)), "wheel indices")
        for w in wheels:
            require(math.isfinite(w["omega_rad_s"]), "wheel nonfinite")
            require(w["radius_m"] > 0 and w["max_brake_nm"] >= 0 and w["bone"], "geometry readback")
            require(w["set_drive_nm"] == w["set_friction_nm"] == w["set_steer_right_rad"] == 0, "persistent effort")
            negative += w["omega_rad_s"] < 0
    return dict(receipts=len(tickets), sessions=len(cursor), raw_negative_wheel_samples=negative,
                physical_reset_checked=reset_checked,
                interval_work_valid=False, normal_driving_enabled=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("result", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = json.loads(args.result.read_text())
    report = dict(status="FAIL")
    try:
        report.update(audit(result))
        faults = {
            "frame_gap": lambda r: r["receipts"][1].update(frame=str(int(r["receipts"][1]["frame"])+1)),
            "source_byte_changed": lambda r: r["receipts"][0]["original_actual"]["drive"].update(payload="01"+r["receipts"][0]["original_actual"]["drive"]["payload"][2:]),
            "expiry_at_end": lambda r: r["receipts"][0]["original_actual"]["drive"].update(exclusive_expiry_ns=r["receipts"][0]["logical_end_ns"]),
            "energy_promoted": lambda r: r["receipts"][0].update(interval_work_valid=True),
            "wrong_epoch": lambda r: r["receipts"][0].update(session="999"),
            "duplicate": lambda r: r["receipts"].__setitem__(1, r["receipts"][0]),
            "nonfinite_raw_wheel": lambda r: r["receipts"][0]["physics"]["wheels"][0].update(omega_rad_s=float("nan")),
            "persistent_setter": lambda r: r["receipts"][0]["physics"]["wheels"][0].update(set_drive_nm=1),
        }
        report["corruption_rejections"] = {}
        for name, mutate in faults.items():
            damaged = copy.deepcopy(result)
            mutate(damaged)
            try:
                audit(damaged)
            except ValueError as exc:
                report["corruption_rejections"][name] = str(exc)
            else:
                raise ValueError("accepted damaged evidence: "+name)
        report["status"] = "PASS_LIMITED_ZERO_PROBE_AUDIT"
    except Exception as exc:
        report["error"] = str(exc)
    args.output.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report))
    return 0 if report["status"] == "PASS_LIMITED_ZERO_PROBE_AUDIT" else 1


if __name__ == "__main__":
    raise SystemExit(main())

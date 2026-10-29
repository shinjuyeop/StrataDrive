#!/usr/bin/env python3
"""Independent receipt/native-return oracle; no runtime bridge import."""
import argparse
import copy
import gzip
import hashlib
import json
import math
from pathlib import Path

from audit_m7_1m_effort import audit as audit_effort, read_receipts


def require(ok, why):
    if not ok:
        raise AssertionError(why)


def read_bridge(path):
    p = path/"bridge.jsonl"
    raw = p.read_bytes() if p.exists() else gzip.decompress((path/"bridge.jsonl.gz").read_bytes())
    return [json.loads(line) for line in raw.splitlines()]


def audit(result, entries, observations, fault=None):
    require(len(entries) == len(observations) > 0, "observation coverage")
    require(not result["normal_driving_enabled"] and not result["interval_work_valid"], "scope")
    require(all(c["status"] == "PASS" for c in result["cases"]), "runtime cases")
    require(result["original_settings"] == result["restored_settings"] and not result["remaining_vehicle_ids"], "cleanup")
    bindings = {(b["run"], b["session"]): b for b in result["bridge_bindings"]}
    history, cursor = {}, {}
    armed = returned = waits = 0
    max_age = max_error = 0
    negatives = 0
    for i, (entry, o) in enumerate(zip(entries, observations)):
        last_fault = bool(fault) and i == len(entries)-1
        r = entry["receipt"]
        key = r["run"], r["session"]
        b = bindings[key]
        require(o["run"] == r["run"] and o["session"] == r["session"] and
                o["frame"] == r["frame"] and o["phase"] == entry["phase"], "binding/log pairing")
        require(r["actor"] == b["actor"] and r["physics_generation"] == r["physics"]["generation"] == b["physics"]["generation"], "source identity")
        previous = cursor.get(key, (int(b["frame"]), b["simulation_seconds"]))
        require(int(r["frame"]) == previous[0]+1 and abs(r["simulation_begin_seconds"]-previous[1]) < 1e-9, "cursor")
        cursor[key] = int(r["frame"]), r["simulation_end_seconds"]
        if last_fault and fault == "snapshot-loss":
            lost = o["injected_snapshot_loss"]
            require(lost["held_frame"] == int(r["frame"])-1 and
                    lost["held_elapsed_seconds"] == r["simulation_begin_seconds"] and
                    "snapshot_frame" not in o, "missing snapshot not restamped")
        else:
            require(o["snapshot_frame"] == int(r["frame"]) and
                    o["snapshot_elapsed_seconds"] == r["simulation_end_seconds"], "independent snapshot")
            waits += o["snapshot_delivery"]["polls"] > 0
        omega = [w["solver_omega_rad_s"] for w in r["physics"]["wheels"]]
        require(all(w["solver_omega_source"] == "PhysX3.4.mWheelSpeeds.direct.v1" for w in r["physics"]["wheels"]) and
                len(omega) == 4 and all(math.isfinite(x) for x in omega), "direct source")
        rear_negative = omega[2] < 0 or omega[3] < 0
        negatives += rear_negative
        source = math.floor(r["simulation_end_seconds"]*1e9+.5)
        history.setdefault(key, {})[source] = (omega[2]+omega[3])/2
        if last_fault:
            require(rear_negative == (fault == "negative") and o["status"] == "REJECTED_NO_NEXT_TICK" and "native" not in o,
                    "fault must have no barrier")
            continue
        require(not rear_negative and o["status"] == "NATIVE_SENSOR_RETURN_BARRIER", "forward/barrier")
        s, n = o["sample"], o["native"]
        require(s["solver_omega_rad_s"] == omega and s["solver_omega_source"] == "PhysX3.4.mWheelSpeeds.direct.v1" and
                s["source_ns"] == source and s["frame"] == int(r["frame"]), "no solver correction/restamp")
        line = s["line"].split()
        require(len(line) == 15 and line[:5] == ["WHEEL", "1", "42", "7", str(0x4D3746554E435449)] and
                int(line[5]) == int(line[9]) == int(r["frame"]) and float(line[6]) == r["simulation_end_seconds"] and
                abs(float(line[7])-.01) < 1e-6 and line[8] == r["actor"] and int(line[10]) == source and
                list(map(float, line[11:])) == omega, "native input provenance")
        require(n["status"] == "WHEEL_SHADOW_BARRIER" and not n["driving"] and n["now_ns"] == source and
                n["next_frame"] == int(r["frame"])+1 and n["service_mask"] == 255, "next barrier")
        if n["armed_fixture"]:
            armed += 1
            require(n["release_mask"] == n["credit_mask"] == 255 and n["returned_wheel"] and n["sensor_wheel"], "native fixture authority")
        for field in ("sensor_wheel", "returned_wheel"):
            w = n[field]
            if not w:
                continue
            require(w["source_ns"] in history[key] and w["source_ns"] <= source, "native original acquisition")
            error = abs(w["rad_s"]-history[key][w["source_ns"]])
            require(math.isfinite(error) and error <= (0 if field == "sensor_wheel" else .005+1e-12), "CAN value quantization")
            age = source+10000000-w["source_ns"]
            if n["armed_fixture"]:
                require(age <= 30000000, "30ms source age")
            if field == "returned_wheel":
                returned += 1
                max_age, max_error = max(max_age, age), max(max_error, error)
    if fault:
        stop = result["bridge_fail_stop"]
        require(result["status"] == "FAIL" and negatives == int(fault == "negative") and
                stop["native_exit"] == int(fault == "negative") and stop["cached_rejected"], "expected bridge failure")
        require(stop["before"]["frame"] == stop["after"]["frame"] == entries[-1]["receipt"]["frame"] and
                stop["paused"]["latched"] and stop["after"]["latched"] and stop["after"]["physics"]["inputs_zero"], "fail stop containment")
    else:
        require(result["status"] == "PASS_RECEIPT_RUN" and negatives == 0 and armed > 0 and returned > 0, "complete forward run")
        names = {c["name"] for c in result["cases"]}
        require(all("bridge_wall_pause_no_restamp_"+s in names for s in ("2", "3", "4")) and
                all("retired_bridge_rejects_cached_"+s in names for s in ("2", "3", "4")), "pause/reset coverage")
    return dict(receipts=len(entries), native_barriers=len(entries)-int(bool(fault)), armed=armed, returned=returned,
                rear_negative_frames=negatives, snapshot_delivery_wait_frames=waits,
                max_next_interval_end_age_ns=max_age, max_CAN_error_rad_s=max_error)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--model", type=Path, default=Path("tools/carla/m7_nodrive/virtual_ev_v1.json"))
    p.add_argument("--expect-negative", action="store_true")
    p.add_argument("--expect-snapshot-loss", action="store_true")
    a = p.parse_args()
    result = json.loads((a.input/"result.json").read_text())
    entries, observations = read_receipts(a.input), read_bridge(a.input)
    require(not (a.expect_negative and a.expect_snapshot_loss), "one expected fault")
    fault = "negative" if a.expect_negative else "snapshot-loss" if a.expect_snapshot_loss else None
    report = dict(status="PASS_EXPECTED_FAULT_CONTAINMENT" if fault else "PASS_SENSOR_RETURN_ONLY", expected_fault=fault)
    report["sensor_return"] = audit(result, entries, observations, fault)
    if not fault:
        report["effort_receipts"] = audit_effort(result, entries, json.loads(a.model.read_text()), hashlib.sha256(a.model.read_bytes()).hexdigest())
        last = next(i for i, o in enumerate(observations) if o["native"]["armed_fixture"])
        mutations = {
            "source_restamp": lambda o: o[last]["native"]["returned_wheel"].update(source_ns=o[last]["native"]["now_ns"]+1),
            "returned_value": lambda o: o[last]["native"]["returned_wheel"].update(rad_s=90),
            "barrier_frame": lambda o: o[last]["native"].update(next_frame=0),
            "snapshot_frame": lambda o: o[last].update(snapshot_frame=0),
            "solver_value": lambda o: o[last]["sample"]["solver_omega_rad_s"].__setitem__(2, 90),
            "wire_actor": lambda o: o[last]["sample"].update(line=o[last]["sample"]["line"].replace("WHEEL", "COMMAND")),
            "missing_role": lambda o: o[last]["native"].update(service_mask=127),
            "missing_return": lambda o: o[last]["native"].update(returned_wheel=None),
        }
        report["oracle_corruptions_rejected"] = []
        for name, mutate in mutations.items():
            bad = copy.deepcopy(observations)
            mutate(bad)
            try:
                audit(result, entries, bad)
            except AssertionError:
                report["oracle_corruptions_rejected"].append(name)
            else:
                raise AssertionError("oracle accepted "+name)
    a.output.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()

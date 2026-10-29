#!/usr/bin/env python3
"""Replay frozen direct-solver observations and corrupt the sensor boundary.

Executes the real existing native shadow; this is NOT a fresh CARLA run.
"""
import argparse
import copy
import json
from pathlib import Path
from types import SimpleNamespace

from audit_m7_1m_effort import read_receipts
from m7_1p_bridge import NativeBridge, aligned_snapshot


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--native", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    source_result = json.loads((a.source/"result.json").read_text())
    entries = read_receipts(a.source)
    bindings = {b["session"]: b for b in source_result["bindings"]}
    report = dict(status="FAIL", mode="frozen receipt replay, NOT live CARLA", replay=[], corruptions=[])
    try:
        old = SimpleNamespace(frame=9, elapsed_seconds=.09)
        current = SimpleNamespace(frame=10, elapsed_seconds=.1)
        stream = iter([old, old, current])
        actual, delivery = aligned_snapshot(lambda: next(stream), 10)
        assert actual is current and delivery["polls"] == 2 and current.elapsed_seconds == .1
        report["snapshot_delivery"] = dict(delayed_exact_frame=True, missing_rejected=False, skipped_rejected=False)
        for name, sample in (("missing_rejected", old), ("skipped_rejected", SimpleNamespace(frame=11))):
            try:
                aligned_snapshot(lambda: sample, 10, timeout=0)
            except RuntimeError:
                report["snapshot_delivery"][name] = True
            else:
                raise AssertionError(name)
        for session in sorted({e["receipt"]["session"] for e in entries}):
            data = [e["receipt"] for e in entries if e["receipt"]["session"] == session]
            # Frozen replay has no independent world snapshot. Live admission
            # instead anchors this field from world.get_snapshot() at bind.
            bindings[session]["simulation_seconds"] = data[0]["simulation_begin_seconds"]
            bridge = NativeBridge(a.native, bindings[session], a.output/("replay-"+session+".stderr"))
            armed = returned = 0
            max_age = max_error = 0
            try:
                for r in data:
                    observation = bridge.observe(r)
                    reply = observation["native"]
                    armed += bool(reply["armed_fixture"])
                    w = reply["returned_wheel"]
                    if w:
                        returned += 1
                        max_age = max(max_age, reply["now_ns"]+10000000-w["source_ns"])
                        max_error = max(max_error, abs(w["rad_s"]-bridge.history[w["source_ns"]]))
            finally:
                code = bridge.close()
            assert code == 0 and armed > 0 and returned > 0
            report["replay"].append(dict(session=session, count=len(data), armed=armed, returned=returned,
                                         max_next_end_age_ns=max_age, max_CAN_error_rad_s=max_error, exit=code))

        original = entries[0]["receipt"]
        binding = bindings[original["session"]]
        mutations = []

        def field(name, key, value):
            mutations.append((name, lambda r: r.__setitem__(key, value)))

        for key in ("run", "session", "actor", "model_id", "model_sha256", "effort_profile", "physics_generation", "clock_domain", "source_identity"):
            field("wrong_"+key, key, "wrong")
        field("duplicate_frame", "frame", binding["frame"])
        field("skipped_frame", "frame", str(int(original["frame"])+1))
        field("stale_time", "simulation_end_seconds", original["simulation_end_seconds"]-.01)
        field("future_time", "simulation_end_seconds", original["simulation_end_seconds"]+.01)
        field("nan_time", "simulation_end_seconds", float("nan"))
        mutations.append(("shifted_begin_and_end", lambda r: r.update(
            simulation_begin_seconds=r["simulation_begin_seconds"]+1,
            simulation_end_seconds=r["simulation_end_seconds"]+1)))
        field("uncleared_inputs", "inputs_cleared_after_physics", False)
        field("wrong_logical_epoch", "logical_begin_ns", "0")
        mutations += [
            ("missing_solver_value", lambda r: r["physics"]["wheels"][2].pop("solver_omega_rad_s")),
            ("missing_source_id", lambda r: r["physics"]["wheels"][2].pop("solver_omega_source")),
            ("public_getter_source", lambda r: r["physics"]["wheels"][2].update(solver_omega_source="getWheelRotationSpeed")),
            ("wrong_wheel_order", lambda r: r["physics"]["wheels"].reverse()),
            ("missing_wheel", lambda r: r["physics"]["wheels"].pop()),
            ("wrong_nested_generation", lambda r: r["physics"].update(generation="2")),
            ("wrong_numerical_profile", lambda r: r["physics"].update(vehicle_substeps_low=20)),
        ]
        for name, value in (("tiny_rear_negative", -1e-9), ("reverse_rear", -1), ("range_rear", 100.01),
                            ("nan_solver", float("nan")), ("inf_solver", float("inf"))):
            mutations.append((name, lambda r, v=value: r["physics"]["wheels"][2].update(solver_omega_rad_s=v)))
        for name, mutate in mutations:
            bridge = NativeBridge(a.native, binding, a.output/(name+".stderr"))
            bad = copy.deepcopy(original)
            mutate(bad)
            rejected = latched = False
            reason = ""
            try:
                bridge.observe(bad)
            except (RuntimeError, KeyError) as e:
                rejected, reason = True, str(e)
            try:
                bridge.observe(original)
            except RuntimeError:
                latched = True
            code = bridge.close()
            assert rejected and latched and code in (0, 1), name
            report["corruptions"].append(dict(name=name, rejected=rejected, latched=latched, native_exit=code, reason=reason))

        # A duplicate valid receipt is rejected even though all its values match.
        bridge = NativeBridge(a.native, binding, a.output/"duplicate-receipt.stderr")
        bridge.observe(original)
        try:
            bridge.observe(original)
        except RuntimeError:
            assert bridge.failed
        else:
            raise AssertionError("duplicate accepted")
        assert bridge.close() == 0
        report["duplicate_receipt_rejected"] = True
        # Prove the bridge doesn't read the public getter or reinterpret it as solver data.
        bridge = NativeBridge(a.native, binding, a.output/"public-getter-unused.stderr")
        bad_public = copy.deepcopy(original)
        for w in bad_public["physics"]["wheels"]:
            w["omega_rad_s"] = -999
        reply = bridge.observe(bad_public)
        assert reply["sample"]["solver_omega_rad_s"] == [0]*4
        assert bridge.close() == 0
        report["public_getter_unused"] = True
        report["status"] = "PASS_REPLAY_AND_REJECTION"
    finally:
        (a.output/"result.json").write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()

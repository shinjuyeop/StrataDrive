#!/usr/bin/env python3
"""Isolated V1 synthetic Actual diagnostic. Never connects native driving/energy.

Keep raw negatives, failures and all receipts. An advance timeout is never retried.
Dynamic observations are separate from receipt/mapping checks and acceptance.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import time
import traceback

import carla
from m7_1k_server_probe import FIELDS


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--fixture", type=Path, required=True)
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--port", type=int, default=2200)
    args = p.parse_args()
    args.output.mkdir(exist_ok=False, parents=True)
    model_hash = hashlib.sha256(args.model.read_bytes()).hexdigest()
    result = dict(status="FAIL", started_utc=datetime.now(timezone.utc).isoformat(),
                  mode="isolated synthetic CAN/P05 V1 diagnostic; NOT native driving",
                  normal_driving_enabled=False, interval_work_valid=False,
                  model_sha256=model_hash, cases=[], bindings=[], phases=[])
    events = []
    client = carla.Client("127.0.0.1", args.port)
    client.set_timeout(10)
    key = os.environ["STRATADRIVE_M7_OWNER_KEY"]
    session, run = "0", ""
    world = original = actor = None
    bound = False
    begin = frame = seq = 0
    receipts = (args.output/"receipts.jsonl").open("w")

    def case(name, ok, **details):
        result["cases"].append(dict(name=name, status="PASS" if ok else "FAIL", **details))
        if not ok:
            raise AssertionError(name)

    def rpc(op, record=True, auth=True, **kw):
        req = dict(op=op, **kw)
        if op not in ("describe", "bind"):
            req.setdefault("session", session)
            req.setdefault("run", run)
        if auth:
            req["owner_key"] = key
        out = json.loads(client.m7_nodrive(json.dumps(req)))
        if record:
            events.append(dict(request={k: v for k, v in req.items() if k != "owner_key"}, response=out))
        return out

    def fixture(torque=0, pressure=0, angle=0, kind="actual"):
        return json.loads(subprocess.check_output([str(args.fixture.resolve()), session, str(seq), str(begin),
                         str(torque), str(pressure), str(angle), kind], text=True))

    def bind(label):
        nonlocal actor, bound, session, run, begin, frame, seq
        bp = world.get_blueprint_library().find("vehicle.lincoln.mkz_2020")
        bp.set_attribute("role_name", "m7_virtual_v1_diagnostic")
        pose = world.get_map().get_spawn_points()[0]
        actor = world.spawn_actor(bp, pose)
        bad = rpc("bind", actor=str(actor.id), model_sha256="0"*64)
        case("model_identity_required_"+label, not bad["ok"] and bad["reason"] == "model_identity")
        out = rpc("bind", actor=str(actor.id), model_sha256=model_hash)
        bound = out["locked"]
        session, run = out["session"], out["run"]
        case("bound_v1_"+label, out["ok"] and out["effort_profile"] == "virtual-ev-v1-diagnostic" and
             out["model_sha256"] == model_hash and out["physics"]["inputs_zero"])
        result["bindings"].append(out)
        begin, frame, seq = int(out["logical_begin_ns"]), int(out["frame"]), 0

    def close():
        nonlocal bound, actor
        out = rpc("close")
        case("close_"+session, out["ok"] and not out["locked"] and not out["registry_actor_present"])
        bound, actor = False, None

    def rejected(name, expected, **kw):
        before = rpc("describe", auth=False)["frame"]
        out = rpc("stage", frame=str(frame+1), **kw)
        after = rpc("describe", auth=False)["frame"]
        case(name, not out["ok"] and out["reason"] == expected and before == after)

    def tick(label, torque=0, pressure=0, angle=0, kind="actual"):
        nonlocal begin, frame, seq
        original_actual = fixture(torque, pressure, angle, kind)
        staged = rpc("stage", record=False, frame=str(frame+1), **original_actual)
        if not staged["ok"] or int(staged["frame"]) != frame:
            raise RuntimeError("stage: "+json.dumps(staged))
        ticket = staged["ticket"]
        queued = rpc("advance", record=False, ticket=ticket)
        if not queued["ok"] or queued["reason"] != "queued_not_receipt":
            raise RuntimeError("advance: "+json.dumps(queued))
        deadline = time.monotonic()+10
        receipt = None
        while time.monotonic() < deadline:
            q = rpc("receipt", record=False)
            if q["latched"]:
                raise RuntimeError("latched: "+json.dumps(q))
            if q.get("receipt", {}).get("ticket") == ticket:
                receipt = q["receipt"]
                break
            time.sleep(.005)
        if receipt is None:
            raise RuntimeError("ambiguous tick: query only; advance NOT retried")
        entry = dict(phase=label, requested=dict(torque_nm=torque, pressure_pa=pressure, angle_left_rad=angle, kind=kind),
                     receipt=receipt)
        receipts.write(json.dumps(entry, separators=(",", ":"))+"\n")
        receipts.flush()
        if (receipt["original_actual"] != original_actual or int(receipt["frame"]) != frame+1 or
                not receipt["inputs_cleared_after_physics"] or receipt["interval_work_valid"]):
            raise RuntimeError("receipt mismatch")
        if seq == 0 or label == "release" and seq % 10 == 0:
            cleared = rpc("describe", auth=False, record=False)
            case("persistent_setters_clear_"+str(frame), cleared["physics"]["inputs_zero"])
            replay = rpc("advance", ticket=ticket)
            case("ticket_single_use_"+str(frame), not replay["ok"] and int(replay["frame"]) == frame+1)
        begin, frame, seq = begin+10000000, frame+1, seq+1
        return receipt["physics"]

    def phase(label, count, torque=0, pressure=0, angle=0, kind="actual"):
        data = [tick(label, torque, pressure, angle, kind) for _ in range(count)]
        negative = sum(w["omega_rad_s"] < 0 for d in data for w in d["wheels"])
        rear_invalid = sum(any(w["omega_rad_s"] < 0 for w in d["wheels"][2:]) for d in data)
        summary = dict(label=label, count=count, first=data[0], last=data[-1],
                       raw_negative_samples=negative, native_forward_unavailable_frames=rear_invalid,
                       all_wheels_exact_zero_frames=sum(all(w["omega_rad_s"] == 0 for w in d["wheels"]) for d in data),
                       rear_negative_policy="unavailable to native input; diagnostic observations only; no native loop connected")
        result["phases"].append(summary)
        print(json.dumps({k: summary[k] for k in ("label", "count", "raw_negative_samples", "native_forward_unavailable_frames")}), flush=True)
        return data

    try:
        result["client_version"] = client.get_client_version()
        result["server_version"] = client.get_server_version()
        case("version", result["client_version"] == result["server_version"] == "294096e-dirty")
        world = client.get_world()
        result["map"] = world.get_map().name
        case("dedicated_map", result["map"].endswith("/Town03_Opt") and not list(world.get_actors().filter("vehicle.*")))
        original = world.get_settings()
        result["original_settings"] = {k: getattr(original, k) for k in FIELDS}
        s = world.get_settings()
        s.synchronous_mode, s.fixed_delta_seconds, s.no_rendering_mode = True, .01, True
        s.substepping, s.max_substep_delta_time, s.max_substeps = True, .01, 10
        world.apply_settings(s)
        world.tick()
        result["settings"] = {k: getattr(world.get_settings(), k) for k in FIELDS}
        bind("straight")
        rejected("command_not_actual", "envelope_or_coverage", **fixture(kind="command"))
        rejected("pressure_range_not_clamped", "actual_receiver", **fixture(pressure=1501000))
        rejected("drive_range_not_clamped", "actual_receiver", **fixture(torque=301))
        rejected("steer_range_not_clamped", "actual_receiver", **fixture(angle=.301))
        bad = fixture()
        bad["drive"]["payload"] = "01"+bad["drive"]["payload"][2:]
        rejected("CRC", "actual_receiver", **bad)
        bad = fixture()
        bad["drive"]["exclusive_expiry_ns"] = str(begin+10000000)
        rejected("expiry_at_end", "envelope_or_coverage", **bad)
        # A separate client attempts a direct writer route while a nonzero stage is pending.
        observer = carla.Client("127.0.0.1", args.port)
        observer.set_timeout(2)
        foreign = observer.get_world().get_actor(actor.id)
        staged = rpc("stage", frame=str(frame+1), **fixture(pressure=200000))
        case("nonzero_stage_no_apply", staged["ok"] and rpc("describe", auth=False)["physics"]["inputs_zero"])
        foreign.apply_control(carla.VehicleControl(throttle=1))
        time.sleep(.05)
        denied = rpc("describe", auth=False)
        case("foreign_writer_denied", int(denied["denied_legacy_rpc"].get("apply_control_to_vehicle", "0")) > 0)
        paused = rpc("pause")
        case("pending_nonzero_pause_discards", paused["latched"] and not paused["staged"] and
             rpc("describe", auth=False)["physics"]["inputs_zero"])
        case("pause_cannot_rearm", not rpc("advance", ticket=staged["ticket"])["ok"])
        close()
        bind("straight_after_pause")
        phase("settle_hold", 100, pressure=1500000, kind="brake-protection")
        phase("capacity_200kPa", 1, pressure=200000)
        launch = phase("launch", 300, torque=300)
        regen = phase("negative_motor", 100, torque=-200)
        brake = phase("friction_stop", 200, pressure=1500000, kind="brake-protection")
        hold = phase("hold", 100, pressure=1500000, kind="brake-protection")
        phase("release", 20)
        # Report physical criteria separately; a failure remains a failure without discarding observations.
        result["dynamic_checks"] = {
            "forward_launch": launch[-1]["body_forward_velocity_m_s"] > launch[0]["body_forward_velocity_m_s"] and launch[-1]["body_forward_velocity_m_s"] > 0,
            "negative_motor_decelerates_forward": regen[0]["body_forward_velocity_m_s"] > 0 and regen[-1]["body_forward_velocity_m_s"] < regen[0]["body_forward_velocity_m_s"],
            "friction_reaches_exact_wheel_zero": any(all(w["omega_rad_s"] == 0 for w in d["wheels"]) for d in brake),
            "hold_exact_wheel_zero": all(all(w["omega_rad_s"] == 0 for w in d["wheels"]) for d in hold),
        }
        close()
        for label, angle in (("left", .2), ("right", -.2)):
            bind(label)
            phase(label+"_settle", 100, pressure=1500000, kind="brake-protection")
            turn = phase(label+"_turn", 300, torque=300, angle=angle)
            yaw_integral = sum(d["angular_velocity_world_rad_s"][2]*.01 for d in turn)
            result["dynamic_checks"][label+"_yaw_sign"] = yaw_integral*angle < 0
            result.setdefault("yaw_integrals_ue_rad", {})[label] = yaw_integral
            # A staged effort must not survive a physical state recreation.
            staged = rpc("stage", frame=str(frame+1), **fixture(torque=300, pressure=200000, angle=angle))
            generation = int(turn[-1]["generation"])
            reset = rpc("reset")
            case("nonzero_reset_"+label, staged["ok"] and reset["latched"] and
                 reset["physics"]["inputs_zero"] and int(reset["physics"]["generation"]) > generation)
            case("reset_ticket_rejected_"+label, not rpc("advance", ticket=staged["ticket"])["ok"])
            close()
        result["status"] = "PASS_RECEIPT_RUN" if all(result["dynamic_checks"].values()) else "DYNAMIC_CRITERIA_FAIL"
    except Exception:
        result["error"] = traceback.format_exc()
    finally:
        receipts.close()
        try:
            if bound:
                result["close"] = rpc("close")
                bound = result["close"]["locked"]
                if not bound:
                    actor = None
            if actor is not None and not bound:
                actor.destroy()
            if world is not None and original is not None and not bound:
                world.apply_settings(original)
                result["restored_settings"] = {k: getattr(world.get_settings(), k) for k in FIELDS}
                result["remaining_vehicle_ids"] = [a.id for a in world.get_actors().filter("vehicle.*")]
                if result["original_settings"] != result["restored_settings"] or result["remaining_vehicle_ids"]:
                    raise RuntimeError("cleanup mismatch")
        except Exception:
            result["cleanup_error"] = traceback.format_exc()
            result["status"] = "FAIL"
        (args.output/"events.json").write_text(json.dumps(events, indent=2)+"\n")
        (args.output/"result.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps({"status": result["status"], "cases": len(result["cases"]), "output": str(args.output)}))
    return 0 if result["status"] == "PASS_RECEIPT_RUN" else 1


if __name__ == "__main__":
    raise SystemExit(main())

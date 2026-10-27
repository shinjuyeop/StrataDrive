#!/usr/bin/env python3
"""Real CARLA/UE NoDrive zero-effort diagnostic; no normal-driving authority.

Requires the experimental server opt-in and a separate owner-key environment.
RPC timeout never retries advance. Original requests exclude owner secrets on disk.
"""
import argparse
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time
import traceback

import carla

FIELDS = ("synchronous_mode", "fixed_delta_seconds", "no_rendering_mode",
          "substepping", "max_substep_delta_time", "max_substeps")
ROLES = ("steering", "brake", "drive")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--fixture", required=True, type=Path)
    p.add_argument("--port", type=int, default=2200)
    p.add_argument("--expected-version", required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    key = os.environ["STRATADRIVE_M7_OWNER_KEY"]
    result = dict(status="FAIL", started_utc=datetime.now(timezone.utc).isoformat(),
                  mode="zero-effort synthetic CAN/P05; real UE NoDrive; NOT native eight-role driving",
                  normal_driving_enabled=False, interval_work_valid=False, cases=[], receipts=[])
    events = []
    client = world = original = actor = observer_world = observer = None
    bound = False
    session = "0"
    run = ""

    def rpc(op, auth=True, **kw):
        req = dict(op=op, **kw)
        if op not in ("describe", "bind"):
            req.setdefault("session", session)
            req.setdefault("run", run)
        if auth:
            req["owner_key"] = key
        # Never write owner_key, request bytes containing it, or server environment.
        public = {k: v for k, v in req.items() if k != "owner_key"}
        start = time.monotonic()
        response = json.loads(client.m7_nodrive(json.dumps(req, separators=(",", ":"))))
        events.append(dict(request=public, response=response, wall_seconds=time.monotonic()-start))
        return response

    def case(name, condition, **details):
        result["cases"].append(dict(name=name, status="PASS" if condition else "FAIL", **details))
        if not condition:
            raise AssertionError(name)

    def fixed_frame():
        return int(rpc("describe", auth=False)["frame"])

    def rejected(name, expected, **request):
        before = fixed_frame()
        reply = rpc("stage", **request)
        after = fixed_frame()
        case(name, not reply["ok"] and reply["reason"] == expected and before == after,
             response=reply, frame_before=before, frame_after=after)

    def fixture(seq, source, torque=0, pressure=0, angle=0, kind="actual", epoch=None):
        return json.loads(subprocess.check_output([
            str(args.fixture.resolve()), str(epoch or session), str(seq), str(source),
            str(torque), str(pressure), str(angle), kind], text=True))

    def bind():
        nonlocal actor, bound, session, run
        bp = world.get_blueprint_library().find("vehicle.lincoln.mkz_2020")
        bp.set_attribute("role_name", "m7_nodrive_zero_probe")
        # Existing prepared Town03 asset; isolated spawn, no TM or autopilot API.
        actor = world.spawn_actor(bp, world.get_map().get_spawn_points()[0])
        reply = rpc("bind", actor=str(actor.id))
        bound = reply.get("locked", False)
        session = reply["session"]
        run = reply["run"]
        case("bind_real_nodrive", reply["ok"] and reply["physics"]["nodrive"] and
             reply["physics"]["inputs_zero"] and len(reply["physics"]["wheels"]) == 4,
             response=reply)
        result.setdefault("bindings", []).append(reply)
        return int(reply["logical_begin_ns"]), int(reply["frame"])

    def accepted_tick(seq, begin, frame):
        original_actual = fixture(seq, begin)
        staged = rpc("stage", frame=str(frame+1), **original_actual)
        case("stage_ack_before_physics", staged["ok"] and
             staged["reason"] == "staged_not_applied" and int(staged["frame"]) == frame,
             sequence=seq)
        ticket = staged["ticket"]
        duplicate = rpc("stage", frame=str(frame+1), **original_actual)
        case("pending_stage_rejected", not duplicate["ok"] and duplicate["reason"] == "pending")
        wrong = rpc("advance", ticket=str(int(ticket)+1))
        case("wrong_ticket_does_not_tick", not wrong["ok"] and fixed_frame() == frame)
        queued = rpc("advance", ticket=ticket)
        case("advance_is_not_receipt", queued["ok"] and queued["reason"] == "queued_not_receipt")
        # Query only after send: never retry the non-rollbackable advance operation.
        deadline = time.monotonic()+10
        receipt = None
        while time.monotonic() < deadline:
            query = rpc("receipt")
            candidate = query.get("receipt")
            if candidate and candidate["ticket"] == ticket:
                receipt = candidate
                break
            time.sleep(.01)
        case("postphysics_receipt", receipt is not None and int(receipt["frame"]) == frame+1)
        result["receipts"].append(receipt)
        case("receipt_preserves_original_actual", receipt["original_actual"] == original_actual)
        case("receipt_interval_and_no_energy_claim",
             int(receipt["logical_begin_ns"]) == begin and int(receipt["logical_end_ns"]) == begin+10000000 and
             abs(receipt["simulation_end_seconds"]-receipt["simulation_begin_seconds"]-.01) < 1e-6 and
             receipt["physics"]["nodrive"] and receipt["physics"]["inputs_zero"] and
             not receipt["interval_work_valid"] and not receipt["solver_substep_work_observed"])
        twice = rpc("receipt")
        case("receipt_query_idempotent", twice["receipt"] == receipt)
        duplicate_tick = rpc("advance", ticket=ticket)
        case("consumed_ticket_cannot_tick", not duplicate_tick["ok"] and fixed_frame() == frame+1)
        return begin+10000000, frame+1

    try:
        client = carla.Client("127.0.0.1", args.port)
        client.set_timeout(10)
        result["client_version"] = client.get_client_version()
        result["server_version"] = client.get_server_version()
        case("version", result["client_version"] == result["server_version"] == args.expected_version)
        world = client.get_world()
        observer = carla.Client("127.0.0.1", args.port)
        observer.set_timeout(10)
        observer_world = observer.get_world()
        result["map"] = world.get_map().name
        case("dedicated_prepared_map", result["map"].endswith("/Town03_Opt") and
             not list(world.get_actors().filter("vehicle.*")))
        original = world.get_settings()
        result["original_settings"] = {name: getattr(original, name) for name in FIELDS}
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .01
        settings.no_rendering_mode = True
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        world.tick()
        case("no_owner_cannot_bind", rpc("bind", auth=False, actor="0")["reason"] == "owner")
        malformed = json.loads(client.m7_nodrive("{"))
        case("malformed_request_rejected", not malformed["ok"] and malformed["reason"] == "malformed")
        begin, frame = bind()
        case("second_bind_rejected", rpc("bind", actor=str(actor.id))["reason"] == "already_bound")
        actual = fixture(0, begin)
        rejected("missing_bundle", "envelope_or_coverage", frame=str(frame+1))
        rejected("frame_mismatch", "frame", frame=str(frame+2), **actual)
        wrong_owner = rpc("stage", auth=False, frame=str(frame+1), **actual)
        case("unauthenticated_stage_rejected", not wrong_owner["ok"] and wrong_owner["reason"] == "owner")
        wrong_session = rpc("stage", session=str(int(session)+1), frame=str(frame+1), **actual)
        case("wrong_session_rejected", not wrong_session["ok"] and wrong_session["reason"] == "session")
        wrong_run = rpc("stage", run="previous-process-run", frame=str(frame+1), **actual)
        case("wrong_run_rejected", not wrong_run["ok"] and wrong_run["reason"] == "session" and fixed_frame() == frame)
        rejected("command_is_not_actual", "envelope_or_coverage", frame=str(frame+1),
                 **fixture(0, begin, kind="command"))
        bad = copy.deepcopy(actual)
        bad["drive"]["payload"] = ("01" if bad["drive"]["payload"][:2] != "01" else "00") + bad["drive"]["payload"][2:]
        rejected("p05_crc_rejected", "actual_receiver", frame=str(frame+1), **bad)
        rejected("old_application_epoch_rejected", "actual_receiver", frame=str(frame+1),
                 **fixture(0, begin, epoch=int(session)+1))
        rejected("future_actual_rejected", "envelope_or_coverage", frame=str(frame+1), **fixture(0, begin+1))
        bad = fixture(0, begin+1)
        for role in ROLES:
            bad[role]["oldest_ns"] = str(begin)
        rejected("future_wire_source_rejected", "actual_receiver", frame=str(frame+1), **bad)
        bad = copy.deepcopy(actual)
        bad["drive"]["oldest_ns"] = str(begin-30000000)
        rejected("whole_interval_age_not_relaxed", "envelope_or_coverage", frame=str(frame+1), **bad)
        bad = copy.deepcopy(actual)
        bad["drive"]["exclusive_expiry_ns"] = str(begin+10000000)
        rejected("exclusive_expiry_at_end_rejected", "envelope_or_coverage", frame=str(frame+1), **bad)
        for name, values in (("torque", dict(torque=1)), ("pressure", dict(pressure=1000)), ("angle", dict(angle=.001))):
            rejected("uncalibrated_"+name, "calibration_unavailable_zero_only", frame=str(frame+1),
                     **fixture(0, begin, **values))
        for name, operation in (
            ("ordinary_tick", lambda: world.tick()),
            ("settings_write", lambda: world.apply_settings(settings)),
            ("reload", lambda: client.reload_world(False)),
        ):
            caught = None
            try:
                operation()
            except RuntimeError as exc:
                caught = str(exc)
            case(name+"_server_blocked", caught is not None and "M7 exclusive zero-probe owner" in caught and
                 fixed_frame() == frame, error=caught)
        blocked = observer.apply_batch_sync([carla.command.ApplyVehicleControl(actor.id, carla.VehicleControl(throttle=1))], False)
        case("foreign_batch_writer_blocked", len(blocked) == 1 and blocked[0].has_error() and
             "M7 exclusive zero-probe owner" in blocked[0].error and fixed_frame() == frame)
        caught = None
        try:
            observer.apply_batch_sync([carla.command.ApplyVehicleControl(actor.id, carla.VehicleControl(throttle=1))], True)
        except RuntimeError as exc:
            caught = str(exc)
        case("foreign_batch_followup_tick_blocked", caught is not None and
             "M7 exclusive zero-probe owner" in caught and fixed_frame() == frame, error=caught)
        foreign_actor = observer_world.get_actor(actor.id)
        foreign_actor.apply_control(carla.VehicleControl(throttle=1))
        foreign_actor.set_target_velocity(carla.Vector3D(100, 0, 0))
        foreign_actor.set_transform(carla.Transform())
        caught = None
        try:
            foreign_actor.set_simulate_physics(False)
        except RuntimeError as exc:
            caught = str(exc)
        case("foreign_direct_physics_rpc_blocked", caught is not None and
             "M7 exclusive zero-probe owner" in caught, error=caught)
        expected = ("apply_control_to_vehicle", "set_actor_target_velocity",
                    "set_actor_transform", "set_actor_simulate_physics")
        deadline = time.monotonic()+5
        observed = None
        while time.monotonic() < deadline:
            observed = rpc("describe", auth=False)
            denied = observed.get("denied_legacy_rpc", {})
            if all(int(denied.get(name, "0")) >= 1 for name in expected):
                break
            time.sleep(.01)
        result["legacy_denials"] = observed
        case("foreign_direct_writers_server_rejected", all(int(denied.get(name, "0")) >= 1 for name in expected) and
             int(observed["frame"]) == frame and observed["physics"]["nodrive"] and observed["physics"]["inputs_zero"])
        for seq in range(12):
            begin, frame = accepted_tick(seq, begin, frame)
        # A replay has correct CAN identity and CRC but stale source/sequence/counter.
        rejected("accepted_actual_replay_rejected", "actual_receiver", frame=str(frame+1), **fixture(11, begin-10000000))
        pending = rpc("stage", frame=str(frame+1), **fixture(12, begin))
        case("pause_has_pending_stage", pending["ok"])
        paused = rpc("pause")
        case("pause_invalidates_stage", paused["ok"] and paused["latched"] and not paused["staged"])
        refused = rpc("advance", ticket=pending["ticket"])
        case("paused_tick_requires_new_init", not refused["ok"] and fixed_frame() == frame)
        old_session = session
        closed = rpc("close")
        bound = False
        # ActorCache keeps old descriptions; use the server registry readback.
        case("close_destroys_bound_ego", closed["ok"] and not closed["locked"] and not closed["registry_actor_present"])
        actor = None
        begin, frame = bind()
        case("new_init_advances_session", int(session) > int(old_session))
        old = rpc("advance", session=old_session, ticket=pending["ticket"])
        case("old_session_ticket_cannot_rearm", not old["ok"] and old["reason"] == "session")
        begin, frame = accepted_tick(0, begin, frame)
        pending = rpc("stage", frame=str(frame+1), **fixture(1, begin))
        case("reset_has_pending_stage", pending["ok"])
        prior_generation = int(result["receipts"][-1]["physics"]["generation"])
        reset = rpc("reset")
        result["reset"] = reset
        case("physical_reset_invalidates_pending", reset["ok"] and reset["latched"] and
             not reset["staged"] and int(reset["physics"]["generation"]) > prior_generation and
             reset["physics"]["inputs_zero"] and fixed_frame() == frame)
        refused = rpc("advance", ticket=pending["ticket"])
        case("reset_never_rearms_automatically", not refused["ok"] and fixed_frame() == frame)
        result["status"] = "PASS_LIMITED_ZERO_PROBE"
    except Exception:
        result["error"] = traceback.format_exc()
    finally:
        try:
            if bound:
                result["close"] = rpc("close")
                bound = not result["close"]["ok"]
                if not bound:
                    actor = None
            if actor is not None and not bound:
                actor.destroy()
            if world is not None and original is not None and not bound:
                world.apply_settings(original)
                result["restored_settings"] = {name: getattr(world.get_settings(), name) for name in FIELDS}
                result["remaining_vehicle_ids"] = [a.id for a in world.get_actors().filter("vehicle.*")]
                if result["restored_settings"] != result["original_settings"] or result["remaining_vehicle_ids"]:
                    raise RuntimeError("cleanup mismatch")
        except Exception:
            result["cleanup_error"] = traceback.format_exc()
            result["status"] = "FAIL"
        (args.output/"rpc-events.json").write_text(json.dumps(events, indent=2)+"\n")
        (args.output/"result.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps({"status": result["status"], "cases": len(result["cases"]),
                      "receipts": len(result["receipts"]), "output": str(args.output)}))
    return 0 if result["status"] == "PASS_LIMITED_ZERO_PROBE" else 1


if __name__ == "__main__":
    raise SystemExit(main())

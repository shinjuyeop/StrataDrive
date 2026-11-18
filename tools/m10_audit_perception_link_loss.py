"""Join the observed perception socket close to native braking, motion and settlement."""

import argparse
import json
from pathlib import Path

from m10_compare_visual_scene import read, sha


def audit(directory):
    run = read(directory / "result.json")
    source = directory / "owner/inspect"
    verdict = read(source / "result.json")
    path = source / "trace.jsonl"
    with path.open() as stream:
        rows = [json.loads(line) for line in stream]
    if (
        run["status"] != "PASS_NATIVE_PERCEPTION_LINK_LOSS"
        or verdict["fault"] != "perception-disconnect"
        or any(item["status"] != "PASS" for item in verdict["cases"])
        or len(rows) != 401
    ):
        raise ValueError("incomplete functional disconnect run")
    for current, following in zip(rows, rows[1:]):
        receipt = current["receipt"]
        settlement = following["settlement_ack"]
        if (
            int(receipt["frame"]) != current["frame"] + 1
            or int(receipt["frame"]) != following["frame"]
            or not receipt["interval_work_valid"]
            or not settlement["ok"]
            or settlement["reason"] != "ev_settlement_accepted"
            or settlement["awaiting_ev_settlement"]
            or (receipt["frame"], receipt["ticket"])
            != (settlement["frame"], settlement["ticket"])
        ):
            raise ValueError("original receipt or work settlement mismatch")
    (connected, lost) = [row for row in rows if "perception_link" in row]
    event = verdict["perception_link_loss"]
    if (
        connected["perception_link"]["disconnected"]
        or not lost["perception_link"]["disconnected"]
        or event["frame"] != lost["frame"]
        or event["detected_wall_ns"] != lost["perception_link"]["detected_wall_ns"]
        or not event["closed_wall_ns"]
        <= event["detected_wall_ns"]
        <= lost["wall_advance_begin_ns"]
        or not lost["native"]["admission"]["normal"]
    ):
        raise ValueError("disconnect did not occur at a completed normal barrier")
    after = rows[rows.index(lost) + 1 : -1]
    brake = after[0]
    if any(
        row["native"]["admission"]["normal"]
        or not row["native"]["admission"]["protection"]
        for row in after
    ):
        raise ValueError("normal authority after native transport loss")

    torque = [row["native"]["admission"]["torque_nm"] for row in [lost, *after]]
    if torque[-1] != 0 or any(
        new > old or new < 0 for old, new in zip(torque, torque[1:])
    ):
        raise ValueError("actuator torque failed to run down during native protection")
    zero_torque = next(
        row for row in after if row["native"]["admission"]["torque_nm"] == 0
    )

    def stopped(row):
        state = row["receipt"]["physics"]
        return state["body_forward_velocity_m_s"] == 0 and all(
            w["solver_omega_rad_s"] == 0 for w in state["wheels"]
        )

    first_stop = next(row for row in after if stopped(row))
    if (
        not all(stopped(r) for r in after[after.index(first_stop) :])
        or brake["native"]["admission"]["pressure_pa"] <= 0
        or after[-1]["native"]["admission"]["pressure_pa"] < 1_000_000
    ):
        raise ValueError("brake pressure or physical stop not maintained")
    return dict(
        status="PASS",
        scope="Native IPC peer disconnect in moving simulation-time SIL; no positive visual input",
        trace_sha256=sha(path),
        physical_intervals=len(rows) - 1,
        paired_work_settlements=len(rows) - 1,
        normal_intervals=verdict["normal_intervals"],
        closed_at_frame=lost["frame"],
        incoming_speed_m_s=lost["physics"]["body_forward_velocity_m_s"],
        observed_disconnect_wall_ns=event["detected_wall_ns"] - event["closed_wall_ns"],
        first_protective_stage_frame=brake["frame"],
        first_protective_torque_nm=torque[1],
        zero_torque_stage_frame=zero_torque["frame"],
        first_brake_pressure_pa=brake["native"]["admission"]["pressure_pa"],
        stopped_physical_frame=int(first_stop["receipt"]["frame"]),
        simulation_seconds_until_held_stop=first_stop["receipt"][
            "simulation_end_seconds"
        ]
        - lost["simulation_seconds"],
        final_pressure_pa=after[-1]["native"]["admission"]["pressure_pa"],
        actual_visual_admissions=0,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    result = audit(a.run)
    with a.output.open("x") as out:
        json.dump(result, out, indent=2, allow_nan=False)
        out.write("\n")

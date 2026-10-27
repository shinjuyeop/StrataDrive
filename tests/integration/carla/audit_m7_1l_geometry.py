#!/usr/bin/env python3
"""Independent SE(3)/reference-pose/COM audit of real, saved geometry."""
import argparse
import copy
import json
import math
from pathlib import Path

EPS32 = 2**-23
BONES = ("Wheel_Front_Left", "Wheel_Front_Right", "Wheel_Rear_Left", "Wheel_Rear_Right")


def require(value, reason):
    if not value:
        raise ValueError(reason)


def add(a, b):
    return [x+y for x, y in zip(a, b)]


def sub(a, b):
    return [x-y for x, y in zip(a, b)]


def rotate(q, v):
    # Independent quaternion-to-matrix expansion; no UE/CARLA math imports.
    x, y, z, w = q
    require(abs(sum(t*t for t in q)-1) < 16*EPS32, "nonunit quaternion")
    matrix = ((1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)),
              (2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)),
              (2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)))
    return [sum(a*b for a, b in zip(row, v)) for row in matrix]


def apply(t, v):
    return add(t["translation_m"], rotate(t["quaternion_xyzw"], [a*b for a, b in zip(v, t["scale"])]))


def inverse(t, v):
    x, y, z, w = t["quaternion_xyzw"]
    return [a/b for a, b in zip(rotate([-x, -y, -z, w], sub(v, t["translation_m"])), t["scale"])]


def reflect(v):
    return [v[0], -v[1], v[2]]


def tolerance(*vectors):
    # Prespecified float32 roundoff budget for <=64 arithmetic operations per
    # coordinate transform. Numerical comparison only, never a sensor epsilon.
    return 64*EPS32*max(1., *(abs(x) for v in vectors for x in v))


def close(a, b, reason, *reference_scale):
    require(len(a) == len(b) == 3 and all(math.isfinite(x) for x in a+b), reason+" finite")
    error = max(abs(x-y) for x, y in zip(a, b))
    require(error <= tolerance(a, b, *reference_scale), reason)
    return error


def audit(result):
    require(result["status"] == "PASS_READBACK_ONLY", "runtime")
    require(result["original_settings"] == result["restored_settings"] and not result["remaining_vehicle_ids"], "cleanup")
    require(len(result["snapshots"]) == 5, "poses")
    require(len({s["binding"]["session"] for s in result["snapshots"]}) == 5 and
            len({s["binding"]["actor"] for s in result["snapshots"]}) == 5, "distinct INIT identities")
    if "reset_geometry_guard" in result:
        guard = result["reset_geometry_guard"]
        require(guard["reset"]["ok"] and guard["reset"]["latched"] and
                not guard["rejected"]["ok"] and guard["rejected"]["reason"] == "geometry_generation", "reset geometry guard")
    rows = []
    max_error = 0
    first_actor_points = None
    for sample in result["snapshots"]:
        snap = sample["snapshot"]
        g = snap["geometry"]
        require(all(snap[key] == sample["binding"][key] for key in ("run", "session", "actor")), "geometry source identity")
        require(snap["frame"] == sample["binding"]["frame"] and g["valid"] and g["inputs_zero"], "frozen frame")
        require(g["schema"] == "m7-rest-geometry-v1" and len(g["wheels"]) == 4, "schema")
        close(g["mesh_relative_scale"], [1, 1, 1], "unsupported mesh scale")
        require([w["bone"] for w in g["wheels"]] == list(BONES), "wheel order")
        require(g["mass_kg"] == sample["public_physics"]["mass_kg"], "mass")
        # RPC uses geom::Location: the C++ COMNudge in cm has already become m.
        close(sample["public_physics"]["center_of_mass_field"], g["com_nudge_m"], "COMNudge field")
        local = []
        for i, wheel in enumerate(g["wheels"]):
            require(wheel["index"] == i, "wheel index")
            # UE reference bone -> scaled mesh -> root body, plus class/setup offsets.
            scaled_bone = [x*s for x, s in zip(wheel["reference_bone_mesh_m"], g["mesh_relative_scale"])]
            expected_rest = add(inverse(g["reference_root_body_mesh"], scaled_bone),
                                add(wheel["class_offset_m"], wheel["setup_offset_m"]))
            paths = (
                (expected_rest, wheel["ue_rest_body_m"], "reference pose/rest body"),
                (apply(g["com_body"], wheel["px_rest_com_m"]), wheel["px_rest_body_m"], "COM/body"),
                (wheel["px_rest_body_m"], wheel["ue_rest_body_m"], "PhysX/UE rest"),
                (apply(g["body_world"], wheel["px_rest_body_m"]), wheel["px_rest_world_m"], "body/world"),
                (inverse(g["actor_world"], wheel["px_rest_world_m"]), wheel["px_rest_actor_m"], "world/actor"),
            )
            for a, b, name in paths:
                context = [g["actor_world"]["translation_m"]] if name == "world/actor" else []
                max_error = max(max_error, close(a, b, name, *context))
            public = sample["public_physics"]["wheels"][i]
            require(abs(public["radius_cm"]/100-wheel["radius_m"]) <= EPS32, "cm/m radius")
            require(public["max_brake_nm"] == wheel["max_brake_nm"], "Nm readback")
            require(abs(math.radians(public["max_steer_deg"])-wheel["max_steer_rad"]) < 16*EPS32, "deg/rad")
            local.append(wheel["px_rest_actor_m"])
        # Static rest geometry must not change with the world INIT orientation.
        if first_actor_points is None:
            first_actor_points = local
        else:
            for before, after in zip(first_actor_points, local):
                max_error = max(max_error, close(before, after, "INIT invariant actor geometry", g["actor_world"]["translation_m"]))
        front = [(a+b)/2 for a, b in zip(local[0], local[1])]
        rear = [(a+b)/2 for a, b in zip(local[2], local[3])]
        require(front[0] > rear[0] and local[0][1] < local[1][1] and local[2][1] < local[3][1], "forward/left wheel identity")
        world_rear = apply(g["actor_world"], rear)
        projected = dict(g["actor_world"])
        qx, qy, qz, qw = projected["quaternion_xyzw"]
        projected["quaternion_xyzw"] = [-qx, qy, -qz, qw]
        projected["translation_m"] = reflect(projected["translation_m"])
        max_error = max(max_error, close(reflect(world_rear), apply(projected, reflect(rear)), "project reflection"))
        rows.append(dict(init_pose=sample["init_pose"], rear_axle_actor_m=rear,
                         rear_axle_project_actor_m=reflect(rear), rear_axle_world_m=world_rear,
                         wheelbase_actor_x_m=front[0]-rear[0],
                         front_track_actor_y_m=local[1][1]-local[0][1],
                         rear_track_actor_y_m=local[3][1]-local[2][1],
                         actual_com_body_m=g["com_body"]["translation_m"], com_nudge_m=g["com_nudge_m"]))
    return dict(status="PASS_REST_GEOMETRY_ONLY", poses=len(rows), wheel_order=list(BONES),
                max_cross_check_error_m=max_error, roundoff_budget="64*2^-23*max(1, compared coordinate magnitudes)",
                poses_derived=rows, steering_actuation_sign="NOT RUN", pressure_calibration="UNAVAILABLE",
                normal_driving_enabled=False, physics_reset_geometry_rejected="reset_geometry_guard" in result)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("result", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    try:
        source = json.loads(args.result.read_text())
        report = audit(source)
        faults = {
            "unit_cm_as_m": lambda g: g["wheels"][0].update(px_rest_com_m=[x*100 for x in g["wheels"][0]["px_rest_com_m"]]),
            "swap_wheels": lambda g: g["wheels"].__setitem__(slice(0, 2), list(reversed(g["wheels"][:2]))),
            "COMNudge_as_actual_COM": lambda g: g["com_body"].update(translation_m=g["com_nudge_m"]),
            "wrong_y_handedness": lambda g: g["wheels"][0].update(px_rest_actor_m=reflect(g["wheels"][0]["px_rest_actor_m"])),
            "zero_rear_axle": lambda g: g["wheels"][2].update(px_rest_actor_m=[0, 0, 0]),
            "nonfinite": lambda g: g["wheels"][0].update(px_rest_com_m=[float("nan"), 0, 0]),
        }
        report["corruption_rejections"] = {}
        for name, corrupt in faults.items():
            broken = copy.deepcopy(source)
            corrupt(broken["snapshots"][0]["snapshot"]["geometry"])
            try:
                audit(broken)
            except ValueError as exc:
                report["corruption_rejections"][name] = str(exc)
            else:
                raise ValueError("accepted corruption: "+name)
        broken = copy.deepcopy(source)
        broken["snapshots"][0]["snapshot"]["actor"] = broken["snapshots"][1]["snapshot"]["actor"]
        try:
            audit(broken)
        except ValueError as exc:
            report["corruption_rejections"]["different_actor_same_frame"] = str(exc)
        else:
            raise ValueError("accepted geometry from another actor")
    except Exception as exc:
        report = dict(status="FAIL", error=str(exc))
    args.output.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report))
    return 0 if report["status"] == "PASS_REST_GEOMETRY_ONLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Pure, auditable road-relative placement and camera geometry for M10 preparation."""

import math


def finite(values):
    if not all(type(v) in (int, float) and math.isfinite(v) for v in values):
        raise ValueError("finite geometry required")


def angle_delta(a, b):
    finite((a, b))
    return (a - b + 180) % 360 - 180


def route_choice(previous_yaw, candidates):
    """Smallest local turn, then stable road identity; never SDK list order."""
    if not candidates:
        raise ValueError("route ends before requested distance")
    return min(
        candidates,
        key=lambda p: (
            abs(angle_delta(p["pose"]["rotation"]["yaw"], previous_yaw)),
            p["road_id"],
            p["section_id"],
            p["lane_id"],
            p["s"],
            p["id"],
        ),
    )


def road_pose(node, right_m, clearance_m, yaw_offset=0):
    """Use surveyed lane height/attitude; right offset follows the road bank."""
    p = node["pose"]
    loc, rot = p["location"], p["rotation"]
    finite(
        tuple(loc.values())
        + tuple(rot.values())
        + (right_m, clearance_m, yaw_offset, node["lane_width"])
    )
    if node["lane_width"] <= 0 or abs(right_m) > node["lane_width"] / 2 - 0.2:
        raise ValueError("actor center outside declared lane margin")
    yaw, pitch, roll = map(math.radians, (rot["yaw"], rot["pitch"], rot["roll"]))
    # CARLA/UE right vector; unlike yaw-only placement this preserves road bank.
    right = (
        math.cos(yaw) * math.sin(pitch) * math.sin(roll)
        - math.sin(yaw) * math.cos(roll),
        math.sin(yaw) * math.sin(pitch) * math.sin(roll)
        + math.cos(yaw) * math.cos(roll),
        -math.cos(pitch) * math.sin(roll),
    )
    return dict(
        location=dict(
            x=loc["x"] + right_m * right[0],
            y=loc["y"] + right_m * right[1],
            z=loc["z"] + right_m * right[2] + clearance_m,
        ),
        rotation=dict(
            pitch=rot["pitch"],
            yaw=(rot["yaw"] + yaw_offset + 180) % 360 - 180,
            roll=rot["roll"],
        ),
    )


def camera_projection(camera, target):
    """640x384/FOV90 pinhole; geometry screen only, cannot see mesh occlusion."""
    c, r = camera["location"], camera["rotation"]
    t = target["location"]
    finite(tuple(c.values()) + tuple(r.values()) + tuple(t.values()))
    yaw, pitch, roll = map(math.radians, (r["yaw"], r["pitch"], r["roll"]))
    cy, sy, cp, sp, cr, sr = (
        math.cos(yaw),
        math.sin(yaw),
        math.cos(pitch),
        math.sin(pitch),
        math.cos(roll),
        math.sin(roll),
    )
    forward = (cp * cy, cp * sy, sp)
    right = (cy * sp * sr - sy * cr, sy * sp * sr + cy * cr, -cp * sr)
    up = (-cy * sp * cr - sy * sr, -sy * sp * cr + cy * sr, cp * cr)
    delta = [t[k] - c[k] for k in ("x", "y", "z")]
    depth = sum(a * b for a, b in zip(delta, forward))
    if depth <= 0:
        return dict(depth_m=depth, u=None, v=None, in_frame=False)
    u = 320 + 320 * sum(a * b for a, b in zip(delta, right)) / depth
    v = 192 - 320 * sum(a * b for a, b in zip(delta, up)) / depth
    return dict(depth_m=depth, u=u, v=v, in_frame=8 <= u < 632 and 8 <= v < 376)


def check_pose(actual, expected):
    for p in (actual, expected):
        finite(tuple(p["location"].values()) + tuple(p["rotation"].values()))
    if math.dist(
        [actual["location"][k] for k in ("x", "y", "z")],
        [expected["location"][k] for k in ("x", "y", "z")],
    ) > 0.02 or any(
        abs(angle_delta(actual["rotation"][k], expected["rotation"][k])) > 0.1
        for k in ("pitch", "yaw", "roll")
    ):
        raise ValueError("settled pose differs from surveyed road plan")


def route_eligible(site):
    nodes = site["nodes"]
    if (
        set(nodes) != {str(n) for n in range(43)}
        or site["spawn_point_index"] < 7
        or "camera_pose" not in site
        or "base_clearance_m" not in site
    ):
        return False
    return (
        not any(n["is_junction"] for n in nodes.values())
        and all(n["lane_width"] >= 3.2 for n in nodes.values())
        and max(
            abs(
                angle_delta(
                    n["pose"]["rotation"]["yaw"], nodes["0"]["pose"]["rotation"]["yaw"]
                )
            )
            for n in nodes.values()
        )
        <= 15
        and all(
            camera_projection(
                site["camera_pose"],
                road_pose(nodes[str(n)], 0, site["base_clearance_m"] + 0.5),
            )["in_frame"]
            for n in range(5, 43)
        )
    )


def select_sites(sites):
    selected = []
    for site in sorted(sites, key=lambda s: s["spawn_point_index"]):
        if not route_eligible(site):
            continue
        pos = site["nodes"]["0"]["pose"]["location"]
        if any(
            s["nodes"]["0"]["road_id"] == site["nodes"]["0"]["road_id"]
            or math.dist(
                [pos[k] for k in ("x", "y", "z")],
                [s["nodes"]["0"]["pose"]["location"][k] for k in ("x", "y", "z")],
            )
            < 50
            for s in selected
        ):
            continue
        selected.append(site)
        if len(selected) == 2:
            break
    if len(selected) != 2:
        raise ValueError("two separated nonjunction camera sites required")
    return selected

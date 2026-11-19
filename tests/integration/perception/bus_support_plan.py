"""Materialize the new Town06 geometry with the original holdout scene template."""

from functools import lru_cache
import hashlib
import json
import math

import carla
from multiview_plan import (
    ROOT,
    TEMPLATE,
    XODR as TOWN04,
    read,
    digest,
    node,
    road_pose,
    route_eligible,
    angle_delta,
    build,
    validate_plan,
)

WORK = ROOT / "build/m10-bus-support-v1"
EVIDENCE = ROOT / "docs/test-plan/evidence/m10_bus_support_v1"
PREVIOUS = ROOT / "build/m10-cycle-transfer-v1/native"


@lru_cache(maxsize=1)
def plans():
    town = "Town06_Opt"
    xodr = TOWN04.with_name(town + ".xodr")
    map_ = carla.Map(town, xodr.read_text())
    sites = []
    geometry = []
    origins = []
    roads = set()
    waypoints = sorted(
        map_.generate_waypoints(10), key=lambda p: (p.road_id, p.lane_id, p.s)
    )
    for index, wp in enumerate(waypoints, start=7):
        if wp.road_id in roads or wp.is_junction:
            continue
        head = node(wp)
        pose = head["pose"]
        distance = min(
            (
                math.hypot(
                    pose["location"]["x"] - s["location"]["x"],
                    pose["location"]["y"] - s["location"]["y"],
                )
                for s in origins
            ),
            default=None,
        )
        if distance is not None and distance < 75:
            continue
        nodes = {"0": head}
        for d in range(1, 43):
            options = wp.next(1)
            if len(options) != 1:
                break
            wp = options[0]
            if (
                wp.is_junction
                or wp.road_id != head["road_id"]
                or abs(wp.transform.rotation.pitch) > 2
                or abs(angle_delta(wp.transform.rotation.yaw, pose["rotation"]["yaw"]))
                > 2
            ):
                break
            nodes[str(d)] = node(wp)
        camera = road_pose(head, 0, 2.1)
        camera["rotation"]["pitch"] -= 6
        site = dict(
            spawn_point_index=index,
            nodes=nodes,
            camera_pose=camera,
            base_clearance_m=0.4,
            eligible=True,
        )
        if route_eligible(site):
            sites.append(site)
            origins.append(camera)
            roads.add(head["road_id"])
            geometry.append(
                dict(
                    site=index,
                    road=head["road_id"],
                    lane=head["lane_id"],
                    nearest_dev_m=distance,
                )
            )
            if len(sites) == 2:
                break
    if len(sites) != 2:
        raise ValueError("independent route count")
    # Only the holdout partition is acquired. The first eligible road is the holdout.
    sites.reverse()
    geometry.reverse()
    template = read(TEMPLATE)
    template["map"] = town
    for case in template["partitions"]["holdout"]["cases"]:
        if case["stratum"] == "occluded" and case["target_class"] == 0:
            next(a for a in case["actors"] if a["role"] == "occluder")["right_m"] = -0.6
    survey = dict(
        schema="m10-road-survey-v4",
        status="PASS",
        client_version="294096e-dirty",
        server_version="294096e-dirty",
        sites=sites,
        selected_sites=[s["spawn_point_index"] for s in sites],
        xodr_sha256=digest(xodr),
    )
    result = dict(
        sites=dict(
            map=town,
            development=geometry[0],
            holdout=geometry[1],
            xodr_sha256=digest(xodr),
        )
    )
    survey_sha = hashlib.sha256(json.dumps(survey, sort_keys=True).encode()).hexdigest()
    for plan in build(survey, survey_sha, template, digest(TEMPLATE)):
        validate_plan(plan)
        plan.update(
            schema="m10-bus-support-2k-v1",
            camera=dict(width=2560, height=1536, horizontal_fov=90),
            canonical_evaluation=[640, 384],
            sensor_tick_seconds=0.1,
            alignment_ticks=35,
            readback_ticks=3,
        )
        del plan["selected_capture_tick"], plan["created_date"]
        result[plan["phase"]] = plan
    return result


def validate_retained(directory):
    if any(read(directory / (k + ".json")) != v for k, v in plans().items()):
        raise ValueError("retained cycle evaluation plan changed")

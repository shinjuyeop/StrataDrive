"""Plan two disjoint native-quality roads after the sealed road-8 evaluation."""

from functools import lru_cache
import math

import carla
from bus_recall_plan import (
    XODR,
    SURVEY,
    TEMPLATE,
    ROOT,
    digest,
    read,
    node,
    road_pose,
    route_eligible,
    angle_delta,
    build,
    validate_plan,
)

WORK = ROOT / "build/m10-multiview-v1"
EVIDENCE = ROOT / "docs/test-plan/evidence/m10_multiview_v1"


@lru_cache(maxsize=1)
def plans():
    survey = read(SURVEY)
    prev = read(ROOT / "build/m10-bus-recall-v1/holdout/plan/sites.json")
    roads = set(prev["excluded_roads"]) | {prev["road"]}
    used = set(prev["excluded_sites"]) | set(prev["selected"])
    sites = [s for s in survey["sites"] if s["spawn_point_index"] in used]
    origins = [s["nodes"]["0"]["pose"]["location"] for s in sites]
    old_plan = read(ROOT / "build/m10-bus-recall-v1/holdout/plan/evaluation.json")
    origins.append(old_plan["partitions"]["holdout"]["camera_pose"]["location"])
    if digest(XODR) != prev["xodr_sha256"]:
        raise ValueError("map identity")
    m = carla.Map("Town04_Opt", XODR.read_text())
    selected = []
    records = []
    for index, wp in enumerate(
        sorted(m.generate_waypoints(10), key=lambda w: (w.road_id, w.lane_id, w.s)),
        start=len(survey["sites"]),
    ):
        base = node(wp)
        loc = base["pose"]["location"]
        distance = min(
            math.hypot(loc["x"] - o["x"], loc["y"] - o["y"]) for o in origins
        )
        if distance < 75 or wp.road_id in roads or wp.is_junction:
            continue
        nodes = {"0": base}
        for d in range(1, 43):
            opts = wp.next(1)
            if len(opts) != 1:
                break
            wp = opts[0]
            if (
                wp.road_id != base["road_id"]
                or wp.is_junction
                or abs(
                    angle_delta(
                        wp.transform.rotation.yaw, base["pose"]["rotation"]["yaw"]
                    )
                )
                > 2
                or abs(wp.transform.rotation.pitch) > 2
            ):
                break
            nodes[str(d)] = node(wp)
        camera = road_pose(base, 0, 2.1)
        camera["rotation"]["pitch"] -= 6
        site = dict(
            spawn_point_index=index,
            base_clearance_m=0.4,
            camera_pose=camera,
            nodes=nodes,
            eligible=True,
        )
        if not route_eligible(site):
            continue
        selected.append(site)
        roads.add(base["road_id"])
        origins.append(loc)
        records.append(
            dict(
                site=index,
                road=base["road_id"],
                lane=base["lane_id"],
                nearest_prior_m=distance,
            )
        )
        if len(selected) == 2:
            break
    if len(selected) != 2:
        raise ValueError(f"fresh lane count {records}")
    template = read(TEMPLATE)
    for case in template["partitions"]["holdout"]["cases"]:
        if case["stratum"] == "occluded" and case["target_class"] == 0:
            (blocker,) = [a for a in case["actors"] if a["role"] == "occluder"]
            blocker["right_m"] = -0.6
    result = dict(
        sites=dict(development=records[0], holdout=records[1], xodr_sha256=digest(XODR))
    )
    for plan in build(
        dict(
            survey,
            sites=selected,
            selected_sites=[s["spawn_point_index"] for s in selected],
        ),
        digest(SURVEY),
        template,
        digest(TEMPLATE),
    ):
        validate_plan(plan)
        plan.update(
            schema="m10-multiview-2k-v1",
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
    for key, value in plans().items():
        if read(directory / (key + ".json")) != value:
            raise ValueError("plan changed")

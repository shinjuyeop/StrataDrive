"""Select a previously unused Town04 lane from the original OpenDRIVE on a 10 m grid."""

import math
from functools import lru_cache

import carla
from carla_quality_layout_v9 import node
from fresh_quality_2k_plan import SURVEY, TEMPLATE, ROOT, digest, read
from quality_geometry_v4 import road_pose, route_eligible, angle_delta
from quality_plan_v4 import build, validate_plan

WORK = ROOT / "build/m10-bus-recall-v1"
EVIDENCE = ROOT / "docs/test-plan/evidence/m10_bus_recall_v1"
XODR = (
    ROOT.parent
    / "stratadrive-tools/m7-source/carla-0.9.16/Unreal/CarlaUE4/Content/Carla/Maps/OpenDrive/Town04_Opt.xodr"
)


@lru_cache(maxsize=1)
def plans():
    prior = read(ROOT / "build/m10-person-support-v1/holdout/plan/sites.json")
    old = read(SURVEY)
    if digest(XODR) != old["xodr_sha256"] or digest(SURVEY) != prior["survey_sha256"]:
        raise ValueError("Town04 geometry changed")
    used = set(prior["excluded_sites"]) | set(prior["selected"]) | set(range(7))
    previous = [v for v in old["sites"] if v["spawn_point_index"] in used]
    roads = {n["road_id"] for v in previous for n in v["nodes"].values()}
    origins = [v["nodes"]["0"]["pose"]["location"] for v in previous]
    m = carla.Map("Town04_Opt", XODR.read_text())
    for index, wp in enumerate(
        sorted(m.generate_waypoints(10), key=lambda w: (w.road_id, w.lane_id, w.s)),
        start=len(old["sites"]),
    ):
        base = node(wp)
        loc = base["pose"]["location"]
        nearest = min(
            math.dist(tuple(loc[k] for k in "xyz"), tuple(o[k] for k in "xyz"))
            for o in origins
        )
        if nearest < 75 or wp.road_id in roads or wp.is_junction:
            continue
        nodes = {"0": base}
        for d in range(1, 43):
            forward = wp.next(1)
            if len(forward) != 1:
                break
            wp = forward[0]
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
        cam = road_pose(base, 0, 2.1)
        cam["rotation"]["pitch"] -= 6
        site = dict(
            spawn_point_index=index,
            base_clearance_m=0.4,
            camera_pose=cam,
            nodes=nodes,
            eligible=True,
        )
        if route_eligible(site):
            break
    else:
        raise ValueError("no eligible lane")
    dev = next(v for v in old["sites"] if v["spawn_point_index"] == 90)
    ids = [90, index]
    survey = dict(old, sites=[dev, site], selected_sites=ids)
    template = read(TEMPLATE)
    for case in template["partitions"]["holdout"]["cases"]:
        if case["stratum"] == "occluded" and case["target_class"] == 0:
            (blocker,) = [a for a in case["actors"] if a["role"] == "occluder"]
            blocker["right_m"] = -0.6
    result = dict(
        sites=dict(
            selected=ids,
            road=base["road_id"],
            lane=base["lane_id"],
            s=base["s"],
            nearest_prior_camera_m=nearest,
            excluded_roads=sorted(roads),
            excluded_sites=sorted(used),
            xodr_sha256=digest(XODR),
            grid_m=10,
        )
    )
    for plan in build(survey, digest(SURVEY), template, digest(TEMPLATE)):
        validate_plan(plan)
        plan.update(
            schema="m10-bus-transfer-2k-v1",
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
    for name, value in plans().items():
        if read(directory / (name + ".json")) != value:
            raise ValueError("route plan changed")

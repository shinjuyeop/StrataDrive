"""Prospective six-class follow-up on a road excluded from every earlier Town04 split."""

import math

from fresh_quality_2k_plan import ROOT, SURVEY, TEMPLATE, read, digest
from person_proposal_diagnosis import PREV
from quality_plan_v4 import build, validate_plan
from quality_geometry_v4 import route_eligible


def plans():
    survey = read(SURVEY)
    prior = read(
        ROOT / "docs/test-plan/evidence/m10_fresh_quality_2k_v1/plan/sites.json"
    )
    if prior["survey_sha256"] != digest(SURVEY) or prior["template_sha256"] != digest(
        TEMPLATE
    ):
        raise ValueError("survey or template identity")
    used = set(prior["used_sites"])
    used.update(s["spawn_index"] for s in prior["selected"].values())
    used.update(
        int(s["id"].split("-")[0])
        for s in read(PREV / "run-02/dataset/plan.json")["scenes"]
    )
    sites = {s["spawn_point_index"]: s for s in survey["sites"]}
    descriptor = dict(
        schema="m10-used-map-roads-v9",
        map="Town04_Opt",
        route_road_ids=sorted(
            {n["road_id"] for i in used for n in sites[i]["nodes"].values()}
        ),
        route_origins=[
            sites[i]["nodes"]["0"]["pose"]["location"] for i in sorted(used)
        ],
    )

    def fresh(s):
        if not route_eligible(s) or set(descriptor["route_road_ids"]).intersection(
            n["road_id"] for n in s["nodes"].values()
        ):
            return False
        origin = s["nodes"]["0"]["pose"]["location"]
        return all(
            math.dist([origin[k] for k in "xyz"], [o[k] for k in "xyz"]) >= 50
            for o in descriptor["route_origins"]
        )

    holdout = next(
        s
        for s in sorted(survey["sites"], key=lambda s: s["spawn_point_index"])
        if fresh(s)
    )
    indices = [
        prior["selected"]["development"]["spawn_index"],
        holdout["spawn_point_index"],
    ]
    template = read(TEMPLATE)
    # Carry the previously qualified partial-occlusion geometry forward.
    for case in template["partitions"]["holdout"]["cases"]:
        if case["stratum"] == "occluded" and case["target_class"] == 0:
            (blocker,) = [a for a in case["actors"] if a["role"] == "occluder"]
            blocker["right_m"] = -0.6
    result = dict(
        sites=dict(
            excluded_sites=sorted(used),
            excluded_roads=descriptor["route_road_ids"],
            selected=indices,
            survey_sha256=digest(SURVEY),
        )
    )
    for plan in build(
        dict(survey, selected_sites=indices), digest(SURVEY), template, digest(TEMPLATE)
    ):
        for part in plan["partitions"].values():
            for case in part["cases"]:
                for key in ("id", "reference_for"):
                    if key in case:
                        case[key] = case[key].replace("v4-", "support-2k-", 1)
        validate_plan(plan)
        plan.update(
            schema="m10-person-support-holdout-v1",
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
    for name, expected in plans().items():
        if read(directory / (name + ".json")) != expected:
            raise ValueError(f"fresh {name} identity")

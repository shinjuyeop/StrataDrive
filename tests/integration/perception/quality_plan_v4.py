#!/usr/bin/env python3
"""Turn a saved road survey into explicit, reproducible preparation/evaluation poses."""

import argparse
from copy import deepcopy
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import read_json
from quality_benchmark import require, write_new
from quality_geometry_v4 import road_pose, camera_projection, route_eligible

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / "profiles/perception-quality-plan-v3.json"


def build(survey, survey_sha256, template, template_sha256):
    require(
        survey["schema"] == "m10-road-survey-v4"
        and survey["status"] == "PASS"
        and survey["client_version"] == survey["server_version"] == "294096e-dirty"
        and len(set(survey["selected_sites"])) == 2,
        "road survey identity",
    )
    sites = {s["spawn_point_index"]: s for s in survey["sites"]}
    common = {
        k: deepcopy(template[k])
        for k in (
            "map",
            "server_quality",
            "rgb_postprocess",
            "world_step_ns",
            "sensor_tick_seconds",
            "settle_ticks",
            "capture_ticks",
            "selected_capture_tick",
            "seed",
        )
    }
    common.update(
        created_date="2026-11-09",
        schema="m10-road-plan-v4",
        survey_sha256=survey_sha256,
        xodr_sha256=survey["xodr_sha256"],
        template_sha256=template_sha256,
        scope="Finite stationary visible-mask fixture; lane route poses are not physical driving or ODD acceptance",
        placement_revision="v4c",
        held_person_far_m=26,
        placement_limit="Held walker0010 evaluation far26m/preparation27m; earlier31m preparation24px failed; no>=30m person acceptance",
    )
    evaluation = dict(deepcopy(common), phase="evaluation", partitions={})
    preparation = dict(
        deepcopy(common),
        schema="m10-road-preparation-plan-v4",
        phase="preparation",
        partitions={},
    )
    for part, index in zip(("development", "holdout"), survey["selected_sites"]):
        site = sites[index]
        require(site["eligible"] and route_eligible(site), "selected site not eligible")
        for plan, preparing in ((evaluation, False), (preparation, True)):
            camera = deepcopy(site["camera_pose"])
            if preparing:
                camera["location"]["z"] += 0.05
            cases = []
            for n, source in enumerate(template["partitions"][part]["cases"]):
                case = {
                    k: deepcopy(source[k])
                    for k in ("weather", "stratum", "target_class")
                }
                case.update(
                    id=f"v4-{'preparation-' if preparing else ''}{part}-{n:03d}",
                    actors=[],
                )
                for a in source["actors"]:
                    requested = (
                        26
                        if part == "holdout"
                        and source["stratum"] == "far"
                        and a["class_id"] == 0
                        else a["forward_m"]
                    )
                    distance = requested + int(preparing)
                    require(
                        type(distance) is int and str(distance) in site["nodes"],
                        "survey route distance",
                    )
                    node = site["nodes"][str(distance)]
                    actor = {
                        k: a[k]
                        for k in (
                            "class_id",
                            "blueprint",
                            "role",
                            "right_m",
                            "z_offset_m",
                            "yaw_offset_degrees",
                        )
                    }
                    actor.update(
                        route_distance_m=distance,
                        road_node=deepcopy(node),
                        clearance_m=site["base_clearance_m"] + a["z_offset_m"],
                    )
                    actor["pose"] = road_pose(
                        node,
                        actor["right_m"],
                        actor["clearance_m"],
                        actor["yaw_offset_degrees"],
                    )
                    projection = camera_projection(camera, actor["pose"])
                    require(
                        projection["in_frame"],
                        "planned actor origin outside camera frustum",
                    )
                    actor["camera_projection"] = projection
                    case["actors"].append(actor)
                cases.append(case)
            if preparing:
                for case in list(cases):
                    if case["stratum"] != "occluded":
                        continue
                    ref = deepcopy(case)
                    ref.update(
                        id=f"v4-preparation-{part}-{len(cases):03d}",
                        stratum="occluded_reference",
                        reference_for=case["id"],
                    )
                    ref["actors"] = [a for a in ref["actors"] if a["role"] == "target"]
                    cases.append(ref)
            plan["partitions"][part] = dict(
                spawn_point_index=index,
                camera_pose=camera,
                base_clearance_m=site["base_clearance_m"],
                cases=cases,
            )
    preparation["preparation_offsets"] = dict(
        actor_route_m=1,
        camera_world_z_m=0.05,
        reason="Same actual camera sites; nearby distinct preparation poses/RGB are never evaluation samples",
    )
    return evaluation, preparation


def validate_plan(plan):
    require(
        plan["schema"] in ("m10-road-plan-v4", "m10-road-preparation-plan-v4")
        and set(plan["partitions"]) == {"development", "holdout"},
        "v4 plan schema",
    )
    seen = set()
    for part, settings in plan["partitions"].items():
        require(
            len(settings["cases"]) == (99 if plan["phase"] == "preparation" else 81),
            "plan denominator",
        )
        for case in settings["cases"]:
            require(case["id"] not in seen, "duplicate case ID")
            seen.add(case["id"])
            for actor in case["actors"]:
                require(
                    actor["blueprint"] != "vehicle.carlamotors.european_hgv",
                    "incompatible NW asset",
                )
                expected = road_pose(
                    actor["road_node"],
                    actor["right_m"],
                    actor["clearance_m"],
                    actor["yaw_offset_degrees"],
                )
                require(
                    expected == actor["pose"],
                    "explicit pose differs from surveyed route",
                )
                require(
                    camera_projection(settings["camera_pose"], expected)
                    == actor["camera_projection"]
                    and actor["camera_projection"]["in_frame"],
                    "camera projection drift",
                )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("survey", type=Path)
    p.add_argument("evaluation", type=Path)
    p.add_argument("preparation", type=Path)
    a = p.parse_args()
    evaluation, preparation = build(
        read_json(a.survey),
        sha256_file(a.survey),
        read_json(TEMPLATE),
        sha256_file(TEMPLATE),
    )
    for path, value in ((a.evaluation, evaluation), (a.preparation, preparation)):
        validate_plan(value)
        write_new(path, value)
    print(
        dict(
            evaluation_cases=162,
            preparation_cases=198,
            sites=read_json(a.survey)["selected_sites"],
        )
    )

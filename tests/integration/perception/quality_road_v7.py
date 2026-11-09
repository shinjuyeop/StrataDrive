"""Fresh sites selected from the original complete map query, never image scores."""

from copy import deepcopy
from pathlib import Path
import math
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.dataset import read_json
from physical_ai.perception.contract import sha256_file
from quality_geometry_v4 import route_eligible
from quality_plan_v4 import build as build_v4, validate_plan as validate_v4, TEMPLATE
from quality_benchmark import require

ROOT = Path(__file__).resolve().parents[3]
SURVEY = ROOT / "docs/test-plan/evidence/m10_road_preparation_v4/survey-selected.json"
USED_SITES = (0, 1, 2, 3, 4, 5, 6, 14, 18, 24, 31, 35, 74, 80, 104)


def select_fresh(survey):
    used = [s for s in survey["sites"] if s["spawn_point_index"] in USED_SITES]
    chosen = []
    for site in sorted(survey["sites"], key=lambda s: s["spawn_point_index"]):
        if site["spawn_point_index"] in USED_SITES or not route_eligible(site):
            continue
        node = site["nodes"]["0"]
        if any(
            node["road_id"] == s["nodes"]["0"]["road_id"]
            or math.dist(
                list(node["pose"]["location"].values()),
                list(s["nodes"]["0"]["pose"]["location"].values()),
            )
            < 50
            for s in used + chosen
        ):
            continue
        chosen.append(site)
        if len(chosen) == 2:
            break
    require(len(chosen) == 2, "two unused separated roads required")
    require(
        [s["spawn_point_index"] for s in chosen] == [127, 215],
        "reserved holdout and next eligible road",
    )
    return [215, 127]


def build():
    survey = read_json(SURVEY)
    survey["selected_sites"] = select_fresh(survey)
    evaluation, preparation = build_v4(
        survey, sha256_file(SURVEY), read_json(TEMPLATE), sha256_file(TEMPLATE)
    )
    for plan in (evaluation, preparation):
        plan.update(
            schema="m10-road-preparation-plan-v7"
            if plan["phase"] == "preparation"
            else "m10-road-plan-v7",
            placement_revision="v7",
            excluded_previous_camera_sites=list(USED_SITES),
            site_selection="Map-only unused roads >=50m from previous sites and each other; reserved127 held, next215 development",
            survey_source=str(SURVEY.relative_to(ROOT)),
        )
        for part in plan["partitions"].values():
            for case in part["cases"]:
                case["id"] = case["id"].replace("v4-", "v7-", 1)
                if "reference_for" in case:
                    case["reference_for"] = case["reference_for"].replace(
                        "v4-", "v7-", 1
                    )
        validate_plan(plan)
    return evaluation, preparation


def validate_plan(plan):
    require(
        plan["schema"] in ("m10-road-plan-v7", "m10-road-preparation-plan-v7"),
        "v7 road schema",
    )
    compatible = deepcopy(plan)
    compatible["schema"] = (
        "m10-road-plan-v4"
        if plan["phase"] == "evaluation"
        else "m10-road-preparation-plan-v4"
    )
    validate_v4(compatible)
    require(
        all(
            c["id"].startswith("v7-")
            for p in plan["partitions"].values()
            for c in p["cases"]
        ),
        "fresh case IDs",
    )
    require(
        [p["spawn_point_index"] for p in plan["partitions"].values()]
        == select_fresh(read_json(SURVEY)),
        "map-only site replay",
    )

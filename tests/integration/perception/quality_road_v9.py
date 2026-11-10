"""Prospective V9 plans from newly queried unused Town04 route geometry."""

from copy import deepcopy
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import read_json
from quality_benchmark import require
from quality_plan_v4 import build as build_v4, validate_plan as validate_v4
from quality_sites_v9 import select_fresh as select_routes

ROOT = Path(__file__).resolve().parents[3]
SURVEY = ROOT / "docs/test-plan/evidence/m10_quality_v9/survey-selected.json"
TEMPLATE = ROOT / "profiles/perception-quality-template-v9.json"
USED = ROOT / "profiles/perception-quality-v9-used-roads.json"


def select_fresh(survey):
    require(
        survey["status"] == "PASS"
        and survey["map"].rsplit("/", 1)[-1] == "Town04_Opt"
        and survey["used_roads_sha256"] == sha256_file(USED),
        "V9 complete map-only survey",
    )
    return [
        s["spawn_point_index"] for s in select_routes(survey["sites"], read_json(USED))
    ]


def build():
    survey = read_json(SURVEY)
    require(
        survey["selected_sites"] == select_fresh(survey), "first unused route selection"
    )
    require(
        read_json(TEMPLATE)
        == read_json(ROOT / "profiles/perception-quality-template-v8b.json"),
        "unchanged model-free V8b recipe",
    )
    evaluation, preparation = build_v4(
        survey, sha256_file(SURVEY), read_json(TEMPLATE), sha256_file(TEMPLATE)
    )
    for plan in (evaluation, preparation):
        plan.update(
            schema="m10-road-preparation-plan-v9"
            if plan["phase"] == "preparation"
            else "m10-road-plan-v9",
            created_date="2026-11-10",
            placement_revision="v9-fixed-v8b-recipe",
            site_selection="First complete unused Town04 road sets >=50m; no images/models",
            survey_source=str(SURVEY.relative_to(ROOT)),
            used_roads_sha256=sha256_file(USED),
        )
        for settings in plan["partitions"].values():
            for case in settings["cases"]:
                case["id"] = case["id"].replace("v4-", "v9-", 1)
                if "reference_for" in case:
                    case["reference_for"] = case["reference_for"].replace(
                        "v4-", "v9-", 1
                    )
        validate_plan(plan)
    return evaluation, preparation


def validate_plan(plan):
    require(
        plan["schema"] in ("m10-road-plan-v9", "m10-road-preparation-plan-v9")
        and plan["map"] == "Town04_Opt"
        and plan["used_roads_sha256"] == sha256_file(USED),
        "V9 plan identity",
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
            case["id"].startswith("v9-")
            for settings in plan["partitions"].values()
            for case in settings["cases"]
        ),
        "fresh V9 case identities",
    )
    require(
        [p["spawn_point_index"] for p in plan["partitions"].values()]
        == select_fresh(read_json(SURVEY)),
        "complete unused routes replay",
    )

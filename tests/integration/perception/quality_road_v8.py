"""New Town04 map-only first eligible separate roads; no image/model ranking."""

from copy import deepcopy
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.dataset import read_json
from physical_ai.perception.contract import sha256_file
from quality_geometry_v4 import select_sites, route_eligible
from quality_plan_v4 import build as build_v4, validate_plan as validate_v4
from quality_benchmark import require

ROOT = Path(__file__).resolve().parents[3]
SURVEY = ROOT / "docs/test-plan/evidence/m10_quality_v8/survey-selected.json"
TEMPLATE = ROOT / "profiles/perception-quality-template-v8.json"


def select_fresh(survey):
    require(
        survey["status"] == "PASS" and survey["map"].rsplit("/", 1)[-1] == "Town04_Opt",
        "complete new Town04 survey",
    )
    return [s["spawn_point_index"] for s in select_sites(survey["sites"])]


def build():
    survey = read_json(SURVEY)
    require(
        survey["selected_sites"] == select_fresh(survey),
        "first eligible map-only selection",
    )
    template = read_json(TEMPLATE)
    require(template["map"] == "Town04_Opt", "fresh map template")
    evaluation, preparation = build_v4(
        survey, sha256_file(SURVEY), template, sha256_file(TEMPLATE)
    )
    for plan in (evaluation, preparation):
        plan.update(
            schema="m10-road-preparation-plan-v8"
            if plan["phase"] == "preparation"
            else "m10-road-plan-v8",
            created_date="2026-11-10",
            placement_revision="v8",
            site_selection="New Town04 first eligible separate roads >=50m; no image/model ranking",
            survey_source=str(SURVEY.relative_to(ROOT)),
        )
        for part in plan["partitions"].values():
            for case in part["cases"]:
                case["id"] = case["id"].replace("v4-", "v8-", 1)
                if "reference_for" in case:
                    case["reference_for"] = case["reference_for"].replace(
                        "v4-", "v8-", 1
                    )
        validate_plan(plan)
    return evaluation, preparation


def validate_plan(plan):
    require(
        plan["schema"] in ("m10-road-plan-v8", "m10-road-preparation-plan-v8")
        and plan["map"] == "Town04_Opt",
        "v8 new-map plan",
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
            c["id"].startswith("v8-")
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
    by_id = {s["spawn_point_index"]: s for s in read_json(SURVEY)["sites"]}
    require(
        all(
            route_eligible(by_id[p["spawn_point_index"]])
            for p in plan["partitions"].values()
        ),
        "complete nonjunction geometry",
    )

"""Model-free preparation revision: only held person occluder shifts20cm right."""

from copy import deepcopy
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.dataset import read_json
from physical_ai.perception.contract import sha256_file
from quality_road_v8 import SURVEY, select_fresh, validate_plan
from quality_plan_v4 import build as build_v4
from quality_benchmark import require

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / "profiles/perception-quality-template-v8b.json"


def build():
    original = read_json(ROOT / "profiles/perception-quality-template-v8.json")
    expected = deepcopy(original)
    for case in expected["partitions"]["holdout"]["cases"]:
        if case["stratum"] == "occluded" and case["target_class"] == 0:
            for actor in case["actors"]:
                if actor["role"] == "occluder":
                    require(actor["right_m"] == -0.6, "original occluder lateral pose")
                    actor["right_m"] = -0.4
    require(
        read_json(TEMPLATE) == expected,
        "only predeclared model-free20cm occluder revision",
    )
    survey = read_json(SURVEY)
    require(survey["selected_sites"] == select_fresh(survey), "same map-only sites")
    evaluation, preparation = build_v4(
        survey, sha256_file(SURVEY), expected, sha256_file(TEMPLATE)
    )
    for plan in (evaluation, preparation):
        plan.update(
            schema="m10-road-preparation-plan-v8"
            if plan["phase"] == "preparation"
            else "m10-road-plan-v8",
            created_date="2026-11-10",
            placement_revision="v8b-person-occluder20cm",
            site_selection="Same fixed Town04 first eligible sites7/25; no image/model ranking",
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

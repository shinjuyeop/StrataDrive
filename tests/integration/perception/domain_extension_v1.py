"""Append-only model-free person occlusion variants; original1020 cases unchanged."""

from copy import deepcopy
from domain_plan_v1 import build, validate_plan as validate_base
from quality_geometry_v4 import camera_projection, road_pose
from quality_benchmark import require


def build_extension():
    base = build()
    plan = deepcopy(base)
    plan["extension"] = "person-occlusion-lateral-v1"
    plan["collection_revision"] = (
        "Append .6m/.85m person occlusion and exact unoccluded references; all original cases retained"
    )
    for run, part in plan["partitions"].items():
        source = base["partitions"][run]
        cases = []
        for original in source["cases"]:
            if original["stratum"] != "occluded" or original["target_class"] != 0:
                continue
            for right in (0.6, 0.85):
                case = deepcopy(original)
                case["id"] = f"domain-ext-v1-{run}-{len(cases):03d}"
                case["variant_group"] = f"domain-ext-v1-{run}-{original['weather']}"
                a = case["actors"][0]
                a["right_m"] = right
                a["pose"] = road_pose(
                    a["road_node"], right, a["clearance_m"], a["yaw_offset_degrees"]
                )
                a["camera_projection"] = camera_projection(
                    case["camera_pose"], a["pose"]
                )
                cases.append(case)
                reference = deepcopy(case)
                reference["id"] = f"domain-ext-v1-{run}-{len(cases):03d}"
                reference["stratum"] = "occluded_reference"
                reference["reference_for"] = case["id"]
                reference["actors"] = reference["actors"][:1]
                cases.append(reference)
        part["cases"] = cases
    validate_plan(plan)
    return plan


def validate_plan(plan):
    if "extension" not in plan:
        return validate_base(plan)
    require(
        plan["extension"] == "person-occlusion-lateral-v1"
        and plan["schema"] == "m10-domain-data-plan-v1"
        and plan["phase"] == "development-data",
        "known extension schema",
    )
    base = build()
    require(
        set(plan["partitions"]) == set(base["partitions"]), "extension split/site set"
    )
    for run, part in plan["partitions"].items():
        require(
            part["spawn_point_index"] == base["partitions"][run]["spawn_point_index"]
            and part["split"] == base["partitions"][run]["split"]
            and len(part["cases"]) == 12,
            "extension denominator/site",
        )
        ids = {c["id"]: c for c in part["cases"]}
        require(len(ids) == 12, "unique extension scenes")
        for c in part["cases"]:
            require(
                c["target_class"] == 0
                and c["stratum"] in ("occluded", "occluded_reference")
                and c["actors"][0]["right_m"] in (0.6, 0.85),
                "person lateral extension only",
            )
            for a in c["actors"]:
                require(
                    a["pose"]
                    == road_pose(
                        a["road_node"],
                        a["right_m"],
                        a["clearance_m"],
                        a["yaw_offset_degrees"],
                    )
                    and camera_projection(c["camera_pose"], a["pose"])
                    == a["camera_projection"]
                    and a["camera_projection"]["in_frame"],
                    "extension pose/frustum",
                )
            if "reference_for" in c:
                original = ids[c["reference_for"]]
                require(
                    c["camera_pose"] == original["camera_pose"]
                    and c["actors"][0] == original["actors"][0]
                    and len(c["actors"]) == 1,
                    "exact unoccluded reference",
                )
    return plan

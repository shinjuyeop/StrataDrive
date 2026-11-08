"""V3 experiment identity; preparation must pass before final experiment freeze."""

from datetime import datetime, timezone
from pathlib import Path
import math
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import read_json
from physical_ai.perception.quality_candidates_v3 import (
    CANDIDATES,
    MODELS,
    INPUT_PROFILE,
)
from quality_benchmark import require, write_new

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / "profiles/perception-quality-plan-v3.json"
PREPARATION_PLAN = ROOT / "profiles/perception-quality-preparation-v3.json"
PROTOCOL = ROOT / "profiles/perception-quality-protocol-v3.json"
EXCLUSION = ROOT / "profiles/perception-quality-exclusion-v3.json"
DENIED = {"vehicle.carlamotors.european_hgv"}


def validate_plan(plan):
    seen = set()
    for part, value in plan["partitions"].items():
        require(part in ("preparation", "development", "holdout"), "unknown partition")
        for c in value["cases"]:
            require(c["id"] not in seen, "duplicate case")
            seen.add(c["id"])
            for a in c["actors"]:
                require(a["blueprint"] not in DENIED, "incompatible NW asset")
                require(
                    all(
                        type(a[k]) in (int, float) and math.isfinite(a[k])
                        for k in (
                            "forward_m",
                            "right_m",
                            "z_offset_m",
                            "yaw_offset_degrees",
                        )
                    ),
                    "finite planned pose",
                )
    require(bool(seen), "empty plan")


def validate_descriptors():
    p, plan, prep = read_json(PROTOCOL), read_json(PLAN), read_json(PREPARATION_PLAN)
    validate_plan(plan)
    validate_plan(prep)
    require(
        p["schema"] == "m10-quality-protocol-v3"
        and p["candidate_ids"] == list(CANDIDATES[1:])
        and p["input_profile"] == INPUT_PROFILE
        and {c: p["models"][c]["sha256"] for c in CANDIDATES} == MODELS
        and p["models"]["baseline"]["bytes"] == 35858002
        and all(p["models"][c]["bytes"] == 101259744 for c in CANDIDATES[1:]),
        "v3 model descriptor",
    )
    old = read_json(ROOT / "profiles/perception-quality-protocol-v2.json")
    require(
        all(
            p[k] == old[k]
            for k in (
                "absolute_quality",
                "relative_promotion",
                "selection_order",
                "annotation",
                "coverage",
                "center_refine",
                "score_threshold",
                "minimum_visible_pixels",
                "minimum_box_side",
            )
        ),
        "v3 retains strict annotation and numeric gates",
    )
    require(
        p["preparation"]
        == dict(
            required_status="PASS",
            minimum_target_visible_pixels=25,
            minimum_target_box_side=4,
            all_planned_actors_included=True,
            denied_blueprints=sorted(DENIED),
            before_final_freeze=True,
            no_model_inference=True,
            occluded_visible_ratio_max=0.95,
            unoccluded_reference_cases=36,
        ),
        "preparation descriptor",
    )
    require(
        plan["schema"] == "m10-quality-plan-v3"
        and set(plan["partitions"]) == {"development", "holdout"}
        and all(len(v["cases"]) == 81 for v in plan["partitions"].values())
        and prep["schema"] == "m10-quality-preparation-plan-v3"
        and set(prep["partitions"]) == {"preparation"},
        "v3 plan denominator",
    )


def check_preparation(path):
    report = read_json(path)
    require(
        report["schema"] == "m10-quality-preparation-v3"
        and report["status"] == "PASS"
        and report["plan_sha256"] == sha256_file(PREPARATION_PLAN)
        and report["inference_performed"] is False
        and report["frames"]
        == len(read_json(PREPARATION_PLAN)["partitions"]["preparation"]["cases"])
        and report["missing_actors"] == 0,
        "preparation required",
    )
    require(
        report["occlusion_failures"] == 0,
        "preparation required",
    )
    prepared = report["planned_targets"]
    for part in read_json(PLAN)["partitions"].values():
        for c in part["cases"]:
            if c["stratum"] not in ("near", "medium", "far", "occluded"):
                continue
            for a in c["actors"]:
                if a["role"] != "target":
                    continue
                require(
                    any(
                        p["weather"] == c["weather"]
                        and p["stratum"] == c["stratum"]
                        and all(
                            p["actor"][k] == a[k]
                            for k in (
                                "class_id",
                                "blueprint",
                                "yaw_offset_degrees",
                                "right_m",
                            )
                        )
                        and p["actor"]["forward_m"] >= a["forward_m"]
                        for p in prepared
                    ),
                    "evaluation target not covered by preparation",
                )
    exclusion = set(read_json(EXCLUSION)["rgb_sha256"])
    require(
        set(report["rgb_sha256"]) <= exclusion, "preparation images must be excluded"
    )
    return report


def freeze(path):
    validate_descriptors()
    prep_path = path.parent / "preparation-acceptance.json"
    report = check_preparation(prep_path)
    model_check = check_model_report(path.parent / "model-check.json")
    require(
        model_check["dataset_sha256"] == report["rgb_manifest_sha256"],
        "numeric check preparation binding",
    )
    files = set((ROOT / "physical_ai/perception").glob("*.py"))
    files.update((ROOT / "tests/integration/perception").glob("*quality*.py"))
    files.update(
        ROOT / "tests/integration/perception" / name
        for name in ("evaluate.py", "prepare_dataset.py", "run_capture_v3.py")
    )
    files.update((ROOT / "third_party/megvii-yolox").glob("*"))
    files.add(ROOT / "docs/test-plan/perception-quality-v3-protocol.md")
    files.update(
        (
            PLAN,
            PREPARATION_PLAN,
            PROTOCOL,
            EXCLUSION,
            ROOT / "profiles/perception-quality-protocol-v2.json",
        )
    )
    result = dict(
        schema="m10-quality-freeze-v3",
        created_utc=datetime.now(timezone.utc).isoformat(),
        models=MODELS,
        plan_sha256=sha256_file(PLAN),
        protocol_sha256=sha256_file(PROTOCOL),
        preparation_sha256=sha256_file(prep_path),
        model_check_sha256=sha256_file(path.parent / "model-check.json"),
        preparation_completed_utc=report["completed_utc"],
        preparation_plan_sha256=sha256_file(PREPARATION_PLAN),
        exclusion_sha256=sha256_file(EXCLUSION),
        sources={str(p.relative_to(ROOT)): sha256_file(p) for p in sorted(files)},
    )
    write_new(path, result)
    return result


def check_freeze(path):
    f = read_json(path)
    require(
        f["schema"] == "m10-quality-freeze-v3"
        and f["models"] == MODELS
        and f["plan_sha256"] == sha256_file(PLAN)
        and f["protocol_sha256"] == sha256_file(PROTOCOL)
        and f["preparation_plan_sha256"] == sha256_file(PREPARATION_PLAN)
        and f["exclusion_sha256"] == sha256_file(EXCLUSION)
        and f["preparation_sha256"]
        == sha256_file(path.parent / "preparation-acceptance.json")
        and f["model_check_sha256"] == sha256_file(path.parent / "model-check.json"),
        "v3 freeze identity",
    )
    check_preparation(path.parent / "preparation-acceptance.json")
    check_model_report(path.parent / "model-check.json")
    for name, digest in f["sources"].items():
        require(sha256_file(ROOT / name) == digest, f"v3 frozen source changed: {name}")
    return f


def check_model_report(path):
    report = read_json(path)
    require(
        report["schema"] == "m10-model-check-v3"
        and report["status"] == "PASS"
        and report["model_sha256"] == MODELS["medium-v3"]
        and report["input_profile"] == INPUT_PROFILE
        and report["atol"] == 1e-3
        and report["rtol"] == 1e-4
        and report["cpu_node_fallback_disabled"] is True
        and report["cuda_providers"][0] == "CUDAExecutionProvider"
        and report["cold_calls_excluded"] == 0
        and len(report["rows"]) == 3
        and all(
            r["equal_tensor"] is True
            and all(c["equal"] is True for c in r["comparisons"].values())
            for r in report["rows"]
        ),
        "model numeric check required",
    )
    return report

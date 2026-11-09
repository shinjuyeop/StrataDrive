"""Prospective road-site quality identity; preparation evidence stays immutable."""

from datetime import datetime, timezone
from pathlib import Path
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
from quality_plan_v4 import validate_plan
from quality_v3_common import check_model_report

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / "profiles/perception-road-evaluation-v4.json"
PROTOCOL = ROOT / "profiles/perception-quality-protocol-v4.json"
EXCLUSION = ROOT / "profiles/perception-quality-exclusion-v4.json"
PREPARATION = ROOT / "docs/test-plan/evidence/m10_road_preparation_v4"


def validate_descriptors():
    plan, protocol = read_json(PLAN), read_json(PROTOCOL)
    validate_plan(plan)
    old = read_json(ROOT / "profiles/perception-quality-protocol-v3.json")
    require(
        plan["phase"] == "evaluation"
        and protocol["schema"] == "m10-quality-protocol-v4"
        and all(
            protocol[k] == old[k]
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
                "candidate_ids",
                "models",
                "input_profile",
            )
        )
        and protocol["candidate_ids"] == list(CANDIDATES[1:])
        and protocol["input_profile"] == INPUT_PROFILE
        and {c: protocol["models"][c]["sha256"] for c in CANDIDATES} == MODELS
        and protocol["actual_site_visibility"]
        == dict(all_planned_actors_included=True, all_two_wheeler_riders_included=True)
        and protocol["held_person_far_m"] == 26,
        "v4 preserves pinned models, strict gates and road scope",
    )
    seal = read_json(PREPARATION / "prepared-plan-seal.json")
    require(
        seal["preparation_status"] == "PASS"
        and seal["evaluation_plan_sha256"] == sha256_file(PLAN)
        and seal["preparation_freeze_sha256"]
        == sha256_file(PREPARATION / "preparation-freeze.json")
        and seal["survey_sha256"] == sha256_file(PREPARATION / "survey-selected.json")
        and seal["future_exclusion_sha256"]
        == sha256_file(PREPARATION / "future-evaluation-exclusion.json")
        and seal["future_quality_freeze_required"] is True
        and seal["quality_evaluation"] == "NOT_RUN"
        and seal["inference_performed"] is False
        and seal["runtime_promotion"] is False,
        "prepared road plan seal",
    )
    exclusion = read_json(EXCLUSION)
    prior = set(exclusion["rgb_sha256"])
    baseline = set(
        read_json(PREPARATION / "future-evaluation-exclusion.json")["rgb_sha256"]
    )
    additional = {h for c in exclusion["additional_captures"] for h in c["rgb_sha256"]}
    require(
        len(baseline) == 1387
        and len(additional) == 324
        and not baseline & additional
        and prior == baseline | additional
        and len(prior) == protocol["prior_rgb_excluded"] == 1711
        and protocol["metadata_revision"] == "v4b",
        "all historical, rejected, diagnostic and metadata-aborted RGB excluded",
    )
    for part in ("development", "holdout"):
        path = PREPARATION / f"{part}-preparation.json"
        report = read_json(path)
        require(
            seal["preparation_reports"][part] == sha256_file(path)
            and report["status"] == "PASS"
            and report["frames"] == 99
            and all(report["gates"].values())
            and report["inference_performed"] is False
            and set(report["rgb_sha256"]) <= prior,
            "both actual-site preparation reports required",
        )
    # Additions are allowed; bytes used by the completed preparation remain fixed.
    for name, digest in read_json(PREPARATION / "preparation-freeze.json")[
        "sources"
    ].items():
        require(sha256_file(ROOT / name) == digest, "preparation source drift")
    return seal


def preparation_bindings():
    return {
        name: sha256_file(PREPARATION / name)
        for name in (
            "prepared-plan-seal.json",
            "preparation-freeze.json",
            "development-preparation.json",
            "holdout-preparation.json",
            "preparation-audit.json",
            "archive-recheck.json",
        )
    }


def check_numeric(path):
    report = check_model_report(path)
    require(
        report["dataset_sha256"]
        == read_json(PREPARATION / "development-preparation.json")[
            "rgb_manifest_sha256"
        ],
        "numeric check uses separate preparation RGB",
    )
    return report


def freeze(path):
    validate_descriptors()
    numeric = path.parent / "model-check.json"
    check_numeric(numeric)
    files = set((ROOT / "physical_ai/perception").glob("*.py"))
    files.update((ROOT / "tests/integration/perception").glob("*.py"))
    files.update(
        (
            PLAN,
            PROTOCOL,
            EXCLUSION,
            ROOT / "profiles/perception-road-preparation-v4.json",
            ROOT / "profiles/perception-road-protocol-v4.json",
            ROOT / "profiles/perception-quality-protocol-v3.json",
            ROOT / "docs/test-plan/perception-quality-v4-protocol.md",
        )
    )
    result = dict(
        schema="m10-quality-freeze-v4",
        created_utc=datetime.now(timezone.utc).isoformat(),
        models=MODELS,
        plan_sha256=sha256_file(PLAN),
        protocol_sha256=sha256_file(PROTOCOL),
        exclusion_sha256=sha256_file(EXCLUSION),
        preparation=preparation_bindings(),
        model_check_sha256=sha256_file(numeric),
        sources={str(p.relative_to(ROOT)): sha256_file(p) for p in sorted(files)},
    )
    write_new(path, result)
    return result


def check_freeze(path):
    frozen = read_json(path)
    validate_descriptors()
    require(
        frozen["schema"] == "m10-quality-freeze-v4"
        and frozen["models"] == MODELS
        and frozen["plan_sha256"] == sha256_file(PLAN)
        and frozen["protocol_sha256"] == sha256_file(PROTOCOL)
        and frozen["exclusion_sha256"] == sha256_file(EXCLUSION)
        and frozen["preparation"] == preparation_bindings()
        and frozen["model_check_sha256"]
        == sha256_file(path.parent / "model-check.json"),
        "v4 freeze identity",
    )
    check_numeric(path.parent / "model-check.json")
    for name, digest in frozen["sources"].items():
        require(sha256_file(ROOT / name) == digest, f"v4 frozen source changed: {name}")
    return frozen


def check_selection(path, frozen_path):
    check_freeze(frozen_path)
    selection = read_json(path)
    require(
        selection["schema"] == "m10-quality-selection-v4"
        and selection["freeze_sha256"] == sha256_file(frozen_path)
        and selection["selected"] in CANDIDATES[1:]
        and selection["runtime_promotion"] is False
        and datetime.fromisoformat(selection["created_utc"])
        > datetime.fromisoformat(read_json(frozen_path)["created_utc"]),
        "prospective v4 nomination",
    )
    # Resolve by basename so an extracted archive never needs the original build path.
    import tempfile
    from audit_quality_experiment import compare_selection
    from quality_benchmark_v4 import score, nominate

    score_root = path.parent
    expected = [f"development-{c}-score.json" for c in CANDIDATES]
    if not all((score_root / name).is_file() for name in expected):
        score_root = score_root.parent
    require(
        {Path(p).name for p in selection["score_files"]} == set(expected),
        "nomination score set",
    )
    for name, digest in selection["score_files"].items():
        require(
            sha256_file(score_root / Path(name).name) == digest,
            "nomination score bytes",
        )
    for candidate in CANDIDATES:
        require(
            score(
                score_root / "development-data",
                score_root / f"development-{candidate}/result.json",
                frozen_path,
            )
            == read_json(score_root / f"development-{candidate}-score.json"),
            "nomination recomputed development score",
        )
    with tempfile.TemporaryDirectory() as temporary:
        recomputed = nominate(
            [score_root / name for name in expected],
            frozen_path,
            Path(temporary) / "selection.json",
        )
        compare_selection(selection, recomputed)
    return selection

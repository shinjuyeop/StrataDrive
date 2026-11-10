"""Prospective V9 source, model-free preparation and fixed-model identities."""

from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import read_json, local_path
from physical_ai.perception.quality_candidates_v9 import (
    CANDIDATES,
    MODELS,
    MODEL_BYTES,
    INPUT_PROFILE,
    POLICY,
    validate_policy,
)
from quality_benchmark import require, write_new
from quality_road_v9 import SURVEY, USED, build, select_fresh, validate_plan
from quality_staging_v5 import STAGING

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / "profiles/perception-road-evaluation-v9.json"
PREPARATION_PLAN = ROOT / "profiles/perception-road-preparation-v9.json"
PROTOCOL = ROOT / "profiles/perception-quality-protocol-v9.json"
BASE_EXCLUSION = ROOT / "profiles/perception-quality-exclusion-v9.json"
EXCLUSION = ROOT / "profiles/perception-quality-evaluation-exclusion-v9.json"


def validate_descriptors():
    validate_policy()
    p, original = (
        read_json(PROTOCOL),
        read_json(ROOT / "profiles/perception-quality-protocol-v4.json"),
    )
    require(
        p["schema"] == "m10-quality-protocol-v9"
        and p["road_plan"] == PLAN.name
        and p["metadata_revision"] == "v9"
        and p["policy"] == POLICY
        and p["staging"] == STAGING
        and p["candidate_ids"] == list(CANDIDATES[1:])
        and p["input_profile"] == INPUT_PROFILE
        and {c: p["models"][c]["sha256"] for c in CANDIDATES} == MODELS
        and {c: p["models"][c]["bytes"] for c in CANDIDATES} == MODEL_BYTES
        and p["preparation"]["sites"] == select_fresh(read_json(SURVEY)),
        "V9 fixed candidate/native policy",
    )
    for key in (
        "absolute_quality",
        "relative_promotion",
        "selection_order",
        "annotation",
        "coverage",
        "score_threshold",
        "minimum_visible_pixels",
        "minimum_box_side",
        "actual_site_visibility",
    ):
        require(p[key] == original[key], "unchanged full fresh-quality gate: " + key)
    old_survey = ROOT / "docs/test-plan/evidence/m10_quality_v8/survey-selected.json"
    used, survey_data = read_json(USED), read_json(old_survey)
    prior_sites = [
        site
        for site in survey_data["sites"]
        if site["spawn_point_index"] in used["used_spawn_indices"]
    ]
    require(
        used["previous_survey_sha256"] == sha256_file(old_survey)
        and used["used_spawn_indices"] == [7, 25]
        and used["route_road_ids"]
        == sorted(
            {node["road_id"] for site in prior_sites for node in site["nodes"].values()}
        )
        and used["route_origins"]
        == [site["nodes"]["0"]["pose"]["location"] for site in prior_sites],
        "previous used map geometry replay",
    )
    evaluation, preparation = build()
    require(
        read_json(PLAN) == evaluation and read_json(PREPARATION_PLAN) == preparation,
        "V9 map-to-plan replay",
    )
    validate_plan(evaluation)
    validate_plan(preparation)
    prior = (
        ROOT / "docs/test-plan/evidence/m10_quality_v8/future-evaluation-exclusion.json"
    )
    require(
        sha256_file(prior) == sha256_file(BASE_EXCLUSION)
        and len(set(read_json(BASE_EXCLUSION)["rgb_sha256"])) == 4990,
        "all previously consumed RGB excluded",
    )
    require(
        len(set(read_json(EXCLUSION)["rgb_sha256"])) == p["prior_rgb_excluded"],
        "V9 evaluation exclusion count",
    )


def check_sources(frozen, snapshot):
    for name, digest in frozen["sources"].items():
        require(
            sha256_file(ROOT / name) == sha256_file(snapshot / name) == digest,
            "frozen source drift: " + name,
        )


def check_preparation(base):
    survey_freeze = read_json(base / "survey-freeze.json")
    survey_runs = read_json(base / "survey-runs.json")
    accepted = base / survey_runs["accepted"]
    server = read_json(accepted / "server.json")
    require(
        survey_freeze["schema"] == "m10-map-survey-freeze-v9"
        and survey_freeze["rgb_captured"] is False
        and survey_freeze["inference_performed"] is False
        and server["schema"] == "m10-road-server-v9"
        and server["stage"] == "survey"
        and server["status"] == "PASS"
        and server["capture_exit"] == 0
        and server["server_exit"] == 130
        and not server.get("forced_stop")
        and sha256_file(accepted / "dataset/survey.json") == sha256_file(SURVEY)
        and server["used_roads_sha256"] == sha256_file(USED),
        "accepted fresh map-only survey",
    )
    check_sources(survey_freeze, base / "survey-source")
    require(
        server["probe_sha256"]
        == survey_freeze["sources"][
            "tests/integration/perception/carla_quality_layout_v9.py"
        ]
        and server["site_helper_sha256"]
        == survey_freeze["sources"]["tests/integration/perception/quality_sites_v9.py"],
        "survey executable/helper identity",
    )
    visual = read_json(base / "preparation-visual-review.json")
    require(
        visual["status"] == "PASS"
        and visual["model_inference_performed"] is False
        and (base / "preparation-reviewed.flag").exists(),
        "GT-only preparation visual review",
    )
    binding = {}

    def bind(path):
        binding[str(path.relative_to(base))] = sha256_file(path)

    for filename in (
        "survey-freeze.json",
        "survey-runs.json",
        "preparation-visual-review.json",
        "preparation-reviewed.flag",
    ):
        bind(base / filename)
    for name in survey_runs["attempts"]:
        run = base / name
        bind(run / "server.json")
        if (run / "dataset/survey.json").exists():
            bind(run / "dataset/survey.json")
        require(not list((run / "dataset").glob("rgb/*")), "survey cannot supply RGB")
    if survey_runs.get("recovery"):
        recovery_path = base / survey_runs["recovery"]
        recovery = read_json(recovery_path)
        failed = base / "survey-01/server.json"
        require(
            recovery["annex_sha256"]
            == sha256_file(
                ROOT / "docs/test-plan/perception-quality-v9-survey-recovery.md"
            )
            and recovery["source_freeze_sha256"]
            == sha256_file(base / "survey-freeze.json")
            and recovery["original_server_sha256"] == sha256_file(failed)
            and recovery["additional_attempts"] == 1
            and recovery["limits"] == [180, 900, 30]
            and recovery["source_policy_changes"] is False
            and read_json(failed)["status"] == "FAIL"
            and datetime.fromisoformat(recovery["created_utc"])
            < datetime.fromisoformat(server["started_utc"]),
            "separate bounded survey recovery",
        )
        bind(recovery_path)
    preparation_freeze = read_json(base / "preparation-freeze.json")
    require(
        preparation_freeze["schema"] == "m10-road-preparation-freeze-v9"
        and preparation_freeze["model_inference_performed"] is False
        and preparation_freeze["plan_sha256"] == sha256_file(PREPARATION_PLAN)
        and preparation_freeze["survey_sha256"] == sha256_file(SURVEY),
        "model-free preparation freeze",
    )
    check_sources(preparation_freeze, base / "preparation-source")
    ledger = read_json(base / "preparation-attempts.json")
    runs = read_json(base / "preparation-runs.json")
    require(
        ledger["model_inference_performed"] is False
        and set(runs) == {"development", "holdout"},
        "all preparation attempts retained",
    )
    prior = set(read_json(BASE_EXCLUSION)["rgb_sha256"])
    all_preparation = set()
    for entry in ledger["attempts"]:
        run = base / entry["run"]
        bind(run / "server.json")
        capture_path = run / "dataset/capture.json"
        if not capture_path.exists():
            continue
        bind(capture_path)
        capture = read_json(capture_path)
        require(
            capture["partition"] == entry["partition"]
            and capture["phase"] == "preparation",
            "preparation attempt lineage",
        )
        for pair in capture["frames"]:
            import hashlib
            import numpy as np

            data = local_path(capture_path.parent, pair["rgb"]["path"])
            require(
                sha256_file(data) == pair["rgb"]["sha256"],
                "all preparation raw RGB hashes",
            )
            rgb = (
                np.frombuffer(data.read_bytes(), np.uint8)
                .reshape(384, 640, 4)[:, :, 2::-1]
                .copy()
                .tobytes()
            )
            all_preparation.add(hashlib.sha256(rgb).hexdigest())
        if entry.get("data"):
            for filename in (
                "acceptance.json",
                "rgb.json",
                "evaluation-only-gt.json",
                "preparation-data.json",
            ):
                bind(base / entry["data"] / filename)
    recovery_path = base / "preparation-recovery-before-launch.json"
    if recovery_path.exists():
        recovery = read_json(recovery_path)
        failed = base / "preparation-holdout-01"
        recovered = base / "preparation-holdout-02"
        require(
            recovery["annex_sha256"]
            == sha256_file(
                ROOT / "docs/test-plan/perception-quality-v9-preparation-recovery.md"
            )
            and recovery["source_freeze_sha256"]
            == sha256_file(base / "preparation-freeze.json")
            and recovery["original_server_sha256"]
            == sha256_file(failed / "server.json")
            and recovery["original_capture_sha256"]
            == sha256_file(failed / "dataset/capture.json")
            and recovery["additional_attempts"] == 1
            and recovery["limits"] == [180, 900, 30]
            and recovery["source_plan_gate_model_changes"] is False
            and recovery["model_inference_performed"] is False
            and runs["holdout"] == recovered.name
            and read_json(failed / "server.json")["status"] == "FAIL"
            and datetime.fromisoformat(recovery["created_utc"])
            < datetime.fromisoformat(
                read_json(recovered / "server.json")["started_utc"]
            ),
            "bounded held preparation recovery retains original failure",
        )
        bind(recovery_path)
    require(
        set(read_json(EXCLUSION)["rgb_sha256"]) == prior | all_preparation,
        "exclude every preparation attempt before evaluation",
    )
    seen = set()
    for part in ("development", "holdout"):
        run = base / runs[part]
        server = read_json(run / "server.json")
        data = base / f"preparation-{part}-data"
        accepted = read_json(data / "acceptance.json")
        require(
            accepted["schema"] == "m10-road-preparation-acceptance-v9"
            and accepted["status"] == "PASS"
            and all(accepted["gates"].values())
            and accepted["frames"] == 99
            and accepted["inference_performed"] is False
            and accepted["plan_sha256"] == sha256_file(PREPARATION_PLAN)
            and accepted["capture_sha256"] == sha256_file(run / "dataset/capture.json")
            and server["status"] == "PASS"
            and server["server_exit"] == 130
            and server["capture_exit"] == 0
            and not server.get("forced_stop")
            and server["probe_sha256"]
            == preparation_freeze["sources"][
                "tests/integration/perception/carla_road_preparation_v9.py"
            ]
            and datetime.fromisoformat(preparation_freeze["created_utc"])
            < datetime.fromisoformat(server["started_utc"]),
            "complete accepted actual-site preparation",
        )
        hashes = set(accepted["rgb_sha256"])
        require(
            len(hashes) == 99 and not hashes.intersection(prior | seen),
            "separate accepted preparation RGB",
        )
        seen.update(hashes)
        for filename in (
            "acceptance.json",
            "rgb.json",
            "evaluation-only-gt.json",
            "preparation-data.json",
        ):
            bind(data / filename)
    for filename in (
        "preparation-freeze.json",
        "preparation-attempts.json",
        "preparation-runs.json",
    ):
        bind(base / filename)
    failed_audit = base / "failed-preparation-raw-audit.json"
    if failed_audit.exists():
        diagnostic = read_json(failed_audit)
        require(
            diagnostic["accepted"] is False
            and diagnostic["server_status"] == "FAIL"
            and diagnostic["frames"] == 99
            and diagnostic["capture_sha256"]
            == sha256_file(base / "preparation-holdout-01/dataset/capture.json")
            and diagnostic["helper_sha256"]
            == sha256_file(
                ROOT / "tests/integration/perception/audit_failed_preparation_v9.py"
            ),
            "failed raw diagnostic never supplies accepted preparation",
        )
        bind(failed_audit)
    return binding


def check_numeric(path):
    report = read_json(path)
    require(
        report["schema"] == "m10-model-check-v9"
        and report["status"] == "PASS"
        and report["models"] == MODELS
        and report["dataset_sha256"]
        == sha256_file(path.parent / "preparation-development-data/rgb.json")
        and report["baseline_raw_atol"] == 0.001
        and report["baseline_raw_rtol"] == 0.0001
        and report["baseline_box_atol"] == 0.01
        and report["dfine_box_atol"] == 0.1
        and report["score_atol"] == 0.0001
        and report["cpu_node_fallback_disabled"] is True
        and report["cold_calls_excluded"] == 0
        and len(report["rows"]) == 6
        and all(row["passed"] for row in report["rows"]),
        "V9 native numeric contract",
    )
    require(
        {(row["candidate"], row["probe"]) for row in report["rows"]}
        == {(c, n) for c in CANDIDATES for n in range(3)},
        "V9 numeric candidate and probe denominator",
    )
    frames = read_json(path.parent / "preparation-development-data/rgb.json")["frames"]
    require(
        all(
            row["rgb_sha256"] == frames[row["probe"]]["rgb_sha256"]
            and row["providers"][0] == "CUDAExecutionProvider"
            for row in report["rows"]
        ),
        "V9 numeric fresh probe identity and CUDA provider",
    )
    return report


def freeze(path):
    validate_descriptors()
    binding = check_preparation(path.parent)
    check_numeric(path.parent / "model-check.json")
    files = (
        set((ROOT / "physical_ai/perception").glob("*.py"))
        | set((ROOT / "tests/integration/perception").glob("*.py"))
        | set((ROOT / "profiles").glob("perception-*.json"))
    )
    files.update(
        ROOT / name
        for name in read_json(path.parent / "preparation-freeze.json")["sources"]
    )
    files.update((ROOT / "third_party/pretrained-screen-v2").rglob("*"))
    files.update(
        [
            SURVEY,
            ROOT / "docs/test-plan/perception-quality-v9-protocol.md",
            ROOT / "docs/test-plan/perception-quality-v9-survey-recovery.md",
            ROOT / "docs/test-plan/perception-quality-v9-preparation-recovery.md",
        ]
    )
    result = dict(
        schema="m10-quality-freeze-v9",
        created_utc=datetime.now(timezone.utc).isoformat(),
        models=MODELS,
        plan_sha256=sha256_file(PLAN),
        protocol_sha256=sha256_file(PROTOCOL),
        exclusion_sha256=sha256_file(EXCLUSION),
        preparation=binding,
        model_check_sha256=sha256_file(path.parent / "model-check.json"),
        sources={
            str(p.relative_to(ROOT)): sha256_file(p)
            for p in sorted(files)
            if p.is_file() and "__pycache__" not in p.parts
        },
    )
    write_new(path, result)
    return result


def check_freeze(path):
    f = read_json(path)
    validate_descriptors()
    require(
        f["schema"] == "m10-quality-freeze-v9"
        and f["models"] == MODELS
        and f["plan_sha256"] == sha256_file(PLAN)
        and f["protocol_sha256"] == sha256_file(PROTOCOL)
        and f["exclusion_sha256"] == sha256_file(EXCLUSION)
        and f["preparation"] == check_preparation(path.parent)
        and f["model_check_sha256"] == sha256_file(path.parent / "model-check.json"),
        "V9 complete freeze identity",
    )
    check_numeric(path.parent / "model-check.json")
    for name, digest in f["sources"].items():
        require(sha256_file(ROOT / name) == digest, "V9 frozen source changed: " + name)
    return f


def check_selection(path, frozen_path):
    check_freeze(frozen_path)
    selected = read_json(path)
    require(
        selected["schema"] == "m10-quality-selection-v9"
        and selected["freeze_sha256"] == sha256_file(frozen_path)
        and selected["selected"] in CANDIDATES[1:]
        and selected["runtime_promotion"] is False
        and datetime.fromisoformat(selected["created_utc"])
        > datetime.fromisoformat(read_json(frozen_path)["created_utc"]),
        "V9 sealed pre-holdout nomination",
    )
    from audit_quality_experiment import compare_selection
    from quality_benchmark_v9 import score, nominate
    import tempfile

    root = path.parent
    names = [f"development-{c}-score.json" for c in CANDIDATES]
    if not all((root / name).exists() for name in names):
        root = root.parent
    require(
        {Path(name).name for name in selected["score_files"]} == set(names),
        "nomination development score set",
    )
    for name, digest in selected["score_files"].items():
        require(sha256_file(root / Path(name).name) == digest, "nomination score bytes")
    for candidate in CANDIDATES:
        require(
            score(
                root / "development-data",
                root / f"development-{candidate}/result.json",
                frozen_path,
            )
            == read_json(root / f"development-{candidate}-score.json"),
            "nomination recomputed primary score",
        )
    with tempfile.TemporaryDirectory() as temporary:
        recomputed = nominate(
            [root / name for name in names],
            frozen_path,
            Path(temporary) / "selection.json",
        )
        compare_selection(selected, recomputed)
    return selected

"""Prospective V8 identity: new sites, prepared visibility, fixed RGB-only policy."""

from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import read_json
from physical_ai.perception.quality_candidates_v8 import (
    CANDIDATES,
    MODELS,
    INPUT_PROFILE,
    POLICY,
)
from quality_benchmark import require, write_new
from quality_road_v8b import validate_plan, build, SURVEY, select_fresh
from quality_staging_v5 import STAGING

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / "profiles/perception-road-evaluation-v8b.json"
PREPARATION_PLAN = ROOT / "profiles/perception-road-preparation-v8b.json"
PROTOCOL = ROOT / "profiles/perception-quality-protocol-v8.json"
BASE_EXCLUSION = ROOT / "profiles/perception-quality-exclusion-v8.json"
EXCLUSION = ROOT / "profiles/perception-quality-evaluation-exclusion-v8.json"


def validate_descriptors():
    p = read_json(PROTOCOL)
    old = read_json(ROOT / "profiles/perception-quality-protocol-v4.json")
    require(
        p["schema"] == "m10-quality-protocol-v8"
        and p["road_plan"] == PLAN.name
        and p["metadata_revision"] == "v8"
        and p["policy"] == POLICY
        and p["staging"] == STAGING
        and p["candidate_ids"] == list(CANDIDATES[1:])
        and p["input_profile"] == INPUT_PROFILE
        and {c: p["models"][c]["sha256"] for c in CANDIDATES} == MODELS
        and all(
            p["models"][c]["bytes"] == (35858002 if c == "baseline" else 216746733)
            for c in CANDIDATES
        )
        and p["held_person_far_m"] == 26
        and p["preparation"]
        == dict(
            required_status="PASS",
            sites=select_fresh(read_json(SURVEY)),
            frames=198,
            all_planned_actors_included=True,
            all_two_wheeler_riders_included=True,
            before_final_freeze=True,
            no_model_inference=True,
        )
        and all(
            p[k] == old[k]
            for k in (
                "absolute_quality",
                "relative_promotion",
                "selection_order",
                "annotation",
                "coverage",
                "score_threshold",
                "minimum_visible_pixels",
                "minimum_box_side",
                "actual_site_visibility",
            )
        ),
        "v8 fixed policy/models and unchanged quality gates",
    )
    expected = build()
    require(
        read_json(PLAN) == expected[0] and read_json(PREPARATION_PLAN) == expected[1],
        "map-to-plan replay",
    )
    validate_plan(read_json(PLAN))
    validate_plan(read_json(PREPARATION_PLAN))
    previous = (
        ROOT / "docs/test-plan/evidence/m10_quality_v7/future-evaluation-exclusion.json"
    )
    require(
        sha256_file(BASE_EXCLUSION) == sha256_file(previous)
        and len(set(read_json(BASE_EXCLUSION)["rgb_sha256"])) == 4333,
        "all consumed V1-V6 and domain/training excluded",
    )
    exclusion = set(read_json(EXCLUSION)["rgb_sha256"])
    require(
        set(read_json(BASE_EXCLUSION)["rgb_sha256"]) <= exclusion
        and len(exclusion) == p["prior_rgb_excluded"],
        "evaluation exclusion descriptor",
    )


def check_preparation(base):
    runs = read_json(base / "preparation-runs.json")
    frozen = read_json(base / "preparation-freeze.json")
    require(
        frozen["schema"] == "m10-road-preparation-freeze-v8",
        "preparation source identity",
    )
    require(
        frozen["survey_sha256"] == sha256_file(SURVEY), "original map query identity"
    )
    survey_freeze = read_json(base / "survey-freeze.json")
    survey_run = base / "survey-01"
    survey_server = read_json(survey_run / "server.json")
    require(
        survey_freeze["schema"] == "m10-map-survey-freeze-v8"
        and survey_freeze["map"] == "Town04_Opt"
        and survey_freeze["inference_performed"] is False
        and survey_freeze["rgb_captured"] is False
        and survey_server["schema"] == "m10-road-server-v8"
        and survey_server["stage"] == "survey"
        and survey_server["status"] == "PASS"
        and survey_server["server_exit"] == 130
        and survey_server["capture_exit"] == 0
        and not survey_server.get("forced_stop")
        and sha256_file(survey_run / "dataset/survey.json") == sha256_file(SURVEY)
        and datetime.fromisoformat(survey_freeze["created_utc"])
        < datetime.fromisoformat(survey_server["started_utc"])
        < datetime.fromisoformat(frozen["created_utc"]),
        "new map-only survey before preparation",
    )
    for name, digest in survey_freeze["sources"].items():
        require(
            sha256_file(ROOT / name)
            == sha256_file(base / "survey-source" / name)
            == digest,
            "survey source drift",
        )
    require(
        survey_server["probe_sha256"]
        == sha256_file(survey_run / "capture-probe.py")
        == survey_freeze["sources"][
            "tests/integration/perception/carla_quality_layout_v8.py"
        ]
        and survey_server["helper_sha256"]
        == sha256_file(survey_run / "quality_geometry_v4.py")
        == survey_freeze["sources"][
            "tests/integration/perception/quality_geometry_v4.py"
        ]
        and "/Game/Carla/Maps/Town04_Opt" in survey_server["argv"],
        "survey probe identity",
    )
    for name, digest in frozen["sources"].items():
        require(
            sha256_file(ROOT / name)
            == sha256_file(base / "preparation-source" / name)
            == digest,
            "preparation source drift",
        )
    prior = set(read_json(BASE_EXCLUSION)["rgb_sha256"])
    exclusion = set(read_json(EXCLUSION)["rgb_sha256"])
    initial_audit = read_json(base / "initial-preparation-audit.json")
    revision = read_json(base / "preparation-revision-before-recapture.json")
    require(
        initial_audit["status"] == "PASS"
        and initial_audit["initial"]["development"]["status"] == "PASS"
        and initial_audit["initial"]["holdout"]["status"] == "FAIL"
        and initial_audit["helper_sha256"]
        == sha256_file(base / "audit-initial-preparation.py")
        and revision["model_inference_performed"] is False
        and revision["quality_freeze_created"] is False
        and revision["annex_sha256"]
        == sha256_file(
            ROOT / "docs/test-plan/perception-quality-v8-preparation-revision.md"
        ),
        "original model-free occlusion failure retained before revision",
    )
    for part in ("development", "holdout"):
        expected = initial_audit["initial"][part]
        require(
            expected["capture_sha256"]
            == sha256_file(base / f"preparation-{part}-01/dataset/capture.json")
            and expected["acceptance_sha256"]
            == sha256_file(base / f"initial-preparation-{part}-data/acceptance.json"),
            "initial preparation artifact identity",
        )
    recovery = read_json(base / "recovery-before-launch.json")
    failed_server = read_json(base / "preparation-holdout-02/server.json")
    require(
        recovery["annex_sha256"]
        == sha256_file(ROOT / "docs/test-plan/perception-quality-v8-recovery.md")
        and recovery["preparation_freeze_sha256"]
        == sha256_file(base / "preparation-freeze.json")
        and recovery["original_failed_server_sha256"]
        == sha256_file(base / "preparation-holdout-02/server.json")
        and recovery["original_capture_sha256"]
        == sha256_file(base / "preparation-holdout-02/dataset/capture.json")
        and recovery["limits"] == [180, 900, 30]
        and recovery["extra_holdout_preparation_attempts"] == 1
        and recovery["model_plan_gate_changes"] is False
        and failed_server["status"] == "FAIL"
        and failed_server["forced_stop"]
        and failed_server["server_exit"] == -9
        and runs["holdout"] == "preparation-holdout-03"
        and datetime.fromisoformat(recovery["created_utc"])
        < datetime.fromisoformat(
            read_json(base / runs["holdout"] / "server.json")["started_utc"]
        ),
        "bounded separate preparation recovery retains original shutdown failure",
    )
    seen = set()
    binding = {
        "recovery-before-launch.json": sha256_file(
            base / "recovery-before-launch.json"
        ),
        "preparation-holdout-02/server.json": sha256_file(
            base / "preparation-holdout-02/server.json"
        ),
        "preparation-holdout-02/dataset/capture.json": sha256_file(
            base / "preparation-holdout-02/dataset/capture.json"
        ),
        "initial-preparation-audit.json": sha256_file(
            base / "initial-preparation-audit.json"
        ),
        "preparation-revision-before-recapture.json": sha256_file(
            base / "preparation-revision-before-recapture.json"
        ),
        "survey-freeze.json": sha256_file(base / "survey-freeze.json"),
        "survey-01/server.json": sha256_file(survey_run / "server.json"),
        "survey-01/dataset/survey.json": sha256_file(
            survey_run / "dataset/survey.json"
        ),
        "preparation-freeze.json": sha256_file(base / "preparation-freeze.json"),
        "preparation-runs.json": sha256_file(base / "preparation-runs.json"),
    }
    for part in ("development", "holdout"):
        path = base / f"preparation-{part}-data/acceptance.json"
        r = read_json(path)
        run = base / runs[part]
        server = read_json(run / "server.json")
        require(
            r["schema"] == "m10-road-preparation-acceptance-v8"
            and r["status"] == "PASS"
            and all(r["gates"].values())
            and r["frames"] == 99
            and r["inference_performed"] is False
            and r["plan_sha256"] == sha256_file(PREPARATION_PLAN)
            and r["capture_sha256"] == sha256_file(run / "dataset/capture.json")
            and server["status"] == "PASS"
            and server["capture_exit"] == 0
            and server["server_exit"] == 130
            and not server.get("forced_stop")
            and server["probe_sha256"]
            == sha256_file(run / "capture-probe.py")
            == frozen["sources"][
                "tests/integration/perception/carla_road_preparation_v8.py"
            ]
            and server["helper_sha256"]
            == sha256_file(run / "quality_geometry_v4.py")
            == frozen["sources"]["tests/integration/perception/quality_geometry_v4.py"]
            and server["staging_sha256"]
            == sha256_file(run / "quality_staging_v5.py")
            == frozen["sources"]["tests/integration/perception/quality_staging_v5.py"],
            "actual preparation required",
        )
        hashes = set(r["rgb_sha256"])
        require(
            len(hashes) == 99 and not hashes & (prior | seen) and hashes <= exclusion,
            "separate preparation RGB",
        )
        seen.update(hashes)
        for name in (
            f"preparation-{part}-data/acceptance.json",
            f"preparation-{part}-data/rgb.json",
            f"preparation-{part}-data/evaluation-only-gt.json",
            f"preparation-{part}-data/preparation-data.json",
            f"{runs[part]}/server.json",
            f"{runs[part]}/dataset/capture.json",
        ):
            binding[name] = sha256_file(base / name)
    return binding


def check_numeric(path):
    report = read_json(path)
    require(
        report["schema"] == "m10-model-check-v8"
        and report["status"] == "PASS"
        and report["model_sha256"] == MODELS["large-v8"]
        and report["dataset_sha256"]
        == sha256_file(path.parent / "preparation-development-data/rgb.json")
        and report["atol"] == 0.001
        and report["rtol"] == 0.0001
        and report["box_atol"] == 0.01
        and report["score_atol"] == 0.0001
        and report["cpu_node_fallback_disabled"] is True
        and report["cold_calls_excluded"] == 0
        and len(report["rows"]) == 6
        and all(row["passed"] for row in report["rows"]),
        "v8 raw and complete numeric check",
    )
    require(
        all(
            sum(row["candidate"] == c for row in report["rows"]) == 3
            for c in CANDIDATES
        ),
        "numeric comparison candidate denominator",
    )
    return report


def freeze(path):
    validate_descriptors()
    prep = check_preparation(path.parent)
    check_numeric(path.parent / "model-check.json")
    files = set((ROOT / "physical_ai/perception").glob("*.py"))
    files.update((ROOT / "tests/integration/perception").glob("*.py"))
    files.update((ROOT / "profiles").glob("perception-*.json"))
    files.add(ROOT / "docs/test-plan/perception-quality-v8-protocol.md")
    files.add(ROOT / "docs/test-plan/perception-quality-v8-preparation-revision.md")
    files.add(ROOT / "docs/test-plan/perception-quality-v8-recovery.md")
    files.add(SURVEY)
    files.update((ROOT / "third_party/megvii-yolox-large").glob("*"))
    result = dict(
        schema="m10-quality-freeze-v8",
        created_utc=datetime.now(timezone.utc).isoformat(),
        models=MODELS,
        plan_sha256=sha256_file(PLAN),
        protocol_sha256=sha256_file(PROTOCOL),
        exclusion_sha256=sha256_file(EXCLUSION),
        preparation=prep,
        model_check_sha256=sha256_file(path.parent / "model-check.json"),
        sources={str(p.relative_to(ROOT)): sha256_file(p) for p in sorted(files)},
    )
    write_new(path, result)
    return result


def check_freeze(path):
    f = read_json(path)
    validate_descriptors()
    require(
        f["schema"] == "m10-quality-freeze-v8"
        and f["models"] == MODELS
        and f["plan_sha256"] == sha256_file(PLAN)
        and f["protocol_sha256"] == sha256_file(PROTOCOL)
        and f["exclusion_sha256"] == sha256_file(EXCLUSION)
        and f["preparation"] == check_preparation(path.parent)
        and f["model_check_sha256"] == sha256_file(path.parent / "model-check.json"),
        "v8 freeze identity",
    )
    check_numeric(path.parent / "model-check.json")
    for name, digest in f["sources"].items():
        require(sha256_file(ROOT / name) == digest, f"v8 frozen source changed: {name}")
    return f


def check_selection(path, frozen_path):
    check_freeze(frozen_path)
    s = read_json(path)
    require(
        s["schema"] == "m10-quality-selection-v8"
        and s["freeze_sha256"] == sha256_file(frozen_path)
        and s["selected"] in CANDIDATES[1:]
        and s["runtime_promotion"] is False
        and datetime.fromisoformat(s["created_utc"])
        > datetime.fromisoformat(read_json(frozen_path)["created_utc"]),
        "v8 prospective nomination",
    )
    import tempfile
    from audit_quality_experiment import compare_selection
    from quality_benchmark_v8 import score, nominate

    score_root = path.parent
    expected = [f"development-{c}-score.json" for c in CANDIDATES]
    if not all((score_root / name).exists() for name in expected):
        score_root = score_root.parent
    require(
        {Path(p).name for p in s["score_files"]} == set(expected),
        "nomination score set",
    )
    for name, digest in s["score_files"].items():
        require(
            sha256_file(score_root / Path(name).name) == digest,
            "nomination score bytes",
        )
    for c in CANDIDATES:
        require(
            score(
                score_root / "development-data",
                score_root / f"development-{c}/result.json",
                frozen_path,
            )
            == read_json(score_root / f"development-{c}-score.json"),
            "nomination recomputed score",
        )
    with tempfile.TemporaryDirectory() as temp:
        recomputed = nominate(
            [score_root / n for n in expected],
            frozen_path,
            Path(temp) / "selection.json",
        )
        compare_selection(s, recomputed)
    return s

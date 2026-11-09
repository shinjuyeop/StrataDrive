"""Prospective V6 identity: new sites, prepared visibility, fixed RGB-only policy."""

from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import read_json
from physical_ai.perception.quality_candidates_v6 import (
    CANDIDATES,
    MODELS,
    INPUT_PROFILE,
    POLICY,
)
from quality_benchmark import require, write_new
from quality_road_v6 import validate_plan, build, SURVEY
from quality_staging_v5 import STAGING

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / "profiles/perception-road-evaluation-v6.json"
PREPARATION_PLAN = ROOT / "profiles/perception-road-preparation-v6.json"
PROTOCOL = ROOT / "profiles/perception-quality-protocol-v6.json"
BASE_EXCLUSION = ROOT / "profiles/perception-quality-exclusion-v6.json"
EXCLUSION = ROOT / "profiles/perception-quality-evaluation-exclusion-v6.json"


def validate_descriptors():
    p = read_json(PROTOCOL)
    old = read_json(ROOT / "profiles/perception-quality-protocol-v4.json")
    require(
        p["schema"] == "m10-quality-protocol-v6"
        and p["road_plan"] == PLAN.name
        and p["metadata_revision"] == "v6"
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
            sites=[74, 80],
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
        "v6 fixed policy/models and unchanged quality gates",
    )
    expected = build()
    require(
        read_json(PLAN) == expected[0] and read_json(PREPARATION_PLAN) == expected[1],
        "map-to-plan replay",
    )
    validate_plan(read_json(PLAN))
    validate_plan(read_json(PREPARATION_PLAN))
    previous = (
        ROOT / "docs/test-plan/evidence/m10_quality_v5/future-evaluation-exclusion.json"
    )
    require(
        sha256_file(BASE_EXCLUSION) == sha256_file(previous)
        and len(set(read_json(BASE_EXCLUSION)["rgb_sha256"])) == 2357,
        "all consumed V1-V5 excluded",
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
        frozen["schema"] == "m10-road-preparation-freeze-v6",
        "preparation source identity",
    )
    require(
        frozen["survey_sha256"] == sha256_file(SURVEY), "original map query identity"
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
    seen = set()
    binding = {
        "preparation-freeze.json": sha256_file(base / "preparation-freeze.json"),
        "preparation-runs.json": sha256_file(base / "preparation-runs.json"),
    }
    for part in ("development", "holdout"):
        path = base / f"preparation-{part}-data/acceptance.json"
        r = read_json(path)
        run = base / runs[part]
        server = read_json(run / "server.json")
        require(
            r["schema"] == "m10-road-preparation-acceptance-v6"
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
                "tests/integration/perception/carla_road_preparation_v6.py"
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
    r = check_model_report(path)
    data = path.parent / "preparation-development-data/rgb.json"
    require(
        r["dataset_sha256"] == sha256_file(data),
        "numeric check uses separate preparation",
    )
    views = read_json(path.parent / "view-check.json")
    require(
        views["schema"] == "m10-v6-view-check"
        and views["status"] == "PASS"
        and views["dataset_sha256"] == sha256_file(data)
        and views["model_sha256"] == MODELS[CANDIDATES[1]]
        and views["source_sha256"]
        == sha256_file(ROOT / "physical_ai/perception/quality_candidates_v6.py")
        and views["box_atol"] == 0.01
        and views["score_atol"] == 1e-4
        and len(views["rows"]) == 6
        and all(row["passed"] is True for row in views["rows"])
        and all(
            sum(row["candidate"] == c for row in views["rows"]) == 3
            for c in CANDIDATES[1:]
        ),
        "complete V6 CPU/CUDA view comparison required",
    )
    return r


def freeze(path):
    validate_descriptors()
    prep = check_preparation(path.parent)
    check_numeric(path.parent / "model-check.json")
    files = set((ROOT / "physical_ai/perception").glob("*.py"))
    files.update((ROOT / "tests/integration/perception").glob("*.py"))
    files.update((ROOT / "profiles").glob("perception-*.json"))
    files.add(ROOT / "docs/test-plan/perception-quality-v6-protocol.md")
    files.update((ROOT / "third_party/megvii-yolox-large").glob("*"))
    result = dict(
        schema="m10-quality-freeze-v6",
        created_utc=datetime.now(timezone.utc).isoformat(),
        models=MODELS,
        plan_sha256=sha256_file(PLAN),
        protocol_sha256=sha256_file(PROTOCOL),
        exclusion_sha256=sha256_file(EXCLUSION),
        preparation=prep,
        model_check_sha256=sha256_file(path.parent / "model-check.json"),
        view_check_sha256=sha256_file(path.parent / "view-check.json"),
        sources={str(p.relative_to(ROOT)): sha256_file(p) for p in sorted(files)},
    )
    write_new(path, result)
    return result


def check_freeze(path):
    f = read_json(path)
    validate_descriptors()
    require(
        f["schema"] == "m10-quality-freeze-v6"
        and f["models"] == MODELS
        and f["plan_sha256"] == sha256_file(PLAN)
        and f["protocol_sha256"] == sha256_file(PROTOCOL)
        and f["exclusion_sha256"] == sha256_file(EXCLUSION)
        and f["preparation"] == check_preparation(path.parent)
        and f["model_check_sha256"] == sha256_file(path.parent / "model-check.json")
        and f["view_check_sha256"] == sha256_file(path.parent / "view-check.json"),
        "v6 freeze identity",
    )
    check_numeric(path.parent / "model-check.json")
    for name, digest in f["sources"].items():
        require(sha256_file(ROOT / name) == digest, f"v6 frozen source changed: {name}")
    return f


def check_selection(path, frozen_path):
    check_freeze(frozen_path)
    s = read_json(path)
    require(
        s["schema"] == "m10-quality-selection-v6"
        and s["freeze_sha256"] == sha256_file(frozen_path)
        and s["selected"] in CANDIDATES[1:]
        and s["runtime_promotion"] is False
        and datetime.fromisoformat(s["created_utc"])
        > datetime.fromisoformat(read_json(frozen_path)["created_utc"]),
        "v6 prospective nomination",
    )
    import tempfile
    from audit_quality_experiment import compare_selection
    from quality_benchmark_v6 import score, nominate

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


def check_model_report(path):
    report = read_json(path)
    require(
        report["schema"] == "m10-model-check-v6"
        and report["status"] == "PASS"
        and report["model_sha256"] == MODELS["large-v6"]
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

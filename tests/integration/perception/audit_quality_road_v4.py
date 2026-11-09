#!/usr/bin/env python3
"""Reconstruct actual-site preparation from raw pairs and the saved road survey."""

import argparse
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import read_json, RgbDataset
from physical_ai.perception.yolox import image_health
from quality_benchmark import require, write_new
from quality_plan_v4 import build, TEMPLATE, ROOT, validate_plan
from prepare_quality_road_v4 import prepare
from select_road_sites_v4 import derive


def audit_initial_trial(root):
    frozen = read_json(root / "preparation-freeze.json")
    for name, digest in frozen["sources"].items():
        require(
            sha256_file(root / "frozen-source" / name) == digest,
            "initial source snapshot",
        )
    dev = root / "development-01"
    held = root / "holdout-01"
    for run in (dev, held):
        s = read_json(run / "server.json")
        require(
            s["probe_sha256"]
            == sha256_file(run / "capture-probe.py")
            == frozen["sources"][
                "tests/integration/perception/carla_quality_capture_v4.py"
            ]
            and s["helper_sha256"]
            == sha256_file(run / "quality_geometry_v4.py")
            == frozen["sources"]["tests/integration/perception/quality_geometry_v4.py"],
            "initial executed source",
        )
    with tempfile.TemporaryDirectory() as tmp:
        prepared = Path(tmp) / "data"
        result = prepare(
            dev / "dataset/capture.json",
            dev / "quality-plan.json",
            root / "frozen-source/profiles/perception-road-exclusion-v4.json",
            prepared,
        )
        require(result["status"] == "PASS", "initial development preparation")
        for name in ("rgb.json", "evaluation-only-gt.json", "preparation-data.json"):
            require(
                sha256_file(prepared / name)
                == sha256_file(root / "development-data" / name),
                "initial development raw replay",
            )
    h = read_json(held / "server.json")
    capture = read_json(held / "dataset/capture.json")
    require(
        h["status"] == capture["status"] == "FAIL"
        and h["capture_exit"] == 1
        and h["server_exit"] == 130
        and len(capture["frames"]) == len(capture["scenes"]) == 1,
        "initial incomplete held preparation",
    )
    for row in capture["frames"]:
        for stream in ("rgb", "instance"):
            require(
                sha256_file(held / "dataset" / row[stream]["path"])
                == row[stream]["sha256"],
                "partial raw hash",
            )
    return dict(
        audit="PASS",
        development_pairs=99,
        development_preparation="PASS",
        holdout_pairs=1,
        holdout_preparation="FAIL",
        inference_performed=False,
        scope="Initial18 site enters junction; actual-site lane check rejects before second pair; not pooled into final preparation",
    )


def audit_intermediate_trial(root):
    frozen = read_json(root / "preparation-freeze.json")
    for name, digest in frozen["sources"].items():
        require(
            sha256_file(root / "frozen-source" / name) == digest,
            "intermediate source bytes",
        )
    reports = {}
    for part in ("development", "holdout"):
        run = root / f"{part}-01"
        server = read_json(run / "server.json")
        require(
            server["probe_sha256"]
            == sha256_file(run / "capture-probe.py")
            == frozen["sources"][
                "tests/integration/perception/carla_quality_capture_v4.py"
            ]
            and server["helper_sha256"]
            == sha256_file(run / "quality_geometry_v4.py")
            == frozen["sources"]["tests/integration/perception/quality_geometry_v4.py"],
            "intermediate executed source",
        )
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "data"
            result = prepare(
                run / "dataset/capture.json",
                run / "quality-plan.json",
                root / "frozen-source/profiles/perception-road-exclusion-v4.json",
                data,
            )
            for name in (
                "rgb.json",
                "evaluation-only-gt.json",
                "preparation-data.json",
            ):
                require(
                    sha256_file(data / name)
                    == sha256_file(root / f"{part}-data" / name),
                    "intermediate raw reconstruction",
                )
            saved = read_json(root / f"{part}-data/acceptance.json")
            require(
                all(result[k] == saved[k] for k in saved if k != "completed_utc"),
                "intermediate preparation replay",
            )
        reports[part] = dict(
            status=result["status"], frames=99, missing_actors=result["missing_actors"]
        )
    require(
        reports["development"]["status"] == "PASS"
        and reports["holdout"]["status"] == "FAIL"
        and len(reports["holdout"]["missing_actors"]) == 3,
        "31m walker support failure preserved",
    )
    return dict(
        audit="PASS",
        preparation=reports,
        inference_performed=False,
        scope="Intermediate complete preparation remains failed: held walker31m24px; no mask/gate relaxation",
    )


def audit(root):
    frozen = read_json(root / "preparation-freeze.json")
    require(frozen["schema"] == "m10-road-preparation-freeze-v4", "freeze schema")
    for name, digest in frozen["sources"].items():
        require(
            sha256_file(ROOT / name)
            == sha256_file(root / "frozen-source" / name)
            == digest,
            "frozen source/config drift",
        )
    survey_path = root / frozen["survey_relative"]
    survey = read_json(survey_path)
    require(sha256_file(survey_path) == frozen["survey_sha256"], "survey identity")
    for attempt in ("survey-01", "survey-02"):
        run = root / attempt
        server = read_json(run / "server.json")
        require(
            server["probe_sha256"] == sha256_file(run / "capture-probe.py")
            and server["helper_sha256"] == sha256_file(run / "quality_geometry_v4.py"),
            "survey source bytes",
        )
        require(
            server["server_exit"] == 130 and server["shutdown_budget_seconds"] == 30,
            "survey lifecycle",
        )
        require(
            (server["status"], server["capture_exit"])
            == (("FAIL", 1) if attempt == "survey-01" else ("PASS", 0)),
            "original survey failure preserved",
        )
    raw_survey = root / "survey-02/dataset/survey.json"
    require(
        sha256_file(raw_survey) == frozen["raw_survey_sha256"], "raw map query identity"
    )
    require(
        derive(read_json(raw_survey), sha256_file(raw_survey)) == survey,
        "nonjunction site selection replay",
    )
    evaluation, preparation = build(
        survey, sha256_file(survey_path), read_json(TEMPLATE), sha256_file(TEMPLATE)
    )
    evaluation_path = ROOT / "profiles/perception-road-evaluation-v4.json"
    preparation_path = ROOT / "profiles/perception-road-preparation-v4.json"
    require(
        evaluation == read_json(evaluation_path)
        and preparation == read_json(preparation_path),
        "survey-to-plan replay",
    )
    validate_plan(evaluation)
    validate_plan(preparation)
    exclusion_path = ROOT / "profiles/perception-road-exclusion-v4.json"
    prior = set(read_json(exclusion_path)["rgb_sha256"])
    observed = {}
    summary = {}
    for part in ("development", "holdout"):
        run = root / f"{part}-01"
        data = root / f"{part}-data"
        server = read_json(run / "server.json")
        require(
            server["probe_sha256"]
            == sha256_file(run / "capture-probe.py")
            == frozen["sources"][
                "tests/integration/perception/carla_quality_capture_v4.py"
            ]
            and server["helper_sha256"]
            == sha256_file(run / "quality_geometry_v4.py")
            == frozen["sources"]["tests/integration/perception/quality_geometry_v4.py"]
            and server["plan_sha256"]
            == sha256_file(run / "quality-plan.json")
            == sha256_file(preparation_path),
            "executed capture source/plan",
        )
        with tempfile.TemporaryDirectory() as temp:
            rebuilt = Path(temp) / "data"
            result = prepare(
                run / "dataset/capture.json", preparation_path, exclusion_path, rebuilt
            )
            for name in (
                "rgb.json",
                "evaluation-only-gt.json",
                "preparation-data.json",
            ):
                require(
                    sha256_file(rebuilt / name) == sha256_file(data / name),
                    "raw reconstruction",
                )
            saved = read_json(data / "acceptance.json")
            require(
                all(result[k] == saved[k] for k in saved if k != "completed_utc"),
                "preparation result replay",
            )
        observed[part] = set(saved["rgb_sha256"])
        require(not observed[part] & prior, "prior RGB reused")
        health = [
            image_health(frame) for _, frame in RgbDataset(data / "rgb.json").frames()
        ]
        summary[part] = {
            k: saved[k]
            for k in (
                "status",
                "site",
                "frames",
                "gates",
                "primary_coverage",
                "objects",
                "excluded",
            )
        }
        summary[part].update(
            min_luma_std=min(h["luma_std"] for h in health), all_rgb_health="PASS"
        )
    require(
        not observed["development"] & observed["holdout"], "preparation sites reuse RGB"
    )
    ready = all(v["status"] == "PASS" for v in summary.values())
    return dict(
        schema="m10-road-preparation-audit-v4",
        audit="PASS",
        preparation_status="PASS" if ready else "FAIL",
        future_plan_preparation_complete=ready,
        evaluation_plan_sha256=sha256_file(evaluation_path),
        preparation_plan_sha256=sha256_file(preparation_path),
        freeze_sha256=sha256_file(root / "preparation-freeze.json"),
        survey_sha256=sha256_file(survey_path),
        prior_rgb_overlap=0,
        cross_site_rgb_overlap=0,
        prior_rgb_excluded=len(prior),
        new_preparation_rgb=len(observed["development"] | observed["holdout"]),
        inference_performed=False,
        quality_evaluation="NOT_RUN",
        runtime_promotion=False,
        sites=summary,
        scope="Actual-site preparation only; a future quality freeze must also exclude these preparation images and recheck evaluation coverage",
        initial_trial=audit_initial_trial(root.parent / "m10-road-preparation-v4"),
        intermediate_trial=audit_intermediate_trial(
            root.parent / "m10-road-preparation-v4b"
        ),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("root", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    result = audit(a.root)
    write_new(a.output, result)
    print(
        {
            k: result[k]
            for k in ("audit", "preparation_status", "future_plan_preparation_complete")
        }
    )

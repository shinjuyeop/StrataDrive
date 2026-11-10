#!/usr/bin/env python3
"""Rebuild the complete road-site v8 experiment from raw captures and frozen sources."""

import argparse
from datetime import datetime
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import read_json
from physical_ai.perception.quality_candidates_v8 import CANDIDATES
from audit_quality_experiment import compare_selection, separate_partitions
from prepare_quality_v8 import prepare
from prepare_road_v8 import prepare as prepare_road
from quality_benchmark_v8 import score, nominate
from quality_benchmark import relative
from quality_v8_common import (
    PROTOCOL,
    PREPARATION_PLAN,
    BASE_EXCLUSION,
    check_freeze,
    require,
    write_new,
)


def audit_preparation(root, frozen):
    runs = read_json(root / "preparation-runs.json")
    source = read_json(root / "preparation-freeze.json")
    summaries = {}
    for part in ("development", "holdout"):
        run = root / runs[part]
        saved = read_json(root / f"preparation-{part}-data/acceptance.json")
        require(
            datetime.fromisoformat(source["created_utc"])
            < datetime.fromisoformat(read_json(run / "server.json")["started_utc"])
            < datetime.fromisoformat(frozen["created_utc"])
            and datetime.fromisoformat(saved["completed_utc"])
            < datetime.fromisoformat(frozen["created_utc"]),
            "actual model-free preparation before quality freeze",
        )
        with tempfile.TemporaryDirectory() as temporary:
            rebuilt = Path(temporary) / "data"
            result = prepare_road(
                run / "dataset/capture.json", PREPARATION_PLAN, BASE_EXCLUSION, rebuilt
            )
            require(
                all(result[k] == saved[k] for k in saved if k != "completed_utc"),
                "preparation gate replay",
            )
            for name in (
                "rgb.json",
                "evaluation-only-gt.json",
                "preparation-data.json",
            ):
                require(
                    sha256_file(rebuilt / name)
                    == sha256_file(root / f"preparation-{part}-data" / name),
                    "preparation raw reconstruction",
                )
        summaries[part] = dict(
            status=saved["status"],
            frames=99,
            site=saved["site"],
            gates=saved["gates"],
            primary_coverage=saved["primary_coverage"],
        )
    return summaries


def audit(root):
    frozen_path = root / "experiment-freeze.json"
    frozen = check_freeze(frozen_path)
    preparation = audit_preparation(root, frozen)
    for part in ("development", "holdout"):
        require(
            datetime.fromisoformat(frozen["created_utc"])
            < datetime.fromisoformat(
                read_json(
                    root
                    / read_json(root / "evaluation-runs.json")[part]
                    / "server.json"
                )["started_utc"]
            ),
            "freeze before evaluation acquisition",
        )
    selected_path = root / "candidate-selection.json"
    selection = read_json(selected_path)
    require(selection["runtime_promotion"] is False, "automatic promotion")
    for name, digest in frozen["sources"].items():
        require(
            sha256_file(root / "frozen-source" / name) == digest,
            "missing frozen source bytes",
        )
    for name in ("plan", "protocol"):
        require(
            sha256_file(root / f"{name}-before-capture.json")
            == frozen[f"{name}_sha256"],
            "pre-capture configuration",
        )
    scores, manifests, summaries, times = {}, {}, {}, {}
    for part in ("development", "holdout"):
        cap_root, data = (
            root / read_json(root / "evaluation-runs.json")[part],
            root / f"{part}-data",
        )
        server = read_json(cap_root / "server.json")
        require(
            server["probe_sha256"]
            == sha256_file(cap_root / "capture-probe.py")
            == frozen["sources"][
                "tests/integration/perception/carla_quality_evaluation_v8.py"
            ]
            and sha256_file(cap_root / "quality-plan.json") == frozen["plan_sha256"]
            and server["helper_sha256"]
            == sha256_file(cap_root / "quality_geometry_v4.py")
            == frozen["sources"]["tests/integration/perception/quality_geometry_v4.py"]
            and server["staging_sha256"]
            == sha256_file(cap_root / "quality_staging_v5.py")
            == frozen["sources"]["tests/integration/perception/quality_staging_v5.py"]
            and server["freeze_sha256"] == sha256_file(frozen_path)
            and "-quality-level=Epic" in server["argv"],
            "v8 capture source/profile",
        )
        if part == "holdout":
            require(
                server["selection_sha256"]
                == sha256_file(selected_path)
                == sha256_file(cap_root / "candidate-selection.json"),
                "pre-acquisition nomination",
            )
        with tempfile.TemporaryDirectory() as temporary:
            rebuilt = Path(temporary) / "data"
            summaries[part] = prepare(
                cap_root / "dataset/capture.json", rebuilt, frozen_path
            )
            for name in (
                "rgb.json",
                "evaluation-only-gt.json",
                "benchmark.json",
                "benchmark-seal.json",
                "visibility.json",
            ):
                require(
                    sha256_file(rebuilt / name) == sha256_file(data / name),
                    "raw reconstruction differs",
                )
        manifests[part] = read_json(data / "rgb.json")
        candidates = (
            CANDIDATES if part == "development" else ("baseline", selection["selected"])
        )
        scores[part] = {}
        for candidate in candidates:
            run_path = root / f"{part}-{candidate}/result.json"
            saved = root / f"{part}-{candidate}-score.json"
            recomputed = score(data, run_path, frozen_path)
            require(
                recomputed == read_json(saved), "stored score differs from predictions"
            )
            scores[part][candidate] = recomputed
            times[part, candidate] = datetime.fromisoformat(
                read_json(run_path)["started_utc"]
            )
    separate_partitions(manifests["development"], manifests["holdout"])
    with tempfile.TemporaryDirectory() as temporary:
        recomputed = nominate(
            [root / f"development-{c}-score.json" for c in CANDIDATES],
            frozen_path,
            Path(temporary) / "selection.json",
        )
        compare_selection(selection, recomputed)
    start = datetime.fromisoformat(frozen["created_utc"])
    selected_at = datetime.fromisoformat(selection["created_utc"])
    require(
        selected_at
        < datetime.fromisoformat(
            read_json(
                root
                / read_json(root / "evaluation-runs.json")["holdout"]
                / "server.json"
            )["started_utc"]
        ),
        "nomination before holdout acquisition",
    )
    require(
        all(
            start < t < selected_at for (p, _), t in times.items() if p == "development"
        )
        and all(selected_at < t for (p, _), t in times.items() if p == "holdout"),
        "experiment order",
    )
    nominee = selection["selected"]
    comparison = relative(
        scores["holdout"]["baseline"], scores["holdout"][nominee], read_json(PROTOCOL)
    )
    eligible = (
        selection["development_relative"][nominee]["status"] == "PASS"
        and scores["development"][nominee]["absolute_quality"] == "PASS"
        and scores["holdout"][nominee]["absolute_quality"] == "PASS"
        and comparison["status"] == "PASS"
    )
    return dict(
        schema="m10-quality-experiment-audit-v8",
        audit="PASS",
        selected=nominee,
        freeze_sha256=sha256_file(frozen_path),
        selection_sha256=sha256_file(selected_path),
        raw_reconstruction=summaries,
        cross_partition_rgb_overlap=0,
        prior_rgb_overlap=0,
        prior_rgb_excluded=len(
            read_json(
                Path(__file__).resolve().parents[3]
                / "profiles/perception-quality-evaluation-exclusion-v8.json"
            )["rgb_sha256"]
        ),
        holdout_relative=comparison,
        eligible_for_runtime_review=eligible,
        runtime_promotion=False,
        preparation_binding=frozen["preparation"],
        preparation_raw_reconstruction=preparation,
        scope="Prospective Rider-aware visible-mask comparison; no vehicle/ODD or live20Hz acceptance",
        scores={
            p: {
                c: {
                    k: s[k]
                    for k in (
                        "micro",
                        "per_class",
                        "gates",
                        "absolute_quality",
                        "riders",
                        "primary_coverage",
                        "visibility",
                    )
                }
                for c, s in group.items()
            }
            for p, group in scores.items()
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment", type=Path)
    parser.add_argument("output", type=Path)
    a = parser.parse_args()
    r = audit(a.experiment)
    write_new(a.output, r)
    print(
        {
            k: r[k]
            for k in (
                "audit",
                "selected",
                "holdout_relative",
                "eligible_for_runtime_review",
            )
        }
    )

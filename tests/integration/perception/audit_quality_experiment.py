#!/usr/bin/env python3
"""Recompute the sealed experiment, including cross-run selection and raw lineage.

This additional auditor does not change the pre-inference v1 scorer or gates.
"""

import argparse
from datetime import datetime
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import read_json
from prepare_quality import prepare_quality
from quality_benchmark import (
    PLAN,
    PROTOCOL,
    check_freeze,
    nominate,
    relative,
    require,
    score,
    write_new,
)


def compare_development(scores):
    """A nomination may only compare runs of the very same sealed dataset."""
    require(
        len({s["metadata_sha256"] for s in scores}) == 1,
        "nomination mixed development datasets",
    )
    require(
        len({s["freeze_sha256"] for s in scores}) == 1
        and all(s["partition"] == "development" for s in scores),
        "nomination mixed experiment/partition",
    )


def compare_selection(original, recomputed):
    # Recomputing necessarily has a new timestamp. Every decision field is exact.
    def portable(value):
        result = {k: v for k, v in value.items() if k != "created_utc"}
        files = result["score_files"]
        require(
            len({Path(p).name for p in files}) == len(files), "ambiguous score path"
        )
        result["score_files"] = {Path(p).name: digest for p, digest in files.items()}
        return result

    require(
        portable(original) == portable(recomputed),
        "selection does not match development evidence",
    )


def separate_partitions(development, holdout):
    require(
        not {r["scene"] for r in development["frames"]}
        & {r["scene"] for r in holdout["frames"]},
        "partition scene overlap",
    )
    require(
        not {r["rgb_sha256"] for r in development["frames"]}
        & {r["rgb_sha256"] for r in holdout["frames"]},
        "partition RGB byte overlap",
    )


def audit(root):
    frozen_path = root / "experiment-freeze.json"
    frozen = check_freeze(frozen_path)
    selection_path = root / "candidate-selection.json"
    selection = read_json(selection_path)
    require(selection["runtime_promotion"] is False, "automatic runtime promotion")
    require(
        sha256_file(root / "plan-before-capture.json") == frozen["plan_sha256"]
        and sha256_file(root / "protocol-before-capture.json")
        == frozen["protocol_sha256"],
        "pre-capture configuration changed",
    )
    for path, digest in frozen["sources"].items():
        require(
            sha256_file(root / "frozen-source" / path) == digest,
            "frozen source bytes unavailable",
        )
    protocol = read_json(PROTOCOL)
    scores = {}
    summaries = {}
    manifests = {}
    model_times = {}
    for partition in ("development", "holdout"):
        capture_root = root / f"{partition}-01"
        data = root / f"{partition}-data"
        server = read_json(capture_root / "server.json")
        require(
            server["mode"] == "quality"
            and server["capture_exit"] == 0
            and server["plan_sha256"] == frozen["plan_sha256"]
            and server["probe_sha256"]
            == sha256_file(capture_root / "capture-probe.py")
            == frozen["sources"][
                "tests/integration/perception/carla_quality_capture.py"
            ]
            and sha256_file(capture_root / "quality-plan.json") == frozen["plan_sha256"]
            and "-quality-level=Epic" in server["argv"],
            "capture implementation/profile identity",
        )
        if partition == "holdout":
            require(
                server["selection_sha256"]
                == sha256_file(capture_root / "candidate-selection.json")
                == sha256_file(selection_path),
                "holdout acquisition selection binding",
            )
        # Recreate RGB and labels from every hashed BGRA/instance pair. This also
        # checks capture completion, actor lineage, and bounded server cleanup.
        with tempfile.TemporaryDirectory() as temporary:
            rebuilt = Path(temporary) / "data"
            coverage = prepare_quality(
                capture_root / "dataset/capture.json", PLAN, rebuilt
            )
            for name in (
                "rgb.json",
                "evaluation-only-gt.json",
                "benchmark.json",
                "benchmark-seal.json",
            ):
                require(
                    sha256_file(rebuilt / name) == sha256_file(data / name),
                    f"raw capture reconstruction changed {partition}/{name}",
                )
        manifests[partition] = read_json(data / "rgb.json")
        candidates = (
            ["baseline"] + protocol["candidate_ids"]
            if partition == "development"
            else ["baseline", selection["selected"]]
        )
        scores[partition] = {}
        for candidate in candidates:
            run_path = root / f"{partition}-{candidate}/result.json"
            score_path = root / f"{partition}-{candidate}-score.json"
            recomputed = score(data, run_path, frozen_path)
            require(recomputed == read_json(score_path), "saved score changed")
            scores[partition][candidate] = recomputed
            run = read_json(run_path)
            model_times[partition, candidate] = datetime.fromisoformat(
                run["started_utc"]
            )
        summaries[partition] = coverage
    compare_development(list(scores["development"].values()))
    separate_partitions(manifests["development"], manifests["holdout"])
    score_paths = [
        root / f"development-{c}-score.json"
        for c in ["baseline"] + protocol["candidate_ids"]
    ]
    with tempfile.TemporaryDirectory() as temporary:
        rebuilt_selection = nominate(
            score_paths, frozen_path, Path(temporary) / "selection.json"
        )
        compare_selection(selection, rebuilt_selection)
    freeze_time = datetime.fromisoformat(frozen["created_utc"])
    select_time = datetime.fromisoformat(selection["created_utc"])
    require(
        all(
            freeze_time < t < select_time
            for (p, _), t in model_times.items()
            if p == "development"
        )
        and all(select_time < t for (p, _), t in model_times.items() if p == "holdout"),
        "freeze/development/selection/holdout execution order",
    )
    held = scores["holdout"]
    comparison = relative(held["baseline"], held[selection["selected"]], protocol)
    eligible = (
        selection["development_relative"][selection["selected"]]["status"] == "PASS"
        and selection["development_absolute"][selection["selected"]] == "PASS"
        and held[selection["selected"]]["absolute_quality"] == "PASS"
        and comparison["status"] == "PASS"
    )
    return dict(
        schema="m10-quality-experiment-audit-v1",
        audit="PASS",
        freeze_sha256=sha256_file(frozen_path),
        selection_sha256=sha256_file(selection_path),
        auditor_sha256=sha256_file(Path(__file__)),
        raw_reconstruction=summaries,
        cross_partition_rgb_overlap=0,
        selected=selection["selected"],
        holdout_relative=comparison,
        eligible_for_runtime_review=eligible,
        runtime_promotion=False,
        quality_scope="Frozen visible-instance metric only; rider ontology and visible/amodal mismatch require separate annotation review before acceptance",
        scores={
            p: {
                c: {
                    k: s[k] for k in ("micro", "per_class", "absolute_quality", "gates")
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
    args = parser.parse_args()
    result = audit(args.experiment)
    write_new(args.output, result)
    print(
        {
            k: result[k]
            for k in (
                "audit",
                "selected",
                "holdout_relative",
                "eligible_for_runtime_review",
            )
        }
    )

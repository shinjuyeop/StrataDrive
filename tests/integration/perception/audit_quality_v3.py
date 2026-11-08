#!/usr/bin/env python3
"""Rebuild the complete v3 experiment from raw captures and frozen sources."""

import argparse
from datetime import datetime
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import read_json, local_path
from quality_annotation import visible_boxes_v2
from physical_ai.perception.quality_candidates_v3 import CANDIDATES
from audit_quality_experiment import compare_selection, separate_partitions
from prepare_quality_v3 import prepare
from quality_benchmark_v3 import score, nominate
from quality_benchmark import relative
from quality_v3_common import (
    PROTOCOL,
    check_freeze,
    require,
    write_new,
)


def audit_failed_preparation(root):
    capture_path = root / "preparation-01/dataset/capture.json"
    capture = read_json(capture_path)
    server = read_json(root / "preparation-01/server.json")
    plan_path = root / "preparation-01/quality-plan.json"
    plan = read_json(plan_path)
    saved = read_json(root / "preparation-acceptance.json")
    require(
        server["status"] == capture["status"] == "PASS"
        and server["server_exit"] == 130
        and capture["plan_sha256"] == sha256_file(plan_path)
        and saved["status"] == "FAIL",
        "failed preparation acquisition",
    )
    missing = []
    for case, scene, source in zip(
        plan["partitions"]["preparation"]["cases"], capture["scenes"], capture["frames"]
    ):
        require(
            case["id"] == scene["id"] == source["scene"], "failed preparation source"
        )
        for stream in ("rgb", "instance"):
            require(
                sha256_file(local_path(capture_path.parent, source[stream]["path"]))
                == source[stream]["sha256"],
                "failed preparation raw hash",
            )
        included, excluded = visible_boxes_v2(
            local_path(capture_path.parent, source["instance"]["path"]).read_bytes()
        )
        keys = {(g["class_id"], g["instance_id"]) for g in included}
        for actor in scene["actors"]:
            if (actor["class_id"], actor["actor_id"] % 65536) not in keys:
                missing.append(
                    dict(
                        scene=case["id"],
                        blueprint=actor["blueprint"],
                        excluded=excluded,
                    )
                )
    require(
        len(capture["frames"]) == saved["frames"] == 144
        and len(missing) == saved["missing_actors"] == 3,
        "failed preparation denominator",
    )
    return dict(
        audit="PASS",
        preparation_status="FAIL",
        frames=144,
        missing_actors=missing,
        model_inference="NOT RUN on preparation",
        capture_sha256=sha256_file(capture_path),
    )


def audit(root):
    frozen_path = root / "experiment-freeze.json"
    frozen = check_freeze(frozen_path)
    for part in ("development", "holdout"):
        require(
            datetime.fromisoformat(frozen["created_utc"])
            < datetime.fromisoformat(
                read_json(root / f"{part}-01/server.json")["started_utc"]
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
    with tempfile.TemporaryDirectory() as temporary:
        from preflight_quality_v3 import assess

        prep = root / "preparation-01"
        require(
            read_json(prep / "server.json")["probe_sha256"]
            == sha256_file(prep / "capture-probe.py")
            == frozen["sources"][
                "tests/integration/perception/carla_quality_capture_v3.py"
            ],
            "preparation capture source",
        )
        rebuilt = assess(
            root / "preparation-01/dataset/capture.json", Path(temporary) / "prepared"
        )
        original = read_json(root / "preparation-acceptance.json")
        require(
            all(rebuilt[k] == original[k] for k in original if k != "completed_utc"),
            "preparation raw replay",
        )
    scores, manifests, summaries, times = {}, {}, {}, {}
    for part in ("development", "holdout"):
        cap_root, data = root / f"{part}-01", root / f"{part}-data"
        server = read_json(cap_root / "server.json")
        require(
            server["probe_sha256"]
            == sha256_file(cap_root / "capture-probe.py")
            == frozen["sources"][
                "tests/integration/perception/carla_quality_capture_v3.py"
            ]
            and sha256_file(cap_root / "quality-plan.json") == frozen["plan_sha256"]
            and "-quality-level=Epic" in server["argv"],
            "v3 capture source/profile",
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
            summaries[part] = prepare(cap_root / "dataset/capture.json", rebuilt)
            for name in (
                "rgb.json",
                "evaluation-only-gt.json",
                "benchmark.json",
                "benchmark-seal.json",
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
    require(
        datetime.fromisoformat(frozen["preparation_completed_utc"]) < start,
        "preparation before freeze",
    )
    selected_at = datetime.fromisoformat(selection["created_utc"])
    require(
        selected_at
        < datetime.fromisoformat(
            read_json(root / "holdout-01/server.json")["started_utc"]
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
        schema="m10-quality-experiment-audit-v3",
        audit="PASS",
        selected=nominee,
        freeze_sha256=sha256_file(frozen_path),
        selection_sha256=sha256_file(selected_path),
        raw_reconstruction=summaries,
        cross_partition_rgb_overlap=0,
        prior_v1_v2_preparation_rgb_overlap=0,
        holdout_relative=comparison,
        eligible_for_runtime_review=eligible,
        runtime_promotion=False,
        failed_preparation=audit_failed_preparation(root.parent / "m10-quality-v3"),
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

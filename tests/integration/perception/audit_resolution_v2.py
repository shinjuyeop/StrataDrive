#!/usr/bin/env python3
"""Replay every development raw, strict score and sealed selection without inference."""

import argparse
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import read_json
from physical_ai.perception.resolution_v2 import SIZES, VECTOR
from quality_benchmark import relative
from resolution_v2_common import ROOT, check_freeze, check_numeric, require, write_new
from run_resolution_v2 import score, check_selection, nonregression


def audit(base):
    frozen = check_freeze(base / "freeze.json")
    numeric = check_numeric(base)
    selection = check_selection(base)
    manifest = read_json(base / "models.json")
    require(
        datetime.fromisoformat(frozen["created_utc"])
        < datetime.fromisoformat(manifest["started_utc"])
        < datetime.fromisoformat(manifest["finished_utc"])
        < datetime.fromisoformat(numeric["started_utc"])
        < datetime.fromisoformat(numeric["finished_utc"]),
        "freeze/export/numeric order",
    )
    selected_at = datetime.fromisoformat(selection["created_utc"])
    scores = {}
    for group in ("selection", "regression"):
        scores[group] = {}
        for size in ("baseline", *SIZES):
            recomputed = score(base, size, group)
            require(
                recomputed == read_json(base / f"{group}-{size}-score.json"),
                "raw/primary score replay",
            )
            scores[group][size] = recomputed
            if size != "baseline":
                run = read_json(base / "runs" / str(size) / group / "run.json")
                start, finish = map(
                    datetime.fromisoformat, (run["started_utc"], run["finished_utc"])
                )
                require(
                    datetime.fromisoformat(numeric["finished_utc"]) < start < finish,
                    "numeric before inference",
                )
                require(
                    finish < selected_at
                    if group == "selection"
                    else selected_at < start,
                    "sealed selection before consumed regression",
                )
                require(
                    run["selection_sha256"]
                    == (
                        sha256_file(base / "selection.json")
                        if group == "regression"
                        else None
                    ),
                    "selection binding",
                )
    selected = selection["selected"]
    reg = scores["regression"][selected]
    rel = relative(
        scores["regression"]["baseline"],
        reg,
        read_json(ROOT / "profiles/perception-quality-protocol-v4.json"),
    )
    non = nonregression(scores["regression"][640], reg)
    eligible = (
        selection["eligible_for_fresh_test"]
        and reg["absolute_quality"] == "PASS"
        and rel["status"] == non["status"] == "PASS"
    )
    return dict(
        schema="m10-resolution-audit-v2",
        audit="PASS",
        freeze_sha256=sha256_file(base / "freeze.json"),
        model_manifest_sha256=sha256_file(base / "models.json"),
        selection_sha256=sha256_file(base / "selection.json"),
        native_numeric_probes=6,
        unique_development_frames=486,
        candidate_raw_replays=972,
        baseline_raw_replays=486,
        selected=selected,
        selection_eligible=selection["eligible_for_fresh_test"],
        regression_absolute=reg["absolute_quality"],
        regression_relative=rel,
        regression_nonregression640=non,
        eligible_for_next_fresh_quality_test=eligible,
        holdout_access=False,
        fresh_acceptance=False,
        new_rgb=False,
        future_rgb_exclusion=5449,
        training=False,
        runtime_promotion=False,
        selected_model=manifest["models"][str(selected)],
        vector=list(VECTOR),
        scope="Consumed development comparison only; accuracy, live20Hz, vehicle and independent Thor/Orin acceptance remain separate",
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("base", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    r = audit(a.base)
    write_new(a.output, r)
    print(
        {k: r[k] for k in ("audit", "selected", "eligible_for_next_fresh_quality_test")}
    )

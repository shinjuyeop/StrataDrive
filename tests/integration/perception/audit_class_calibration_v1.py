#!/usr/bin/env python3
"""Read-back JSON replay of the unchanged frozen class calibration computations."""

import argparse
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import read_json
from run_model_screen_v1 import require, write_new
from run_class_calibration_v1 import ROOT, check_freeze, fit, regress

EXTRA_SOURCES = (
    "tests/integration/perception/audit_class_calibration_v1.py",
    "tests/integration/perception/test_class_calibration_audit_v1.py",
    "docs/test-plan/perception-class-calibration-v1-audit-annex.md",
)


def exact_json_candidates(expected, actual):
    # Round trip is representation normalization, never numerical approximation.
    require(
        json.loads(json.dumps(actual, allow_nan=False)) == expected,
        "exact serialized candidate replay",
    )


def freeze(frozen, selection, numeric, regression, failure_log, output):
    old = check_freeze(frozen)
    inputs = dict(old["inputs"])
    for path in (frozen, selection, numeric, regression, failure_log):
        inputs[str(path.relative_to(ROOT))] = sha256_file(path)
    sources = dict(old["sources"])
    sources.update({name: sha256_file(ROOT / name) for name in EXTRA_SOURCES})
    result = dict(
        schema="m10-class-calibration-audit-annex-v1",
        sources=sources,
        inputs=inputs,
        reason="Read back JSON before exact candidate-tree equality; frozen computations unchanged",
        holdout_access=False,
        fresh_acceptance=False,
        runtime_promotion=False,
    )
    write_new(output, result)
    return result


def audit(annex, frozen, selection, numeric, regression, output):
    bound = read_json(annex)
    require(
        bound["schema"] == "m10-class-calibration-audit-annex-v1"
        and bound["holdout_access"] is False
        and bound["fresh_acceptance"] is False
        and bound["runtime_promotion"] is False,
        "audit annex scope",
    )
    for name, digest in {**bound["sources"], **bound["inputs"]}.items():
        require(
            sha256_file(ROOT / name) == digest,
            "audit annex input/source changed: " + name,
        )
    check_freeze(frozen)
    chosen, checked = read_json(selection), read_json(regression)
    with tempfile.TemporaryDirectory() as directory:
        fitted, regressed = (
            Path(directory) / "fit.json",
            Path(directory) / "regression.json",
        )
        fit(frozen, fitted)
        regress(frozen, selection, numeric, regressed)
        exact_json_candidates(chosen["candidates"], read_json(fitted)["candidates"])
        exact_json_candidates(checked["candidates"], read_json(regressed)["candidates"])
    result = dict(
        status="PASS",
        source_root=str(ROOT),
        sources=len(bound["sources"]),
        scorecards=31250,
        selected_raw_replays=810,
        annex_sha256=sha256_file(annex),
        freeze_sha256=sha256_file(frozen),
        selection_sha256=sha256_file(selection),
        regression_sha256=sha256_file(regression),
        failed_initial_audit_preserved=True,
        computations_changed=False,
        holdout_access=False,
        fresh_acceptance=False,
        runtime_promotion=False,
    )
    write_new(output, result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "audit"))
    for key in (
        "annex",
        "freeze",
        "selection",
        "numeric",
        "regression",
        "failure-log",
        "output",
    ):
        parser.add_argument(
            "--" + key, type=Path, required=key not in ("annex", "failure-log")
        )
    args = parser.parse_args()
    if args.action == "freeze":
        result = freeze(
            args.freeze.resolve(),
            args.selection.resolve(),
            args.numeric.resolve(),
            args.regression.resolve(),
            args.failure_log.resolve(),
            args.output,
        )
    else:
        result = audit(
            args.annex,
            args.freeze,
            args.selection,
            args.numeric,
            args.regression,
            args.output,
        )
    print(result.get("status", "PASS"))

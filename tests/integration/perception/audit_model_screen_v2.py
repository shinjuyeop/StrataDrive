#!/usr/bin/env python3
"""Replay every raw development output and every calibration/check score."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import numpy as np
from physical_ai.perception.contract import execution_profile, sha256_file
from physical_ai.perception.dataset import read_json
from physical_ai.perception.model_screen_v2 import (
    CANDIDATES,
    REGISTRY,
    THRESHOLDS,
    decode,
)
from run_model_screen_v1 import require, write_new
from run_model_screen_v2 import (
    check_freeze,
    check_selected,
    score,
    selection_key,
    validate_run,
)

ROOT = Path(__file__).resolve().parents[3]


def audit(frozen, numeric, runs, selection_path, check_path, output):
    f = check_freeze(frozen)
    require(
        sha256_file(numeric) == f["numeric_check_sha256"]
        and read_json(numeric)["status"] == "PASS",
        "numeric evidence changed",
    )
    chosen, checked = read_json(selection_path), read_json(check_path)
    require(
        checked["selection_sha256"] == sha256_file(selection_path), "selection hash"
    )
    vendor = read_json(ROOT / "third_party/pretrained-screen-v2/upstream-files.json")
    for name, spec in vendor.items():
        for relative, digest in spec["files"].items():
            require(
                sha256_file(ROOT / "third_party/pretrained-screen-v2" / name / relative)
                == digest,
                "upstream bytes changed",
            )
    registry = read_json(REGISTRY)
    expected_options = execution_profile("cuda")
    rows = raw_bytes = threshold_sets = 0
    for candidate in CANDIDATES:
        family = registry["models"][candidate]["family"]
        for group in ("calibration", "check"):
            run_path = runs / candidate / group / "run.json"
            report = validate_run(f, frozen, run_path, group)
            options = report["provider_options"]["CUDAExecutionProvider"]
            require(
                all(
                    options[k] == expected_options[k]
                    for k in (
                        "device_id",
                        "use_tf32",
                        "cudnn_conv_algo_search",
                        "gpu_mem_limit",
                    )
                ),
                "CUDA options drift",
            )
            require(
                report["status"] == "PASS"
                and report["model_initialization_wall_ns"] > 0
                and report["runtime_promotion"] is False
                and report["board_execution"] is False,
                "run status/scope",
            )
            for row in report["rows"]:
                cache = run_path.parent / row["raw"]
                require(
                    cache.parent == run_path.parent / "raw"
                    and sha256_file(cache) == row["raw_sha256"],
                    "raw integrity",
                )
                timing = [
                    row[k] for k in ("preprocess_ns", "inference_ns", "postprocess_ns")
                ]
                require(
                    all(type(v) is int and v >= 0 for v in timing)
                    and sum(timing) <= row["elapsed_wall_ns"],
                    "stage timing",
                )
                with np.load(cache, allow_pickle=False) as data:
                    raw = dict(data)
                for threshold in THRESHOLDS:
                    expected = row["predictions"][str(threshold)]
                    try:
                        detections = [asdict(d) for d in decode(raw, family, threshold)]
                    except ValueError as error:
                        require(
                            not expected["valid"]
                            and expected["detections"] is None
                            and str(error) in expected["error"],
                            "invalid output replay",
                        )
                    else:
                        require(
                            expected["valid"]
                            and json.loads(json.dumps(detections))
                            == expected["detections"],
                            "full raw threshold replay",
                        )
                    threshold_sets += 1
                rows += 1
                raw_bytes += cache.stat().st_size
        choice = chosen["candidates"][candidate]
        recalculated = [
            score(
                frozen,
                runs / candidate / "calibration/run.json",
                threshold,
                "calibration",
                verify_raw=False,
            )
            for threshold in THRESHOLDS
        ]
        require(
            recalculated == choice["grid"]
            and max(recalculated, key=selection_key) == choice["selected"]
            and choice["threshold"] == choice["selected"]["threshold"],
            "calibration score/selection replay",
        )
    with tempfile.TemporaryDirectory() as directory:
        result = check_selected(
            frozen, runs, selection_path, Path(directory) / "check.json"
        )
        require(
            result["candidates"] == checked["candidates"], "Town04 check score replay"
        )
    require(rows == 2430 and threshold_sets == 19440, "complete raw replay denominator")
    result = dict(
        status="PASS",
        source_root=str(ROOT),
        source_files=len(f["sources"]),
        raw_outputs=rows,
        raw_bytes=raw_bytes,
        threshold_sets=threshold_sets,
        calibration_score_replays=48,
        town04_check_score_replays=12,
        freeze_sha256=sha256_file(frozen),
        selection_sha256=sha256_file(selection_path),
        check_sha256=sha256_file(check_path),
        holdout_access=False,
        fresh_acceptance=False,
        runtime_promotion=False,
    )
    write_new(output, result)
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("freeze", "numeric", "runs", "selection", "check", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    args = p.parse_args()
    result = audit(
        args.freeze, args.numeric, args.runs, args.selection, args.check, args.output
    )
    print(result["status"], result["raw_outputs"], result["threshold_sets"])

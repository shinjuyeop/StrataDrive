#!/usr/bin/env python3
"""Replay exact native sensor bytes, masks, numeric sets, selection and model scores."""

import argparse
from datetime import datetime
import hashlib
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import read_json, local_path
from physical_ai.perception.camera_resolution_v1 import (
    unpack,
    canonical,
    decode,
)
from camera_resolution_v1_common import (
    EXCLUSION,
    check_freeze,
    check_selection,
    derive,
    require,
    write_new,
)
from run_camera_resolution_v1 import score
from check_model_screen_v1 import compare_top300, compare_detections
from dataclasses import asdict


def audit(base):
    check_freeze(base / "freeze.json")
    selection = check_selection(base)
    futures = set(read_json(EXCLUSION)["rgb_sha256"])
    pairs = 0
    numeric_pairs = 0
    attempts = read_json(base / "capture-attempts.json")
    for attempt in attempts:
        run = base / attempt["run"]
        server = read_json(run / "server.json")
        capture = run / "dataset/capture.json"
        require(
            sha256_file(run / "server.json") == attempt["server_sha256"],
            "all-attempt server identity",
        )
        if not capture.exists():
            require(attempt["frames"] == 0, "missing capture raw")
            continue
        require(
            sha256_file(capture) == attempt["capture_sha256"],
            "all-attempt capture identity",
        )
        cap = read_json(capture)
        w, h = cap["camera"]["width"], cap["camera"]["height"]
        hashes = []
        for pair in cap["frames"]:
            raw = unpack(capture.parent, pair["rgb"], w, h)
            unpack(capture.parent, pair["instance"], w, h)
            rgb = (
                np.frombuffer(raw, np.uint8)
                .reshape(h, w, 4)[:, :, 2::-1]
                .copy()
                .tobytes()
            )
            hashes.append(hashlib.sha256(rgb).hexdigest())
        require(
            hashes == attempt["rgb_sha256"] and len(hashes) == attempt["frames"],
            "all-attempt RGB lineage",
        )
        futures.update(hashes)
        pairs += len(hashes)
    require(
        sorted(futures) == read_json(base / "future-exclusion.json")["rgb_sha256"],
        "all-attempt future union",
    )
    accepted = []
    for scale, pilot in selection["pilots"].items():
        run = base / pilot["run"]
        a = read_json(run / "dataset/acceptance.json")
        if a["status"] != "PASS":
            continue
        accepted.append(run)
        numeric = read_json(base / f"numeric-{scale}.json")
        require(
            datetime.fromisoformat(read_json(run / "server.json")["started_utc"])
            < datetime.fromisoformat(numeric["started_utc"])
            < datetime.fromisoformat(numeric["completed_utc"])
            < datetime.fromisoformat(selection["created_utc"]),
            "pilot/numeric/selection order",
        )
        if len(numeric["rows"]) != 3:
            continue
        for row in numeric["rows"]:
            values = []
            for item in row.get("raw_files", []):
                p = local_path(base, item["file"])
                require(sha256_file(p) == item["sha256"], "numeric raw SHA")
                with np.load(p) as arrays:
                    values.append(dict(arrays))
            if row["passed"]:
                require(len(values) == 3, "complete numeric reference/CPU/CUDA")
                for a, b in zip(values, values[1:]):
                    compare_top300(canonical(a, int(scale)), canonical(b, int(scale)))
                    compare_detections(
                        [asdict(d) for d in decode(a, int(scale))],
                        [asdict(d) for d in decode(b, int(scale))],
                    )
                numeric_pairs += 1
    scores = {}
    for scale, name in read_json(base / "comparison-runs.json").items():
        run = base / name
        accepted.append(run)
        server = read_json(run / "server.json")
        require(
            datetime.fromisoformat(selection["created_utc"])
            < datetime.fromisoformat(server["started_utc"])
            and server["selection_sha256"]
            == sha256_file(base / "selection.json")
            == sha256_file(run / "camera-selection.json"),
            "selection before comparison capture",
        )
        result = score(base, run)
        require(
            result == read_json(base / f"comparison-{scale}-score.json"),
            "native raw strict-score replay",
        )
        scores[scale] = result
    for run in accepted:
        result = derive(run / "dataset/capture.json", base / "freeze.json")
        for key, name in [
            ("rgb", "rgb.json"),
            ("truth", "evaluation-only-gt.json"),
            ("metadata", "benchmark.json"),
            ("acceptance", "acceptance.json"),
        ]:
            require(
                result[key] == read_json(run / "dataset" / name),
                "exact sensor/native-mask reconstruction",
            )
    selected = str(selection["selected_scale"])
    baseline = scores["1"]
    candidate = scores[selected]
    from run_resolution_v2 import nonregression

    comparison = nonregression(baseline, candidate)
    recommend = (
        candidate["absolute_quality"] == "PASS" and comparison["status"] == "PASS"
    )
    return dict(
        schema="m10-camera-source-audit-v1",
        audit="PASS",
        selected_scale=int(selected),
        native_dimensions=candidate["source_dimensions"],
        raw_pairs_rehashed=pairs,
        passed_numeric_pairs=numeric_pairs,
        model_raw_replays=81 * len(scores),
        future_rgb_exclusion=len(futures),
        quality_absolute=candidate["absolute_quality"],
        nonregression=comparison,
        recommended_for_next_fresh_test=recommend,
        new_development_only=True,
        holdout_access=False,
        runtime_promotion=False,
        live20Hz_acceptance=False,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("base", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    r = audit(a.base)
    write_new(a.output, r)
    print(r)

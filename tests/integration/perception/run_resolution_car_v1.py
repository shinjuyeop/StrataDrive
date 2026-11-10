#!/usr/bin/env python3
"""Freeze, numerically validate and replay one development-informed car revision."""

import argparse
from datetime import datetime, timezone
from dataclasses import asdict
from itertools import islice
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import numpy as np
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import RgbDataset, read_json, local_path
from physical_ai.perception.resolution_v2 import (
    ResolutionDetector,
    decode as original_decode,
)
from physical_ai.perception.resolution_car_v1 import VECTOR, CANDIDATE, decode
from resolution_v2_common import (
    ROOT,
    PROBES,
    GROUPS,
    check_freeze as check_parent,
    development,
    require,
    write_new,
)
from run_resolution_v2 import quality, nonregression, json_detections
from check_model_screen_v1 import compare_top300, compare_detections
from quality_benchmark import relative

PARENT = ROOT / "build/m10-resolution-v2"


def freeze(base):
    parent = check_parent(PARENT / "freeze.json")
    require(
        read_json(PARENT / "audit.json")["eligible_for_next_fresh_quality_test"]
        is False,
        "retain original rejection",
    )
    sources = dict(parent["sources"])
    inputs = dict(parent["inputs"])
    names = [
        "physical_ai/perception/resolution_car_v1.py",
        "tests/integration/perception/run_resolution_car_v1.py",
        "tests/integration/perception/test_resolution_car_v1.py",
        "docs/test-plan/perception-resolution-car-v1-protocol.md",
    ]
    sources.update({n: sha256_file(ROOT / n) for n in names})
    for path in PARENT.rglob("*"):
        if (
            path.is_file()
            and "frozen-source" not in path.parts
            and "__pycache__" not in path.parts
            and path.suffix in (".json", ".npz", ".onnx")
        ):
            inputs[str(path.relative_to(ROOT))] = sha256_file(path)
    report = dict(
        schema="m10-resolution-car-freeze-v1",
        created_utc=datetime.now(timezone.utc).isoformat(),
        sources=sources,
        inputs=inputs,
        vector=list(VECTOR),
        candidate=CANDIDATE,
        design_frames=486,
        holdout_access=False,
        fresh_acceptance=False,
        runtime_promotion=False,
    )
    write_new(base / "freeze.json", report)
    return report


def check_freeze(base):
    f = read_json(base / "freeze.json")
    require(
        f["schema"] == "m10-resolution-car-freeze-v1"
        and f["vector"] == list(VECTOR)
        and f["candidate"] == CANDIDATE
        and f["design_frames"] == 486
        and all(
            f[k] is False
            for k in ("holdout_access", "fresh_acceptance", "runtime_promotion")
        ),
        "revision freeze scope",
    )
    for n, h in {**f["sources"], **f["inputs"]}.items():
        require(sha256_file(ROOT / n) == h, "revision frozen source/input: " + n)
    return f


def numeric(base):
    check_freeze(base)
    model = read_json(PARENT / "models.json")["models"]["960"]
    cpu, cuda = [
        ResolutionDetector(960, PARENT / model["path"], PARENT / "models.json", mode)
        for mode in ("cpu", "cuda")
    ]
    rows = []
    for n, (source, frame) in enumerate(islice(RgbDataset(PROBES).frames(), 3)):
        feed = cpu.prepare(frame)
        with np.load(PARENT / "reference" / f"960-{n}.npz") as arrays:
            ref = dict(arrays)
        values = [ref, cpu.raw(feed), cuda.raw(feed)]
        deltas = []
        for a, b in zip(values, values[1:]):
            deltas.append(compare_top300(a, b))
            compare_detections(
                [asdict(d) for d in decode(a)], [asdict(d) for d in decode(b)]
            )
        rows.append(
            dict(
                probe=n,
                rgb_sha256=source["rgb_sha256"],
                passed=True,
                deltas=deltas,
                providers=cuda.session.get_providers(),
            )
        )
    report = dict(
        schema="m10-resolution-car-numeric-v1",
        status="PASS",
        freeze_sha256=sha256_file(base / "freeze.json"),
        rows=rows,
        box_atol=0.1,
        score_atol=0.0001,
        cold_calls_excluded=0,
        completed_utc=datetime.now(timezone.utc).isoformat(),
    )
    write_new(base / "numeric.json", report)
    return report


def evaluate(base):
    check_freeze(base)
    n = read_json(base / "numeric.json")
    require(
        n["status"] == "PASS"
        and n["freeze_sha256"] == sha256_file(base / "freeze.json")
        and len(n["rows"]) == 3
        and {r["probe"] for r in n["rows"]} == {0, 1, 2}
        and all(r["passed"] for r in n["rows"]),
        "revision numeric gate",
    )
    scores = {}
    combined = []
    for group, paths in GROUPS.items():
        report = read_json(PARENT / "runs/960" / group / "run.json")
        position = 0
        rows = []
        partitions = {}
        for key, path in paths.items():
            data, meta, truth = development(ROOT / path)
            subtotal = []
            for source, scene, gt in zip(
                data.manifest["frames"], meta["scenes"], truth["frames"]
            ):
                row = report["rows"][position]
                position += 1
                require(
                    row["valid"]
                    and row["dataset"] == key
                    and row["scene"] == source["scene"] == scene["scene"] == gt["scene"]
                    and row["rgb_sha256"] == source["rgb_sha256"]
                    and row["frame"] == source["frame"] == gt["frame"]
                    and row["source_ns"] == source["source_ns"],
                    "revision raw lineage",
                )
                path = local_path(PARENT / "runs/960" / group, row["raw"])
                require(
                    sha256_file(path) == row["raw_sha256"], "revision native raw SHA"
                )
                with np.load(path) as arrays:
                    raw = dict(arrays)
                require(
                    json_detections(original_decode(raw)) == row["detections"],
                    "original vector/JSON exact replay",
                )
                # Timing/admission are the original V2 context, not new live qualification.
                subtotal.append(
                    (
                        scene,
                        gt,
                        json_detections(decode(raw)),
                        True,
                        row["admitted"],
                        None,
                    )
                )
            partitions[key] = quality(subtotal)
            rows.extend(subtotal)
        require(
            position == len(report["rows"]) == 81 * len(paths),
            "revision full denominator",
        )
        scores[group] = dict(partitions=partitions, **quality(rows))
        combined.extend(rows)
    scores["combined"] = quality(combined)
    protocol = read_json(ROOT / "profiles/perception-quality-protocol-v4.json")
    comparisons = {}
    for group in GROUPS:
        baseline = read_json(PARENT / f"{group}-baseline-score.json")
        control = read_json(PARENT / f"{group}-640-score.json")
        comparisons[group] = dict(
            relative=relative(baseline, scores[group], protocol),
            nonregression640=nonregression(control, scores[group]),
            all_sites_absolute=all(
                s["absolute_quality"] == "PASS"
                for s in scores[group]["partitions"].values()
            ),
        )
    eligible = scores["combined"]["absolute_quality"] == "PASS" and all(
        scores[g]["absolute_quality"] == "PASS"
        and c["relative"]["status"] == "PASS"
        and c["nonregression640"]["status"] == "PASS"
        and c["all_sites_absolute"]
        for g, c in comparisons.items()
    )
    return dict(
        schema="m10-resolution-car-evaluation-v1",
        audit="PASS",
        candidate=CANDIDATE,
        vector=list(VECTOR),
        scores=scores,
        comparisons=comparisons,
        eligible_for_next_fresh_quality_test=eligible,
        design_frames=486,
        independent_regression=False,
        holdout_access=False,
        fresh_acceptance=False,
        runtime_promotion=False,
        new_rgb=False,
        future_rgb_exclusion=5449,
        freeze_sha256=sha256_file(base / "freeze.json"),
        numeric_sha256=sha256_file(base / "numeric.json"),
        timing_scope="Original V2 runs only; revised filter is not live timing qualified",
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("freeze", "numeric", "evaluate", "audit"))
    p.add_argument("base", type=Path)
    a = p.parse_args()
    if a.command == "freeze":
        r = freeze(a.base)
    elif a.command == "numeric":
        r = numeric(a.base)
    else:
        r = evaluate(a.base)
        if a.command == "evaluate":
            write_new(a.base / "evaluation.json", r)
        else:
            require(r == read_json(a.base / "evaluation.json"), "derived score replay")
            write_new(
                a.base / "audit.json",
                dict(
                    audit="PASS",
                    evaluation_sha256=sha256_file(a.base / "evaluation.json"),
                    raw_replays=486,
                    holdout_access=False,
                    runtime_promotion=False,
                ),
            )
    print(
        {
            k: r.get(k)
            for k in (
                "schema",
                "status",
                "audit",
                "eligible_for_next_fresh_quality_test",
            )
        }
    )

#!/usr/bin/env python3
"""Fit sealed class confidence vectors, numerically check, then regress development."""

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from itertools import islice
from pathlib import Path
import sys
import tempfile
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import numpy as np
from physical_ai.perception.class_calibration_v1 import (
    CLASS_ORDER,
    GRID,
    decode,
    from_counts,
    search,
)
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import RgbDataset, read_json
from physical_ai.perception.model_screen_v2 import ScreenDetector
from analyze_model_diagnostics_v1 import check_freeze as check_diagnostic
from check_model_screen_v1 import PROBES, compare_detections, compare_top300
from quality_benchmark_v3 import measure, validate_truth
from run_model_screen_v1 import add, counts, require, validate_development, write_new
from run_model_screen_v2 import validate_run

ROOT = Path(__file__).resolve().parents[3]
V2 = ROOT / "build/m10-model-screen-v2"
DIAG = ROOT / "build/m10-model-diagnostics-v1"
MODELS = ("dfine-m", "rtv4-s")
SOURCES = (
    "physical_ai/perception/class_calibration_v1.py",
    "tests/integration/perception/run_class_calibration_v1.py",
    "tests/integration/perception/test_class_calibration_v1.py",
    "profiles/perception-class-calibration-grid-v1.json",
    "docs/test-plan/perception-class-calibration-v1-protocol.md",
)


def freeze(output):
    old = check_diagnostic(DIAG / "freeze.json")
    grid = read_json(ROOT / SOURCES[3])
    require(
        grid["schema"] == "m10-class-calibration-grid-v1"
        and grid["models"] == list(MODELS)
        and grid["class_order"] == list(CLASS_ORDER)
        and grid["threshold_grid"] == list(GRID)
        and grid["vectors_per_model"] == 15625,
        "predeclared search grid",
    )
    inputs, sources = dict(old["inputs"]), dict(old["sources"])
    paths = [
        V2 / "models.json",
        DIAG / "freeze.json",
        DIAG / "analysis.json",
        DIAG / "audit.json",
        DIAG / "mask-annex/review.json",
        V2 / "reference-rgb/reference.json",
        PROBES,
    ]
    for candidate in MODELS:
        paths.extend(V2 / "reference-rgb" / f"{candidate}-{n}.npz" for n in range(3))
    for source, _ in islice(RgbDataset(PROBES).frames(), 3):
        paths.append(PROBES.parent / source["rgb_path"])
    for path in paths:
        inputs[str(path.relative_to(ROOT))] = sha256_file(path)
    sources.update({name: sha256_file(ROOT / name) for name in SOURCES})
    result = dict(
        schema="m10-class-calibration-freeze-v1",
        created_utc=datetime.now(timezone.utc).isoformat(),
        sources=sources,
        inputs=inputs,
        candidates=list(MODELS),
        class_order=list(CLASS_ORDER),
        grid=list(GRID),
        vectors_per_model=15625,
        fit_frames=324,
        consumed_regression_frames=81,
        holdout_access=False,
        fresh_acceptance=False,
        runtime_promotion=False,
    )
    write_new(output, result)
    return result


def check_freeze(frozen):
    f = read_json(frozen)
    require(
        f["schema"] == "m10-class-calibration-freeze-v1"
        and f["candidates"] == list(MODELS)
        and f["class_order"] == list(CLASS_ORDER)
        and f["grid"] == list(GRID)
        and f["vectors_per_model"] == 15625
        and f["fit_frames"] == 324
        and f["consumed_regression_frames"] == 81
        and f["holdout_access"] is False
        and f["fresh_acceptance"] is False
        and f["runtime_promotion"] is False,
        "class calibration freeze/scope",
    )
    for name, digest in {**f["sources"], **f["inputs"]}.items():
        path = ROOT / name
        require(
            path.resolve().is_relative_to(ROOT) and sha256_file(path) == digest,
            "class calibration frozen file changed: " + name,
        )
    return f


def baseline(group):
    if group == "calibration":
        return next(
            s
            for s in read_json(V2 / "selection.json")["candidates"]["yolox-s"]["grid"]
            if s["threshold"] == 0.35
        )
    return read_json(V2 / "check.json")["candidates"]["yolox-s"]["common"]


def points(candidate):
    original = read_json(V2 / "freeze.json")
    chosen = read_json(V2 / "selection.json")["candidates"][candidate]
    run = validate_run(
        original,
        V2 / "freeze.json",
        V2 / "runs" / candidate / "calibration/run.json",
        "calibration",
    )
    metadata = [
        (key, scene)
        for key, spec in original["datasets"]["calibration"].items()
        for scene in read_json(ROOT / spec["path"] / "benchmark.json")["scenes"]
    ]
    require(len(metadata) == len(run["rows"]) == 324, "point table frame denominator")
    result = {}
    for threshold in GRID:
        point = next(s for s in chosen["grid"] if s["threshold"] == threshold)
        negative, negative_frames, errors = Counter(), 0, 0
        for (key, scene), row in zip(metadata, run["rows"]):
            require(
                row["dataset"] == key and row["scene"] == scene["scene"],
                "point table row identity",
            )
            p = row["predictions"][str(threshold)]
            errors += int(not p["valid"])
            require(
                row["predictions"]["0.35"]["valid"]
                and len(row["predictions"]["0.35"]["detections"]) <= 100,
                "base list capacity",
            )
            if scene["stratum"] == "negative":
                negative_frames += 1
                negative.update(d["class_id"] for d in p["detections"] or [])
        require(
            errors == point["errors"]
            and sum(negative.values()) == point["strata"]["negative"]["fp"],
            "point table primary negative/error counts",
        )
        result[str(threshold)] = dict(
            per_class=point["per_class"],
            near_person=point["near_person"],
            negative_fp_by_class={str(c): negative[c] for c in CLASS_ORDER},
            negative_frames=negative_frames,
            errors=errors,
        )
    return result


def evaluate(candidate, group, vector):
    original = read_json(V2 / "freeze.json")
    run_path = V2 / "runs" / candidate / group / "run.json"
    run = validate_run(original, V2 / "freeze.json", run_path, group)
    aggregate, near = counts(), dict(tp=0, fp=0, fn=0)
    negative = negative_frames = errors = position = 0
    rows = []
    for key, spec in original["datasets"][group].items():
        rgb, metadata, truth = validate_development(ROOT / spec["path"])
        for source, scene, gt in zip(
            rgb.manifest["frames"], metadata["scenes"], truth["frames"]
        ):
            row = run["rows"][position]
            position += 1
            require(
                row["dataset"] == key
                and row["scene"] == source["scene"] == scene["scene"] == gt["scene"]
                and row["frame"] == source["frame"] == gt["frame"]
                and row["source_ns"] == source["source_ns"]
                and row["rgb_sha256"] == source["rgb_sha256"],
                "mixed-vector row lineage",
            )
            validate_truth(gt)
            try:
                cache = run_path.parent / row["raw"]
                require(
                    sha256_file(cache) == row["raw_sha256"],
                    "mixed-vector raw integrity",
                )
                with np.load(cache, allow_pickle=False) as data:
                    predictions = [asdict(d) for d in decode(dict(data), vector)]
                error = None
            except Exception:
                predictions, error = None, traceback.format_exc()
                errors += 1
            values, _, _, _, _ = measure(
                predictions or [], gt["objects"], gt["excluded"]
            )
            add(aggregate, values)
            if scene["stratum"] == "near" and scene["target_class"] == 0:
                for metric in near:
                    near[metric] += values["0"][metric]
            if scene["stratum"] == "negative":
                negative_frames += 1
                negative += sum(values[str(c)]["fp"] for c in CLASS_ORDER)
            rows.append(
                dict(
                    dataset=key,
                    scene=source["scene"],
                    frame=source["frame"],
                    source_ns=source["source_ns"],
                    rgb_sha256=source["rgb_sha256"],
                    valid=error is None,
                    predictions=predictions,
                    error=error,
                    counts=values,
                )
            )
    metrics = from_counts(
        vector, aggregate, near, negative, negative_frames, errors, baseline(group)
    )
    return dict(
        candidate=candidate,
        group=group,
        frames=position,
        errors=errors,
        metrics=metrics,
        per_class=aggregate,
        near_person=near,
        rows=rows,
        runtime_promotion=False,
        fresh_acceptance=False,
    )


def fit(frozen, output):
    check_freeze(frozen)
    result = dict(
        schema="m10-class-calibration-selection-v1",
        freeze_sha256=sha256_file(frozen),
        candidates={},
        fit_frames=324,
        regression_already_consumed=True,
        holdout_access=False,
        fresh_acceptance=False,
        runtime_promotion=False,
    )
    for candidate in MODELS:
        point_table = points(candidate)
        found = search(point_table, baseline("calibration"))
        direct = evaluate(candidate, "calibration", found["selected"]["vector"])
        require(
            direct["metrics"] == found["selected"],
            "class separability against direct primary scorer",
        )
        result["candidates"][candidate] = dict(
            point_table=point_table, search=found, calibration=direct
        )
    result["created_utc"] = datetime.now(timezone.utc).isoformat()
    write_new(output, result)
    return result


def numeric(frozen, selection, output):
    check_freeze(frozen)
    chosen = read_json(selection)
    require(chosen["freeze_sha256"] == sha256_file(frozen), "numeric selection binding")
    models = read_json(V2 / "models.json")
    references = read_json(V2 / "reference-rgb/reference.json")
    probes = list(islice(RgbDataset(PROBES).frames(), 3))
    result = dict(
        status="PASS",
        rows=[],
        failures=[],
        freeze_sha256=sha256_file(frozen),
        selection_sha256=sha256_file(selection),
    )
    for candidate in MODELS:
        try:
            cpu, cuda = [
                ScreenDetector(candidate, ROOT / models[candidate], mode)
                for mode in ("cpu", "cuda")
            ]
            vector = chosen["candidates"][candidate]["search"]["selected"]["vector"]
            for index, (source, frame) in enumerate(probes):
                reference = next(
                    r
                    for r in references["rows"]
                    if r["candidate"] == candidate and r["probe"] == index
                )
                require(
                    reference["rgb_sha256"] == source["rgb_sha256"],
                    "numeric probe identity",
                )
                feed = cpu.prepare(frame)
                names = [o.name for o in cpu.session.get_outputs()]
                actual = [
                    dict(zip(names, backend.session.run(None, feed)))
                    for backend in (cpu, cuda)
                ]
                with np.load(
                    V2 / "reference-rgb" / f"{candidate}-{index}.npz",
                    allow_pickle=False,
                ) as data:
                    expected = dict(data)
                deltas = [compare_top300(expected, actual[0]), compare_top300(*actual)]
                for test_vector in [list([t] * 6) for t in GRID] + [vector]:
                    decoded = [
                        [asdict(d) for d in decode(raw, test_vector)]
                        for raw in [expected, *actual]
                    ]
                    compare_detections(decoded[0], decoded[1])
                    compare_detections(decoded[1], decoded[2])
                result["rows"].append(
                    dict(
                        candidate=candidate,
                        probe=index,
                        rgb_sha256=source["rgb_sha256"],
                        status="PASS",
                        full300_deltas=deltas,
                        scalar_points=list(GRID),
                        selected_vector=vector,
                    )
                )
            del cpu, cuda
        except Exception:
            result["status"] = "FAIL"
            result["failures"].append(
                dict(candidate=candidate, error=traceback.format_exc())
            )
    require(
        len(result["rows"]) == 6 or result["status"] == "FAIL", "numeric denominator"
    )
    write_new(output, result)
    return result


def regress(frozen, selection, numeric_path, output):
    check_freeze(frozen)
    chosen, checked = read_json(selection), read_json(numeric_path)
    require(
        chosen["freeze_sha256"] == sha256_file(frozen)
        and checked["status"] == "PASS"
        and not checked["failures"]
        and len(checked["rows"]) == 6
        and checked["selection_sha256"] == sha256_file(selection),
        "mixed-vector numeric/selection seal",
    )
    result = dict(
        schema="m10-class-calibration-regression-v1",
        created_utc=datetime.now(timezone.utc).isoformat(),
        freeze_sha256=sha256_file(frozen),
        selection_sha256=sha256_file(selection),
        numeric_sha256=sha256_file(numeric_path),
        candidates={},
        scope="Already consumed Town04 development regression; not independent acceptance",
        holdout_access=False,
        fresh_acceptance=False,
        runtime_promotion=False,
    )
    for candidate in MODELS:
        vector = chosen["candidates"][candidate]["search"]["selected"]["vector"]
        result["candidates"][candidate] = evaluate(candidate, "check", vector)
    write_new(output, result)
    return result


def audit(frozen, selection, numeric_path, regression, output):
    f = check_freeze(frozen)
    chosen, checked = read_json(selection), read_json(regression)
    with tempfile.TemporaryDirectory() as directory:
        recalculated = fit(frozen, Path(directory) / "fit.json")
        require(
            recalculated["candidates"] == chosen["candidates"],
            "all search scorecards and direct calibration replay",
        )
        replayed = regress(
            frozen, selection, numeric_path, Path(directory) / "regression.json"
        )
        require(
            replayed["candidates"] == checked["candidates"],
            "consumed regression raw/score replay",
        )
    result = dict(
        status="PASS",
        source_root=str(ROOT),
        sources=len(f["sources"]),
        scorecards=31250,
        selected_raw_replays=810,
        freeze_sha256=sha256_file(frozen),
        selection_sha256=sha256_file(selection),
        regression_sha256=sha256_file(regression),
        holdout_access=False,
        fresh_acceptance=False,
        runtime_promotion=False,
    )
    write_new(output, result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("freeze", "fit", "numeric", "regress", "audit")
    )
    for key in ("freeze", "selection", "numeric", "regression"):
        parser.add_argument("--" + key, type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "freeze":
        result = freeze(args.output)
    elif args.action == "fit":
        result = fit(args.freeze, args.output)
    elif args.action == "numeric":
        result = numeric(args.freeze, args.selection, args.output)
    elif args.action == "regress":
        result = regress(args.freeze, args.selection, args.numeric, args.output)
    else:
        result = audit(
            args.freeze, args.selection, args.numeric, args.regression, args.output
        )
    print(result.get("status", "PASS"))
    if result.get("status") == "FAIL":
        sys.exit(1)

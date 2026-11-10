#!/usr/bin/env python3
"""Freeze, cache, calibrate, then check pretrained models on consumed development."""

import argparse
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import resource
import sys
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import numpy as np
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import RgbDataset, read_json
from physical_ai.perception.model_screen_v2 import (
    CANDIDATES,
    REGISTRY,
    THRESHOLDS,
    ScreenDetection,
    ScreenDetector,
    decode,
)
from physical_ai.perception.provenance import runtime_identity
from physical_ai.perception.run import distribution
from quality_benchmark import total
from quality_benchmark_v3 import measure, validate_truth
from evaluate import rates
from run_model_screen_v1 import (
    DATASETS,
    add,
    counts,
    require,
    validate_development,
    write_new,
)

ROOT = Path(__file__).resolve().parents[3]
GROUPS = {
    "calibration": DATASETS,
    "check": {"v8": "build/m10-quality-v8/development-data"},
}


def freeze(output, numeric):
    checked = read_json(numeric)
    require(
        checked["status"] == "PASS"
        and not checked["failures"]
        and {(r["candidate"], r["probe"]) for r in checked["rows"]}
        == {(c, i) for c in CANDIDATES for i in range(3)}
        and all(
            r["status"] == "PASS" and r["thresholds"] == list(THRESHOLDS)
            for r in checked["rows"]
        ),
        "complete numeric checks required",
    )
    datasets, seen = {}, set()
    for group, paths in GROUPS.items():
        datasets[group] = {}
        for key, relative in paths.items():
            rgb, _, _ = validate_development(ROOT / relative)
            hashes = [source["rgb_sha256"] for source, _ in rgb.frames()]
            require(
                len(hashes) == len(set(hashes)) == 81 and not seen.intersection(hashes),
                "duplicate screen RGB",
            )
            seen.update(hashes)
            datasets[group][key] = dict(
                path=relative,
                rgb_sha256=hashes,
                files={
                    name: sha256_file(ROOT / relative / name)
                    for name in (
                        "rgb.json",
                        "evaluation-only-gt.json",
                        "benchmark.json",
                        "benchmark-seal.json",
                    )
                },
            )
    sources = set()
    for pattern in (
        "physical_ai/perception/*.py",
        "tests/integration/perception/*.py",
        "third_party/pretrained-screen-v2/**/*",
        "third_party/rtdetr-screen-v1/**/*",
    ):
        sources.update(
            p
            for p in ROOT.glob(pattern)
            if p.is_file() and "__pycache__" not in p.parts
        )
    sources.update(
        [
            REGISTRY,
            ROOT / "profiles/perception-host-v1.json",
            ROOT / "profiles/perception-cuda-host-v1.json",
            ROOT / "profiles/perception-model-screen-v1.json",
            ROOT / "docs/test-plan/perception-model-screen-v2-protocol.md",
            ROOT / "physical_ai/requirements-model-screen-v2.txt",
        ]
    )
    result = dict(
        schema="m10-pretrained-screen-freeze-v2",
        created_utc=datetime.now(timezone.utc).isoformat(),
        datasets=datasets,
        sources={str(p.relative_to(ROOT)): sha256_file(p) for p in sorted(sources)},
        numeric_check_sha256=sha256_file(numeric),
        registry_sha256=sha256_file(REGISTRY),
        candidates=list(CANDIDATES),
        thresholds=list(THRESHOLDS),
        frames=405,
        holdout_access=False,
        fresh_acceptance=False,
        runtime_promotion=False,
    )
    write_new(output, result)
    return result


def check_freeze(path):
    f = read_json(path)
    require(
        f["schema"] == "m10-pretrained-screen-freeze-v2"
        and f["frames"] == 405
        and f["candidates"] == list(CANDIDATES)
        and f["thresholds"] == list(THRESHOLDS)
        and f["holdout_access"] is False
        and f["fresh_acceptance"] is False
        and f["runtime_promotion"] is False,
        "screen freeze contract",
    )
    require(
        {g: {k: s["path"] for k, s in d.items()} for g, d in f["datasets"].items()}
        == GROUPS,
        "development dataset allowlist",
    )
    for name, digest in f["sources"].items():
        require(sha256_file(ROOT / name) == digest, "screen source changed: " + name)
    for paths in f["datasets"].values():
        for spec in paths.values():
            for name, digest in spec["files"].items():
                require(
                    sha256_file(ROOT / spec["path"] / name) == digest,
                    "screen data changed",
                )
    return f


def run(candidate, model_path, frozen, group, output):
    f = check_freeze(frozen)
    output.mkdir(parents=True, exist_ok=False)
    (output / "raw").mkdir()
    report = dict(
        schema="m10-pretrained-screen-run-v2",
        candidate=candidate,
        group=group,
        freeze_sha256=sha256_file(frozen),
        model_sha256=read_json(REGISTRY)["models"][candidate]["sha256"],
        rows=[],
        status="FAIL",
        runtime=runtime_identity(),
        cold_calls_excluded=0,
        board_execution=False,
        runtime_promotion=False,
        started_utc=datetime.now(timezone.utc).isoformat(),
    )
    begin = time.monotonic_ns()
    try:
        model = ScreenDetector(candidate, model_path)
        report.update(
            model_initialization_wall_ns=time.monotonic_ns() - begin,
            providers=model.session.get_providers(),
            provider_options=model.session.get_provider_options(),
            cpu_node_fallback_disabled=True,
        )
        for key, spec in f["datasets"][group].items():
            dataset = RgbDataset(ROOT / spec["path"] / "rgb.json")
            for source, camera in dataset.frames():
                row = {
                    k: source[k] for k in ("scene", "frame", "source_ns", "rgb_sha256")
                }
                row.update(dataset=key, predictions={}, raw=None)
                start = time.monotonic_ns()
                try:
                    raw, _, stages = model.infer(camera)
                    elapsed = time.monotonic_ns() - start
                    row.update(stages, elapsed_wall_ns=elapsed)
                    for threshold in THRESHOLDS:
                        decode_start = time.monotonic_ns()
                        try:
                            result = model.decode(raw, threshold)
                            row["predictions"][str(threshold)] = dict(
                                valid=True,
                                detections=[asdict(d) for d in result],
                                postprocess_ns=time.monotonic_ns() - decode_start,
                            )
                        except Exception as error:
                            row["predictions"][str(threshold)] = dict(
                                valid=False,
                                detections=None,
                                error=f"{type(error).__name__}: {error}",
                            )
                    cache = output / "raw" / f"{len(report['rows']):04d}.npz"
                    np.savez_compressed(cache, **raw)
                    row.update(
                        raw=str(cache.relative_to(output)),
                        raw_sha256=sha256_file(cache),
                    )
                except Exception:
                    row["error"] = traceback.format_exc()
                report["rows"].append(row)
        report["expected"] = 81 * len(f["datasets"][group])
        report["status"] = (
            "PASS"
            if len(report["rows"]) == report["expected"]
            and all(
                r["raw"] and r["predictions"]["0.35"]["valid"] for r in report["rows"]
            )
            else "FAIL"
        )
        report["common_threshold_latency"] = distribution(
            [r["elapsed_wall_ns"] for r in report["rows"] if "elapsed_wall_ns" in r]
        )
    except Exception:
        report["error"] = traceback.format_exc()
    report.update(
        wall_ns=time.monotonic_ns() - begin,
        peak_process_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        finished_utc=datetime.now(timezone.utc).isoformat(),
    )
    write_new(output / "run.json", report)
    return report


def validate_run(f, frozen, run_path, group):
    report = read_json(run_path)
    require(
        report["schema"] == "m10-pretrained-screen-run-v2"
        and report["group"] == group
        and report["candidate"] in CANDIDATES
        and report["freeze_sha256"] == sha256_file(frozen)
        and report["model_sha256"]
        == read_json(REGISTRY)["models"][report["candidate"]]["sha256"],
        "run provenance",
    )
    require(
        report["expected"] == len(report["rows"]) == 81 * len(f["datasets"][group])
        and report["providers"][0] == "CUDAExecutionProvider"
        and report["cpu_node_fallback_disabled"] is True
        and report["cold_calls_excluded"] == 0,
        "complete CUDA run required",
    )
    return report


def score(frozen, run_path, threshold, group, verify_raw=True):
    f = check_freeze(frozen)
    report = validate_run(f, frozen, run_path, group)
    require(threshold in THRESHOLDS, "threshold allowlist")
    aggregate, partitions = counts(), {}
    strata = defaultdict(lambda: dict(frames=0, tp=0, fp=0, fn=0))
    near = dict(tp=0, fp=0, fn=0)
    riders = dict(visible=0, detected=0)
    position = errors = 0
    post_ns, records = [], []
    family = read_json(REGISTRY)["models"][report["candidate"]]["family"]
    for key, spec in f["datasets"][group].items():
        rgb, meta, truth = validate_development(ROOT / spec["path"])
        subtotal = counts()
        for source, scene, gt in zip(
            rgb.manifest["frames"], meta["scenes"], truth["frames"]
        ):
            row = report["rows"][position]
            position += 1
            require(
                row["dataset"] == key
                and row["scene"] == source["scene"] == scene["scene"] == gt["scene"]
                and row["frame"] == source["frame"] == gt["frame"]
                and row["source_ns"] == source["source_ns"]
                and row["rgb_sha256"]
                == source["rgb_sha256"]
                == spec["rgb_sha256"][
                    position - 1 if group == "check" else (position - 1) % 81
                ],
                "run row lineage",
            )
            validate_truth(gt)
            prediction = row["predictions"].get(
                str(threshold),
                dict(valid=False, detections=None, error=row.get("error")),
            )
            require(type(prediction["valid"]) is bool, "prediction validity")
            if prediction["valid"]:
                require(
                    isinstance(prediction["detections"], list)
                    and len(prediction["detections"]) <= 100,
                    "prediction capacity",
                )
                for d in prediction["detections"]:
                    require(
                        set(d) == {"class_id", "score", "box"}
                        and d["score"] >= threshold,
                        "detection fields/threshold",
                    )
                    ScreenDetection(
                        d["class_id"], d["score"], tuple(d["box"])
                    ).validate()
                require(
                    type(prediction["postprocess_ns"]) is int
                    and prediction["postprocess_ns"] >= 0,
                    "postprocess timing",
                )
                post_ns.append(prediction["postprocess_ns"])
                if verify_raw:
                    cache = run_path.parent / row["raw"]
                    require(
                        cache.parent == run_path.parent / "raw"
                        and sha256_file(cache) == row["raw_sha256"],
                        "raw cache integrity",
                    )
                    with np.load(cache, allow_pickle=False) as data:
                        actual = [
                            asdict(d) for d in decode(dict(data), family, threshold)
                        ]
                    # JSON tuples become arrays; compare numeric arrays explicitly.
                    require(
                        len(actual) == len(prediction["detections"]), "raw replay count"
                    )
                    for a, b in zip(actual, prediction["detections"]):
                        require(
                            a["class_id"] == b["class_id"]
                            and a["score"] == b["score"]
                            and list(a["box"]) == b["box"],
                            "raw replay predictions",
                        )
            else:
                require(
                    prediction["detections"] is None and prediction.get("error"),
                    "failed frame encoded empty",
                )
                errors += 1
            values, matched, _, _, _ = measure(
                prediction["detections"] or [], gt["objects"], gt["excluded"]
            )
            add(subtotal, values)
            add(aggregate, values)
            stratum = strata[scene["stratum"]]
            stratum["frames"] += 1
            for k in ("tp", "fp", "fn"):
                stratum[k] += total(values)[k]
            if scene["stratum"] == "near" and scene["target_class"] == 0:
                for k in near:
                    near[k] += values["0"][k]
            for n, obj in enumerate(gt["objects"]):
                if 13 in obj["semantic_tags"]:
                    riders["visible"] += 1
                    riders["detected"] += int(n in matched)
            records.append(dict(dataset=key, scene=source["scene"], counts=values))
        partitions[key] = dict(micro=total(subtotal), per_class=rates(subtotal))
    micro, per_class = total(aggregate), rates(aggregate)
    for values in per_class.values():
        denominator = 2 * values["tp"] + values["fp"] + values["fn"]
        values["f1"] = 2 * values["tp"] / denominator if denominator else 0.0
    near["recall"] = near["tp"] / (near["tp"] + near["fn"])
    gates = dict(
        no_model_errors=errors == 0,
        precision=micro["precision"] >= 0.85,
        recall=micro["recall"] >= 0.8,
        per_class_recall=all(c["recall"] >= 0.7 for c in per_class.values()),
        near_person=near["recall"] >= 0.9,
        negative_fp=strata["negative"]["fp"] / strata["negative"]["frames"] <= 1 / 3,
    )
    return dict(
        candidate=report["candidate"],
        group=group,
        threshold=threshold,
        frames=position,
        errors=errors,
        micro=micro,
        per_class=per_class,
        macro_f1=sum(c["f1"] for c in per_class.values()) / 6,
        minimum_class_recall=min(c["recall"] for c in per_class.values()),
        near_person=near,
        riders=riders,
        strata=dict(strata),
        partitions=partitions,
        gates=gates,
        absolute_development_gates="PASS" if all(gates.values()) else "FAIL",
        postprocess_latency=distribution(post_ns) if post_ns else None,
        run_sha256=sha256_file(run_path),
        freeze_sha256=sha256_file(frozen),
        fresh_acceptance=False,
        runtime_promotion=False,
        records=records,
    )


def selection_key(score):
    return (
        score["absolute_development_gates"] == "PASS",
        score["macro_f1"],
        score["minimum_class_recall"],
        score["micro"]["f1"],
        score["threshold"],
    )


def calibrate(frozen, runs, output):
    check_freeze(frozen)
    result = dict(
        schema="m10-pretrained-screen-selection-v2",
        freeze_sha256=sha256_file(frozen),
        created_utc=datetime.now(timezone.utc).isoformat(),
        thresholds=list(THRESHOLDS),
        candidates={},
        holdout_access=False,
        check_scores_accessed=False,
        fresh_acceptance=False,
        runtime_promotion=False,
    )
    for candidate in CANDIDATES:
        run_path = runs / candidate / "calibration" / "run.json"
        scores = [
            score(frozen, run_path, t, "calibration", verify_raw=(t == 0.35))
            for t in THRESHOLDS
        ]
        selected = max(scores, key=selection_key)
        result["candidates"][candidate] = dict(
            threshold=selected["threshold"],
            calibration_run_sha256=sha256_file(run_path),
            selected=selected,
            grid=scores,
        )
    write_new(output, result)
    return result


def check_selected(frozen, runs, selection, output):
    f, chosen = check_freeze(frozen), read_json(selection)
    require(
        chosen["schema"] == "m10-pretrained-screen-selection-v2"
        and chosen["freeze_sha256"] == sha256_file(frozen)
        and chosen["check_scores_accessed"] is False
        and set(chosen["candidates"]) == set(CANDIDATES),
        "selection seal",
    )
    result = dict(
        schema="m10-pretrained-screen-check-v2",
        selection_sha256=sha256_file(selection),
        freeze_sha256=sha256_file(frozen),
        created_utc=datetime.now(timezone.utc).isoformat(),
        frames=81,
        candidates={},
        fresh_acceptance=False,
        runtime_promotion=False,
    )
    for candidate in CANDIDATES:
        choice = chosen["candidates"][candidate]
        calibration = runs / candidate / "calibration" / "run.json"
        require(
            sha256_file(calibration) == choice["calibration_run_sha256"]
            and choice["threshold"]
            == max(choice["grid"], key=selection_key)["threshold"],
            "calibration selection changed",
        )
        check_run = runs / candidate / "check" / "run.json"
        run_report = validate_run(f, frozen, check_run, "check")
        require(
            chosen["created_utc"] <= run_report["started_utc"],
            "check run started before selection seal",
        )
        result["candidates"][candidate] = dict(
            selected=score(frozen, check_run, choice["threshold"], "check"),
            common=score(frozen, check_run, 0.35, "check"),
        )
    baseline = result["candidates"]["yolox-s"]["common"]
    for values in result["candidates"].values():
        for score_value in values.values():
            relative = dict(
                precision_gain_3pp=score_value["micro"]["precision"]
                - baseline["micro"]["precision"]
                >= 0.03 - 1e-12,
                recall_gain_3pp=score_value["micro"]["recall"]
                - baseline["micro"]["recall"]
                >= 0.03 - 1e-12,
                no_class_recall_drop=all(
                    score_value["per_class"][c]["recall"]
                    >= baseline["per_class"][c]["recall"]
                    for c in baseline["per_class"]
                ),
            )
            score_value.update(
                relative_gates=relative,
                relative_development_gates="PASS" if all(relative.values()) else "FAIL",
            )
    write_new(output, result)
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("freeze", "run", "calibrate", "check"))
    p.add_argument("--freeze", type=Path)
    p.add_argument("--numeric", type=Path)
    p.add_argument("--models", type=Path)
    p.add_argument("--candidate", choices=CANDIDATES)
    p.add_argument("--group", choices=GROUPS)
    p.add_argument("--runs", type=Path)
    p.add_argument("--selection", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.action == "freeze":
        report = freeze(args.output, args.numeric)
    elif args.action == "run":
        report = run(
            args.candidate,
            ROOT / read_json(args.models)[args.candidate],
            args.freeze,
            args.group,
            args.output,
        )
    elif args.action == "calibrate":
        report = calibrate(args.freeze, args.runs, args.output)
    else:
        report = check_selected(args.freeze, args.runs, args.selection, args.output)
    print(report.get("status", "PASS"))
    if report.get("status") == "FAIL":
        sys.exit(1)

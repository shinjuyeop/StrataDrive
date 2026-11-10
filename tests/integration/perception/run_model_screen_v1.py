#!/usr/bin/env python3
"""Freeze, execute and score pretrained candidates on consumed DEVELOPMENT only."""

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
from physical_ai.perception.contract import Detection, sha256_file
from physical_ai.perception.dataset import RgbDataset, read_json
from physical_ai.perception.model_screen_v1 import CANDIDATES, REGISTRY, ScreenDetector
from physical_ai.perception.provenance import runtime_identity
from physical_ai.perception.run import distribution
from quality_benchmark import total
from quality_benchmark_v3 import measure, validate_truth
from evaluate import rates

ROOT = Path(__file__).resolve().parents[3]

DATASETS = {
    "v4": "build/m10-quality-v4g/development-data",
    "v5": "build/m10-quality-v5b/development-data",
    "v6": "build/m10-quality-v6/development-data",
    "v7": "build/m10-quality-v7/development-data",
}
CLASSES = (0, 1, 2, 3, 5, 7)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def write_new(path, value):
    import json

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")


def validate_development(data):
    meta = read_json(data / "benchmark.json")
    gt = read_json(data / "evaluation-only-gt.json")
    seal = read_json(data / "benchmark-seal.json")
    rgb = RgbDataset(data / "rgb.json")
    require(
        meta["partition"] == gt["partition"] == seal["partition"] == "development",
        "screen refuses holdout partition",
    )
    require(
        meta["rgb_manifest_sha256"]
        == gt["rgb_manifest_sha256"]
        == seal["rgb_manifest_sha256"]
        == sha256_file(rgb.path)
        and seal["truth_sha256"]
        == meta["truth_sha256"]
        == sha256_file(data / "evaluation-only-gt.json")
        and seal["metadata_sha256"] == sha256_file(data / "benchmark.json"),
        "development seal mismatch",
    )
    require(
        len(rgb.manifest["frames"]) == len(gt["frames"]) == len(meta["scenes"]) == 81,
        "development denominator",
    )
    return rgb, meta, gt


def freeze(output, numeric):
    check = read_json(numeric)
    require(check["status"] == "PASS", "numeric check required")
    datasets, seen = {}, set()
    for key, relative in DATASETS.items():
        data = ROOT / relative
        rgb, _, _ = validate_development(data)
        frames = list(rgb.frames())
        hashes = [r["rgb_sha256"] for r, _ in frames]
        require(
            len(hashes) == len(set(hashes)) == 81 and not seen.intersection(hashes),
            "screen RGB reused",
        )
        seen.update(hashes)
        datasets[key] = dict(
            path=relative,
            frames=81,
            rgb_sha256=hashes,
            files={
                name: sha256_file(data / name)
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
        "third_party/rtdetr-screen-v1/**/*",
        "third_party/nanodet-screen-v1/**/*",
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
            ROOT / "docs/test-plan/perception-model-screen-v1-protocol.md",
            ROOT / "physical_ai/requirements-host.txt",
            ROOT / "physical_ai/requirements-cuda-host.txt",
            ROOT / "physical_ai/requirements-model-screen-v1.txt",
        ]
    )
    report = dict(
        schema="m10-pretrained-screen-freeze-v1",
        created_utc=datetime.now(timezone.utc).isoformat(),
        scope="consumed development only; not fresh acceptance; board optimization deferred",
        candidates=list(CANDIDATES),
        datasets=datasets,
        sources={str(p.relative_to(ROOT)): sha256_file(p) for p in sorted(sources)},
        numeric_check_sha256=sha256_file(numeric),
        registry_sha256=sha256_file(REGISTRY),
        frames=324,
        holdout_access=False,
        runtime_promotion=False,
    )
    write_new(output, report)
    return report


def check_freeze(path):
    f = read_json(path)
    require(
        f["schema"] == "m10-pretrained-screen-freeze-v1"
        and f["candidates"] == list(CANDIDATES)
        and f["frames"] == 324
        and f["holdout_access"] is False
        and f["runtime_promotion"] is False,
        "screen freeze contract",
    )
    require(
        {k: v["path"] for k, v in f["datasets"].items()} == DATASETS,
        "screen dataset allowlist",
    )
    for name, digest in f["sources"].items():
        require(sha256_file(ROOT / name) == digest, "screen source changed: " + name)
    for spec in f["datasets"].values():
        for name, digest in spec["files"].items():
            require(
                sha256_file(ROOT / spec["path"] / name) == digest, "screen data changed"
            )
    return f


def run(candidate, model_path, frozen_path, output):
    f = check_freeze(frozen_path)
    report = dict(
        schema="m10-pretrained-screen-run-v1",
        candidate=candidate,
        status="FAIL",
        scope=f["scope"],
        freeze_sha256=sha256_file(frozen_path),
        started_utc=datetime.now(timezone.utc).isoformat(),
        expected=324,
        attempted=0,
        model_valid=0,
        admitted=0,
        errors=0,
        rows=[],
        runtime=runtime_identity(),
        cold_calls_excluded=0,
        board_execution=False,
        runtime_promotion=False,
        model_sha256=read_json(REGISTRY)["models"][candidate]["sha256"],
    )
    begin = time.monotonic_ns()
    try:
        model = ScreenDetector(candidate, model_path)
        report["model_initialization_wall_ns"] = time.monotonic_ns() - begin
        report["providers"] = model.session.get_providers()
        report["provider_options"] = model.session.get_provider_options()
        report["cpu_node_fallback_disabled"] = True
        for key, spec in f["datasets"].items():
            dataset = RgbDataset(ROOT / spec["path"] / "rgb.json")
            for source, camera in dataset.frames():
                row = {
                    k: source[k] for k in ("scene", "frame", "source_ns", "rgb_sha256")
                }
                row.update(
                    dataset=key, model_valid=False, admitted=False, detections=None
                )
                report["attempted"] += 1
                before = time.monotonic_ns()
                try:
                    detections, stages = model.infer(camera)
                    elapsed = time.monotonic_ns() - before
                    row.update(
                        stages,
                        model_valid=True,
                        admitted=elapsed < 100_000_000,
                        elapsed_wall_ns=elapsed,
                        detections=[asdict(d) for d in detections],
                    )
                    report["model_valid"] += 1
                    report["admitted"] += int(row["admitted"])
                except Exception as error:
                    report["errors"] += 1
                    row.update(
                        error=f"{type(error).__name__}: {error}",
                        elapsed_wall_ns=time.monotonic_ns() - before,
                    )
                report["rows"].append(row)
        report["latency"] = distribution([r["elapsed_wall_ns"] for r in report["rows"]])
        report["after_first_latency"] = distribution(
            [r["elapsed_wall_ns"] for r in report["rows"][1:]]
        )
        report["status"] = (
            "PASS" if report["model_valid"] == 324 and not report["errors"] else "FAIL"
        )
    except Exception:
        report["error"] = traceback.format_exc()
    report["wall_ns"] = time.monotonic_ns() - begin
    report["peak_process_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report["finished_utc"] = datetime.now(timezone.utc).isoformat()
    write_new(output, report)
    return report


def counts():
    return {str(c): dict(tp=0, fp=0, fn=0) for c in CLASSES}


def add(dest, src):
    for c in dest:
        for k in dest[c]:
            dest[c][k] += src[c][k]


def score(frozen_path, run_path):
    f, report = check_freeze(frozen_path), read_json(run_path)
    require(
        report["schema"] == "m10-pretrained-screen-run-v1"
        and report["candidate"] in CANDIDATES
        and report["freeze_sha256"] == sha256_file(frozen_path)
        and report["model_sha256"]
        == read_json(REGISTRY)["models"][report["candidate"]]["sha256"],
        "screen run provenance",
    )
    require(
        report["attempted"] == len(report["rows"]) == report["expected"] == 324,
        "incomplete run cannot be scored",
    )
    require(
        report["providers"][0] == "CUDAExecutionProvider"
        and report["cpu_node_fallback_disabled"] is True,
        "screen CUDA execution",
    )
    aggregate, partitions = counts(), {}
    strata = defaultdict(lambda: dict(frames=0, tp=0, fp=0, fn=0))
    near_person = dict(tp=0, fp=0, fn=0)
    riders = dict(visible=0, detected=0)
    records = []
    position = valid = admitted = errors = 0
    for key, spec in f["datasets"].items():
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
                and row["rgb_sha256"] == source["rgb_sha256"],
                "screen row identity",
            )
            validate_truth(gt)
            require(
                type(row["model_valid"]) is bool
                and type(row["admitted"]) is bool
                and type(row["elapsed_wall_ns"]) is int
                and row["elapsed_wall_ns"] >= 0,
                "screen row validity",
            )
            if row["model_valid"]:
                require(
                    isinstance(row["detections"], list)
                    and len(row["detections"]) <= 100
                    and row["admitted"] == (row["elapsed_wall_ns"] < 100_000_000),
                    "screen admission",
                )
                stages = [
                    row[k] for k in ("preprocess_ns", "inference_ns", "postprocess_ns")
                ]
                require(
                    all(type(v) is int and v >= 0 for v in stages)
                    and sum(stages) <= row["elapsed_wall_ns"],
                    "screen stage timing",
                )
                for d in row["detections"]:
                    require(
                        set(d) == {"class_id", "score", "box"},
                        "screen detection fields",
                    )
                    Detection(d["class_id"], d["score"], tuple(d["box"])).validate()
                valid += 1
                admitted += row["admitted"]
            else:
                require(
                    row["detections"] is None
                    and row.get("error")
                    and not row["admitted"],
                    "screen error encoded as empty",
                )
                errors += 1
            values, matched, _, _, _ = measure(
                row["detections"] or [], gt["objects"], gt["excluded"]
            )
            add(subtotal, values)
            add(aggregate, values)
            s = strata[scene["stratum"]]
            s["frames"] += 1
            for k in ("tp", "fp", "fn"):
                s[k] += total(values)[k]
            if scene["stratum"] == "near" and scene["target_class"] == 0:
                for k in near_person:
                    near_person[k] += values["0"][k]
            for n, obj in enumerate(gt["objects"]):
                if 13 in obj["semantic_tags"]:
                    riders["visible"] += 1
                    riders["detected"] += int(n in matched)
            records.append(dict(dataset=key, scene=source["scene"], counts=values))
        partitions[key] = dict(micro=total(subtotal), per_class=rates(subtotal))
    require(
        (valid, admitted, errors)
        == (report["model_valid"], report["admitted"], report["errors"])
        and report["status"] == ("PASS" if not errors else "FAIL"),
        "screen run counters",
    )
    micro, per_class = total(aggregate), rates(aggregate)
    near_person["recall"] = near_person["tp"] / (near_person["tp"] + near_person["fn"])
    gates = dict(
        no_model_errors=errors == 0,
        precision=micro["precision"] >= 0.85,
        recall=micro["recall"] >= 0.8,
        per_class_recall=all(c["recall"] >= 0.7 for c in per_class.values()),
        near_person=near_person["recall"] >= 0.9,
        negative_fp=strata["negative"]["fp"] / strata["negative"]["frames"] <= 1 / 3,
    )
    return dict(
        schema="m10-pretrained-screen-score-v1",
        candidate=report["candidate"],
        scope=f["scope"],
        frames=324,
        micro=micro,
        per_class=per_class,
        partitions=partitions,
        near_person=near_person,
        riders=riders,
        strata=dict(strata),
        gates=gates,
        absolute_development_gates="PASS" if all(gates.values()) else "FAIL",
        runtime_promotion=False,
        fresh_acceptance=False,
        run_sha256=sha256_file(run_path),
        freeze_sha256=sha256_file(frozen_path),
        records=records,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("freeze", "run", "score"))
    p.add_argument("--freeze", type=Path)
    p.add_argument("--numeric", type=Path)
    p.add_argument("--candidate", choices=CANDIDATES)
    p.add_argument("--model", type=Path)
    p.add_argument("--run", type=Path)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if a.action == "freeze":
        r = freeze(a.output, a.numeric)
    elif a.action == "run":
        r = run(a.candidate, a.model, a.freeze, a.output)
    else:
        r = score(a.freeze, a.run)
        write_new(a.output, r)
    print(
        {k: r[k] for k in ("status", "candidate", "frames", "micro", "gates") if k in r}
    )
    sys.exit(1 if r.get("status") == "FAIL" else 0)

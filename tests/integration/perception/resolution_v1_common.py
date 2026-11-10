"""Allowlisted development inputs and pre-inference resolution-study source freeze."""

from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import MODEL_SHA256, sha256_file
from physical_ai.perception.dataset import RgbDataset, read_json, local_path
from physical_ai.perception.resolution_v1 import (
    SIZES,
    VECTOR,
    ORIGINAL_ONNX_SHA,
    CHECKPOINT_SHA,
)
from run_model_screen_v1 import require, write_new

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "build/m10-resolution-v1"
PROBES = ROOT / "build/m10-quality-v9/preparation-development-data/rgb.json"
GROUPS = dict(
    selection={
        "v4": "build/m10-quality-v4g/development-data",
        "v5": "build/m10-quality-v5b/development-data",
        "v6": "build/m10-quality-v6/development-data",
        "v7": "build/m10-quality-v7/development-data",
        "v8": "build/m10-quality-v8/development-data",
    },
    regression={"v9": "build/m10-quality-v9/development-data"},
)
POLICY = ROOT / "profiles/perception-resolution-study-v1.json"
PROTOCOL = ROOT / "docs/test-plan/perception-resolution-v1-protocol.md"
META = ("rgb.json", "evaluation-only-gt.json", "benchmark.json", "benchmark-seal.json")


def safe_input(path):
    path = Path(path).resolve()
    require(
        path.is_relative_to(ROOT)
        and not any("holdout" in p.lower() for p in path.parts),
        "development allowlist refuses holdout input",
    )
    return path


def development(data):
    safe_input(data)
    meta = read_json(data / "benchmark.json")
    require(
        meta["partition"] == "development",
        "development reader refuses holdout partition",
    )
    truth, seal = (
        read_json(data / "evaluation-only-gt.json"),
        read_json(data / "benchmark-seal.json"),
    )
    require(
        truth["partition"] == seal["partition"] == "development",
        "GT/seal development partition",
    )
    rgb = RgbDataset(data / "rgb.json")
    require(
        meta["rgb_manifest_sha256"]
        == truth["rgb_manifest_sha256"]
        == seal["rgb_manifest_sha256"]
        == sha256_file(rgb.path)
        and meta["truth_sha256"]
        == seal["truth_sha256"]
        == sha256_file(data / "evaluation-only-gt.json")
        and seal["metadata_sha256"] == sha256_file(data / "benchmark.json"),
        "development seals",
    )
    require(
        len(rgb.manifest["frames"])
        == len(meta["scenes"])
        == len(truth["frames"])
        == 81,
        "development denominator",
    )
    return rgb, meta, truth


def freeze(base):
    policy = read_json(POLICY)
    require(
        policy["sizes"] == list(SIZES)
        and policy["confidence_vector"] == list(VECTOR)
        and policy["holdout_access"] is False
        and policy["training"] is False,
        "fixed policy",
    )
    inputs, datasets, seen = {}, {}, set()

    def bind(path):
        path = safe_input(path)
        inputs[str(path.relative_to(ROOT))] = sha256_file(path)

    for group, paths in GROUPS.items():
        datasets[group] = {}
        for key, relative in paths.items():
            data = ROOT / relative
            rgb, meta, truth = development(data)
            hashes = []
            for source, _ in rgb.frames():
                hashes.append(source["rgb_sha256"])
                bind(local_path(data, source["rgb_path"]))
            require(
                len(set(hashes)) == 81 and not seen.intersection(hashes),
                "distinct development RGB",
            )
            seen.update(hashes)
            for name in META:
                bind(data / name)
            datasets[group][key] = dict(path=relative, rgb_sha256=hashes)
    baseline = dict(selection=[], regression=[])
    original = ROOT / "build/m10-model-screen-v2"
    for group, oldgroup in (
        ("selection", "calibration"),
        ("selection", "check"),
        ("regression", None),
    ):
        path = (
            original / "runs/yolox-s" / oldgroup / "run.json"
            if oldgroup
            else ROOT / "build/m10-quality-v9/development-baseline/result.json"
        )
        report = read_json(path)
        require(
            report["status"] == "PASS"
            and report["cpu_node_fallback_disabled"] is True
            and report["cold_calls_excluded"] == 0
            and report["providers"][0] == "CUDAExecutionProvider",
            "original S native run",
        )
        require(report["model_sha256"] == MODEL_SHA256, "original S model")
        bind(path)
        for row in report["rows"]:
            raw = local_path(path.parent, row["raw"])
            require(sha256_file(raw) == row["raw_sha256"], "original S raw SHA")
            bind(raw)
            baseline[group].append(
                dict(
                    dataset=row.get("dataset", "v9"),
                    scene=row["scene"],
                    frame=row["frame"],
                    source_ns=row["source_ns"],
                    rgb_sha256=row["rgb_sha256"],
                    raw=str(raw.relative_to(ROOT)),
                    raw_sha256=row["raw_sha256"],
                    decoder="screen-v2" if oldgroup else "quality-v9",
                    elapsed_wall_ns=row["elapsed_wall_ns"],
                    admitted=row.get("admitted", row["elapsed_wall_ns"] < 100_000_000),
                    detections=row["predictions"]["0.35"]["detections"]
                    if oldgroup
                    else row["detections"],
                )
            )
    require(
        len(baseline["selection"]) == 405
        and len(baseline["regression"]) == 81
        and len(seen) == 486,
        "full development baseline",
    )
    write_new(base / "baseline-index.json", baseline)
    bind(base / "baseline-index.json")
    from itertools import islice

    bind(PROBES)
    for source, _ in islice(RgbDataset(PROBES).frames(), 3):
        bind(local_path(PROBES.parent, source["rgb_path"]))
    bind(ROOT / "build/m10-model-screen-v2/upstream/dfine-m.pth")
    bind(ROOT / "build/m10-model-screen-v2/upstream/dfine-m.onnx")
    old = read_json(ROOT / "build/m10-quality-v9/experiment-freeze.json")
    sources = dict(old["sources"])
    for name, digest in sources.items():
        require(sha256_file(ROOT / name) == digest, "prior source drift: " + name)
    extra = [
        POLICY,
        PROTOCOL,
        ROOT / "docs/test-plan/evidence/m10_quality_v8/survey-selected.json",
        ROOT
        / "docs/test-plan/evidence/m10_quality_v8/future-evaluation-exclusion.json",
    ]
    extra += list((ROOT / "physical_ai/perception").glob("*resolution_v1.py"))
    extra += list((ROOT / "tests/integration/perception").glob("*resolution_v1*.py"))
    sources.update({str(p.relative_to(ROOT)): sha256_file(p) for p in extra})
    report = dict(
        schema="m10-resolution-freeze-v1",
        created_utc=datetime.now(timezone.utc).isoformat(),
        groups=GROUPS,
        datasets=datasets,
        sources=sources,
        inputs=inputs,
        sizes=list(SIZES),
        vector=list(VECTOR),
        holdout_access=False,
        fresh_acceptance=False,
        runtime_promotion=False,
        training=False,
        new_rgb=False,
        future_rgb_exclusion=5449,
    )
    write_new(base / "freeze.json", report)
    return report


def check_freeze(path):
    f = read_json(path)
    require(
        f["schema"] == "m10-resolution-freeze-v1"
        and f["groups"] == GROUPS
        and f["sizes"] == list(SIZES)
        and f["vector"] == list(VECTOR)
        and all(
            f[k] is False
            for k in (
                "holdout_access",
                "fresh_acceptance",
                "runtime_promotion",
                "training",
                "new_rgb",
            )
        ),
        "resolution freeze scope",
    )
    for name, digest in f["sources"].items():
        require(sha256_file(ROOT / name) == digest, "frozen source drift: " + name)
    for name, digest in f["inputs"].items():
        require(
            sha256_file(safe_input(ROOT / name)) == digest,
            "frozen development input drift: " + name,
        )
    return f


def models(base):
    f = check_freeze(base / "freeze.json")
    m = read_json(base / "models.json")
    require(
        m["freeze_sha256"] == sha256_file(base / "freeze.json")
        and m["strict_state_load"] is True
        and m["checkpoint_sha256"] == CHECKPOINT_SHA
        and set(m["models"]) == set(map(str, SIZES)),
        "strict models manifest",
    )
    require(m["models"]["640"]["sha256"] == ORIGINAL_ONNX_SHA, "unchanged640 control")
    require(
        {(r["size"], r["probe"]) for r in m["references"]}
        == {(s, n) for s in SIZES for n in range(3)}
        and len(m["references"]) == 9,
        "native reference denominator",
    )
    for s, spec in m["models"].items():
        p = local_path(base, spec["path"])
        require(
            sha256_file(p) == spec["sha256"]
            and p.stat().st_size == spec["bytes"]
            and spec["size"] == int(s)
            and spec["geometry"]["nongeometric_state_sha256"]
            == m["nongeometric_state_sha256"],
            "model artifact/state identity",
        )
    for row in m["references"]:
        require(
            sha256_file(local_path(base, row["file"])) == row["sha256"],
            "native reference bytes",
        )
    return f, m


def check_numeric(base):
    _, m = models(base)
    n = read_json(base / "numeric.json")
    require(
        n["status"] == "PASS"
        and n["model_manifest_sha256"] == sha256_file(base / "models.json")
        and not n["failures"]
        and n["box_atol"] == 0.1
        and n["score_atol"] == 0.0001
        and n["cold_calls_excluded"] == 0
        and len(n["rows"]) == 9
        and {(r["size"], r["probe"]) for r in n["rows"]}
        == {(s, p) for s in SIZES for p in range(3)},
        "complete fixed numeric gate",
    )
    for r in n["rows"]:
        expected = next(
            x
            for x in m["references"]
            if (x["size"], x["probe"]) == (r["size"], r["probe"])
        )
        require(
            r["passed"] is True
            and r["rgb_sha256"] == expected["rgb_sha256"]
            and r["providers"][0] == "CUDAExecutionProvider",
            "numeric identity/CUDA",
        )
    return n

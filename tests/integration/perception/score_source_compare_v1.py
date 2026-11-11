#!/usr/bin/env python3
"""Matched2K/4K development scoring; all original inputs and predictions retained."""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
import time
import traceback
import hashlib

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import numpy as np
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import read_json
from physical_ai.perception.camera_resolution_v1 import (
    NativeDataset,
    NativeDetector,
    decode,
    prepare,
    unpack,
)
from physical_ai.perception.run import distribution
from source_compare_v1_common import check_freeze, save_derived, require, write_new
from run_resolution_v2 import quality, json_detections

ROOT = Path(__file__).resolve().parents[3]
MODEL = ROOT / "build/m10-resolution-v2/models/dfine-960.onnx"
MODELS = ROOT / "build/m10-resolution-v2/models.json"
PROFILE = ROOT / "profiles/perception-source-compare-v1.json"


def infer(base, run):
    check_freeze(base / "freeze.json")
    data = NativeDataset(run / "dataset/rgb.json")
    scale = data.scale
    require(
        data.manifest["phase"] == "comparison"
        and read_json(run / "dataset/acceptance.json")["status"] == "PASS",
        "accepted comparison",
    )
    out = base / f"comparison-{scale}-model"
    out.mkdir(exist_ok=False)
    (out / "raw").mkdir()
    report = dict(
        schema="m10-camera-model-run-v1",
        scale=scale,
        started_utc=datetime.now(timezone.utc).isoformat(),
        status="FAIL",
        rows=[],
        attempted=0,
        valid=0,
        admitted=0,
        errors=0,
        dataset_sha256=sha256_file(data.path),
        freeze_sha256=sha256_file(base / "freeze.json"),
        profile_sha256=sha256_file(PROFILE),
        cold_calls_excluded=0,
    )
    start = time.monotonic_ns()
    model = NativeDetector(960, MODEL, MODELS)
    report["initialization_wall_ns"] = time.monotonic_ns() - start
    report["providers"] = model.session.get_providers()
    report["provider_options"] = model.session.get_provider_options()
    report["cpu_node_fallback_disabled"] = True
    profile = read_json(PROFILE)
    if scale == 4:
        from physical_ai.perception.native_kernel_2k_v1 import NativeResize
        from physical_ai.perception.staged_kernel_2k_v1 import prepare_staged
        from physical_ai.perception.async_native_2k_v1 import BgraPacket
    else:
        from physical_ai.perception.native_kernel_v1 import NativeResize
        from physical_ai.perception.staged_kernel_v1 import prepare_staged
        from physical_ai.perception.async_native_v1 import BgraPacket
    import cv2

    cv2.setNumThreads(4)
    binding = profile["native_libraries"][str(scale)]
    resize = NativeResize((ROOT / binding["path"]).resolve(), binding["sha256"])
    for source, frame in data.frames():
        row = {k: source[k] for k in ("scene", "frame", "source_ns", "rgb_sha256")}
        row.update(valid=False, admitted=False, detections=None)
        report["attempted"] += 1
        begin = time.monotonic_ns()
        try:
            original = unpack(
                data.path.parent, source["rgb_raw"], frame.width, frame.height
            )
            packet = BgraPacket(frame.identity, original, begin)
            feed, _, _ = prepare_staged(resize, packet, {})
            expected = prepare(frame)
            for key in feed:
                np.testing.assert_array_equal(feed[key], expected[key])
            row["tensor_sha256"] = hashlib.sha256(feed["images"].tobytes()).hexdigest()
            prepared = time.monotonic_ns()
            raw = model.raw(feed)
            inferred = time.monotonic_ns()
            detections = decode(raw, scale)
            done = time.monotonic_ns()
            path = out / "raw" / f"{len(report['rows']):04d}.npz"
            np.savez_compressed(path, **raw)
            row.update(
                valid=True,
                admitted=done - begin < 100_000_000,
                detections=json_detections(detections),
                elapsed_wall_ns=done - begin,
                preprocess_ns=prepared - begin,
                inference_ns=inferred - prepared,
                postprocess_ns=done - inferred,
                raw=str(path.relative_to(out)),
                raw_sha256=sha256_file(path),
            )
            report["valid"] += 1
            report["admitted"] += int(row["admitted"])
        except Exception:
            row.update(
                error=traceback.format_exc(),
                elapsed_wall_ns=time.monotonic_ns() - begin,
            )
            report["errors"] += 1
        report["rows"].append(row)
    report.update(
        status="PASS" if report["attempted"] == report["valid"] == 81 else "FAIL",
        finished_utc=datetime.now(timezone.utc).isoformat(),
        latency=distribution([r["elapsed_wall_ns"] for r in report["rows"]]),
    )
    write_new(out / "run.json", report)
    return report


def score(base, run):
    check_freeze(base / "freeze.json")
    data = NativeDataset(run / "dataset/rgb.json")
    scale = data.scale
    list_sources = [s for s, _ in data.frames()]
    gt = read_json(run / "dataset/evaluation-only-gt.json")
    meta = read_json(run / "dataset/benchmark.json")
    result = read_json(base / f"comparison-{scale}-model/run.json")
    require(
        result["dataset_sha256"] == sha256_file(data.path)
        and result["freeze_sha256"] == sha256_file(base / "freeze.json")
        and result["profile_sha256"] == sha256_file(PROFILE)
        and result["providers"][0] == "CUDAExecutionProvider"
        and result["cpu_node_fallback_disabled"]
        and result["cold_calls_excluded"] == 0,
        "model provenance",
    )
    require(
        len(result["rows"])
        == len(list_sources)
        == len(gt["frames"])
        == len(meta["scenes"])
        == 81,
        "full comparison denominator",
    )
    rows = []
    valid = admitted = 0
    for source, truth, scene, row in zip(
        list_sources, gt["frames"], meta["scenes"], result["rows"]
    ):
        require(
            all(
                row[k] == source[k]
                for k in ("scene", "frame", "source_ns", "rgb_sha256")
            )
            and row["scene"] == truth["scene"] == scene["scene"],
            "comparison row identity",
        )
        raw = None
        pred = []
        if row["valid"]:
            path = base / f"comparison-{scale}-model" / row["raw"]
            require(sha256_file(path) == row["raw_sha256"], "native model raw hash")
            with np.load(path) as arrays:
                raw = dict(arrays)
            pred = json_detections(decode(raw, scale))
            require(
                pred == row["detections"]
                and row["admitted"] == (row["elapsed_wall_ns"] < 100_000_000),
                "raw decode/deadline",
            )
            valid += 1
            admitted += int(row["admitted"])
        else:
            require(
                row["detections"] is None and row.get("error") and not row["admitted"],
                "errors are not empty success",
            )
        rows.append((scene, truth, pred, row["valid"], row["admitted"], None))
    require(
        (valid, admitted, 81 - valid)
        == (result["valid"], result["admitted"], result["errors"]),
        "model denominator",
    )
    return dict(
        schema="m10-camera-source-score-v1",
        scale=scale,
        source_dimensions=[640 * scale, 384 * scale],
        run_sha256=sha256_file(base / f"comparison-{scale}-model/run.json"),
        runtime_promotion=False,
        **quality(rows),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    acceptance = save_derived(
        args.run / "dataset/capture.json", args.base / "freeze.json"
    )
    require(acceptance["status"] == "PASS", "all development targets visible")
    result = infer(args.base, args.run)
    scored = score(args.base, args.run)
    write_new(args.base / f"comparison-{result['scale']}-score.json", scored)
    print({"status": result["status"], "scale": result["scale"], "scores": scored})

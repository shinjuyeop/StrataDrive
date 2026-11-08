"""Actual ONNX replay, wall timing, tracking and optional typed C++ admission."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time
import traceback
import numpy as np
from .contract import (
    LIFETIME_NS,
    PROFILE_PATH,
    CUDA_PROFILE_PATH,
    MODEL_SHA256,
    sha256_file,
    execution_profile,
)
from .dataset import RgbDataset
from .replay import frame_line, run_boundary
from .tracking import ImageTracker
from .yolox import YoloX
from .provenance import runtime_identity


def distribution(samples):
    if not samples:
        return {"n": 0, "mean_ms": None, "p95_ms": None, "p99_ms": None, "max_ms": None}
    values = np.array(samples, dtype=np.float64) / 1e6
    return {
        "n": len(samples),
        "mean_ms": float(values.mean()),
        "p95_ms": float(np.percentile(values, 95)),
        "p99_ms": float(np.percentile(values, 99)),
        "max_ms": float(values.max()),
    }


def run(dataset_path, model_path, output, boundary=None, execution="cpu"):
    execution_profile(execution)
    output.mkdir(parents=True, exist_ok=False)
    report = {
        "status": "FAIL",
        "quality_acceptance": "NOT_SET",
        "wall_acceptance": "NOT_CLAIMED",
        "mode": "offline source-clock replay; independent wall processing qualification",
        "dataset_sha256": sha256_file(dataset_path),
        "profile_sha256": sha256_file(PROFILE_PATH),
        "model_sha256": MODEL_SHA256,
        "execution": execution,
        "execution_profile_sha256": sha256_file(CUDA_PROFILE_PATH)
        if execution == "cuda"
        else None,
        "python": sys.version,
        "platform": platform.platform(),
        "source_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "expected": 0,
        "attempted": 0,
        "model_valid": 0,
        "admitted": 0,
        "late": 0,
        "errors": 0,
        "rows": [],
    }
    started = time.monotonic_ns()
    usage_before = resource.getrusage(resource.RUSAGE_SELF)
    report["runtime"] = runtime_identity()
    try:
        import cv2
        import onnxruntime

        report["versions"] = {
            "numpy": np.__version__,
            "opencv": cv2.__version__,
            "onnxruntime": onnxruntime.__version__,
        }
        dataset = RgbDataset(dataset_path)
        report["expected"] = len(dataset.manifest["frames"])
        model = YoloX(model_path, execution=execution)
        tracker = ImageTracker()
        report["provider"] = model.session.get_providers()
        report["provider_options"] = model.session.get_provider_options()
        report["cpu_node_fallback_disabled"] = execution == "cuda"
        # No unreported warmup: first inference remains in the denominator.
        m = dataset.manifest
        boundary_lines = [f"S {m['epoch']} {m['clock_instance']} 0"]
        with (output / "predictions.jsonl").open("w") as predictions:
            for row, camera in dataset.frames():
                report["attempted"] += 1
                before = time.monotonic_ns()
                record = {
                    "frame": camera.identity.frame,
                    "source_ns": camera.identity.source_ns,
                    "scene": row["scene"],
                    "rgb_sha256": row["rgb_sha256"],
                    "model_valid": False,
                    "admitted": False,
                    "detections": None,
                    "tracks": [],
                }
                try:
                    result = model.infer(camera)
                    elapsed = time.monotonic_ns() - before
                    record.update(
                        model_valid=True,
                        detections=[asdict(d) for d in result.detections],
                        expires_ns=result.expires_ns,
                        preprocess_ns=result.preprocess_ns,
                        inference_ns=result.inference_ns,
                        postprocess_ns=result.postprocess_ns,
                        elapsed_wall_ns=elapsed,
                        admitted=elapsed < LIFETIME_NS,
                    )
                    report["model_valid"] += 1
                    line = frame_line(result, camera.identity.source_ns)
                    if record["admitted"]:
                        report["admitted"] += 1
                        record["tracks"] = [asdict(t) for t in tracker.update(result)]
                    else:
                        report["late"] += 1
                        fields = line.split()
                        fields[12] = "0"
                        line = " ".join(fields)
                    boundary_lines.append(line)
                except Exception as error:
                    report["errors"] += 1
                    record.update(
                        error=f"{type(error).__name__}: {error}",
                        elapsed_wall_ns=time.monotonic_ns() - before,
                    )
                    # An exception is a valid=false envelope, not a valid empty scene.
                    i = camera.identity
                    boundary_lines.append(
                        f"F {i.source_ns} 1 {i.epoch} {i.clock_instance} {i.frame} {i.source_ns} "
                        f"{i.source_ns + LIFETIME_NS} 1 1 640 384 0 {MODEL_SHA256} 0"
                    )
                predictions.write(json.dumps(record, allow_nan=False) + "\n")
                predictions.flush()
                report["rows"].append(record)
        if boundary:
            (output / "boundary-input.txt").write_text("\n".join(boundary_lines) + "\n")
            records = run_boundary(boundary, boundary_lines)
            (output / "boundary-output.json").write_text(
                json.dumps(records, indent=2) + "\n"
            )
            if not records[0]["accepted"]:
                raise ValueError("C++ INIT rejected")
            for prediction, received in zip(report["rows"], records[1:]):
                if (
                    received["accepted"] != prediction["admitted"]
                    or received["available"] != prediction["admitted"]
                ):
                    raise ValueError("C++ availability differs")
                if received["available"] and (
                    received["count"] != len(prediction["detections"])
                    or received["source_ns"] != prediction["source_ns"]
                    or received["expires_ns"] != prediction["expires_ns"]
                    or received["frame"] != prediction["frame"]
                ):
                    raise ValueError("C++ lineage/count differs")
            report["boundary"] = {
                "status": "PASS",
                "records": len(records) - 1,
                "binary_sha256": sha256_file(boundary),
            }
        if report["attempted"] != report["expected"]:
            raise ValueError("frame denominator")
        report["status"] = "PASS" if report["errors"] == 0 else "FAIL"
    except Exception:
        report["error"] = traceback.format_exc()
    finally:
        report["elapsed_wall_ns"] = time.monotonic_ns() - started
        usage_after = resource.getrusage(resource.RUSAGE_SELF)
        report["process_usage"] = {
            "peak_rss_kib": usage_after.ru_maxrss,
            "user_cpu_seconds": usage_after.ru_utime - usage_before.ru_utime,
            "system_cpu_seconds": usage_after.ru_stime - usage_before.ru_stime,
        }
        rows = report.pop("rows")
        report["latency"] = {
            name: distribution([r[name] for r in rows if name in r])
            for name in (
                "preprocess_ns",
                "inference_ns",
                "postprocess_ns",
                "elapsed_wall_ns",
            )
        }
        report["deadline_budget_ns"] = LIFETIME_NS
        report["model_outputs_per_wall_second"] = report["model_valid"] / (
            report["elapsed_wall_ns"] / 1e9
        )
        report["admitted_outputs_per_wall_second"] = report["admitted"] / (
            report["elapsed_wall_ns"] / 1e9
        )
        if (output / "predictions.jsonl").exists():
            report["predictions_sha256"] = sha256_file(output / "predictions.jsonl")
        (output / "result.json").write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n"
        )
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--boundary", type=Path)
    p.add_argument("--execution", choices=("cpu", "cuda"), default="cpu")
    args = p.parse_args()
    report = run(args.dataset, args.model, args.output, args.boundary, args.execution)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

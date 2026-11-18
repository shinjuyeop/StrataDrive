"""Score the fixed D-FINE and YOLOX-S pipelines on matched original 2K exposures."""

import argparse
import hashlib
import os
from pathlib import Path
import sys
import time

import cv2
import numpy as np
from PIL import Image
from fresh_quality_2k_review import BASE, ROOT, digest, read, rgb_bytes, write
from physical_ai.perception.async_native_2k_v1 import BgraPacket
from physical_ai.perception.camera_resolution_v1 import canonical, decode, unpack
from physical_ai.perception.contract import CameraFrame, FrameIdentity, sha256_file
from physical_ai.perception.cuda_resize_2k_v1 import CudaTensorKernelBackend
from physical_ai.perception.quality_candidates_v9 import (
    QualityCandidateV9,
    decode as decode_baseline,
)
from quality_benchmark import relative
from run_resolution_v2 import quality

PROTOCOL = ROOT / "profiles/perception-quality-protocol-v9.json"
MODEL = ROOT / "build/m10-resolution-v2/models/dfine-960.onnx"
BASELINE = ROOT / "build/m10-perception/yolox.onnx"


def predict(run, name):
    inputs = read(run / "images.json")
    if inputs["phase"] != "evaluation" or len(inputs["frames"]) != 81:
        raise ValueError("only full evaluation inputs can be scored")
    out = run / name
    out.mkdir(exist_ok=False)
    (out / "raw").mkdir()
    rows = []
    started = time.monotonic_ns()
    if name == "candidate":
        cuda = read(
            ROOT
            / "docs/test-plan/evidence/m10_cuda_resize_v1/component/release-manifest.json"
        )["library"]
        os.environ.update(
            STRATADRIVE_M10_CUDA_RESIZE_LIBRARY=cuda["path"],
            STRATADRIVE_M10_CUDA_RESIZE_SHA256=cuda["sha256"],
            STRATADRIVE_CUDA_BLOCKING_SYNC="1",
            STRATADRIVE_ORT_PASSIVE_THREADS="1",
        )
        cpu = read(ROOT / "profiles/perception-source-compare-v1.json")[
            "native_libraries"
        ]["4"]
        model = CudaTensorKernelBackend(
            MODEL,
            ROOT / "build/m10-resolution-v2/models.json",
            ROOT / cpu["path"],
            cpu["sha256"],
        )
        cv2.setNumThreads(4)
        original_raw = model.detector.raw
        captured = []

        def retain(feed):
            raw = original_raw(feed)
            captured.append(raw)
            return raw

        model.detector.raw = retain
    else:
        model = QualityCandidateV9(BASELINE, "baseline", "cuda")
    initialized = time.monotonic_ns()
    providers = model.detector.session.get_providers()
    if providers[0] != "CUDAExecutionProvider":
        raise ValueError("CUDA provider required")
    try:
        for index, source in enumerate(inputs["frames"]):
            identity = FrameIdentity(
                inputs["epoch"], inputs["world"], source["frame"], source["source_ns"]
            )
            raw = unpack(run / "dataset", source["rgb_raw"], 2560, 1536)
            rgb = rgb_bytes(raw)
            if hashlib.sha256(rgb).hexdigest() != source["rgb_sha256"]:
                raise ValueError("selected original RGB mismatch")
            row = {k: source[k] for k in ("scene", "frame", "source_ns", "rgb_sha256")}
            begin = time.monotonic_ns()
            try:
                if name == "candidate":
                    captured.clear()
                    result = model.infer(BgraPacket(identity, raw, begin))
                    (outputs,) = captured
                    detections = [
                        dict(
                            class_id=d.class_id,
                            score=d.score,
                            box=[v / 4 for v in d.box],
                        )
                        for d in result.detections
                    ]
                else:
                    reduced = Image.frombytes("RGB", (2560, 1536), rgb).resize(
                        (640, 384), Image.Resampling.BILINEAR
                    )
                    result, outputs = model.infer(
                        CameraFrame(identity, reduced.tobytes())
                    )
                    detections = [
                        dict(class_id=d.class_id, score=d.score, box=list(d.box))
                        for d in result.detections
                    ]
                elapsed = time.monotonic_ns() - begin
                path = out / "raw" / f"{index:03d}.npz"
                np.savez_compressed(path, **outputs)
                row.update(
                    valid=True,
                    elapsed_ns=elapsed,
                    detections=detections,
                    raw=str(path.relative_to(out)),
                    raw_sha256=sha256_file(path),
                )
            except Exception as error:
                row.update(
                    valid=False,
                    error=repr(error),
                    elapsed_ns=time.monotonic_ns() - begin,
                    detections=[],
                )
            rows.append(row)
    finally:
        if name == "candidate":
            model.close()
    report = dict(
        name=name,
        model_sha256=sha256_file(MODEL if name == "candidate" else BASELINE),
        providers=providers,
        initialization_ns=initialized - started,
        images_sha256=digest(run / "images.json"),
        freeze_sha256=digest(BASE / "freeze.json"),
        rows=rows,
    )
    write(out / "predictions.json", report)


def score(run, name):
    inputs = read(run / "images.json")["frames"]
    scenes = read(run / "benchmark.json")["scenes"]
    truth = read(run / "evaluation-only-gt.json")["frames"]
    out = run / name
    predictions = read(out / "predictions.json")
    if predictions["images_sha256"] != digest(run / "images.json") or predictions[
        "freeze_sha256"
    ] != digest(BASE / "freeze.json"):
        raise ValueError("prediction inputs or model freeze changed")
    if not len(predictions["rows"]) == len(inputs) == len(scenes) == len(truth) == 81:
        raise ValueError("full quality denominator")
    rows = []
    for actual, source, scene, gt in zip(predictions["rows"], inputs, scenes, truth):
        if not (
            all(
                actual[k] == source[k]
                for k in ("scene", "frame", "source_ns", "rgb_sha256")
            )
            and source["scene"] == scene["scene"] == gt["scene"]
            and source["frame"] == gt["frame"]
        ):
            raise ValueError("original image/prediction/truth association")
        raw = None
        decoded = []
        if actual["valid"]:
            path = out / actual["raw"]
            if sha256_file(path) != actual["raw_sha256"]:
                raise ValueError("original numerical output changed")
            with np.load(path, allow_pickle=False) as values:
                raw = {k: values[k] for k in values.files}
            decoded = (
                decode(raw, 4)
                if name == "candidate"
                else decode_baseline("baseline", raw)
            )
            if name == "candidate":
                raw = canonical(raw, 4)
            encoded = [
                dict(class_id=d.class_id, score=d.score, box=list(d.box))
                for d in decoded
            ]
            if encoded != actual["detections"]:
                raise ValueError("raw decoder replay mismatch")
        rows.append((scene, gt, actual["detections"], actual["valid"], False, raw))
    result = quality(rows)
    result.update(
        predictions_sha256=digest(out / "predictions.json"),
        labels_sha256=digest(run / "evaluation-only-gt.json"),
        timing_scope="Isolated quality only. No live control admissions.",
    )
    return result


def nomination(run):
    cards = {name: score(run, name) for name in ("baseline", "candidate")}
    comparison = relative(cards["baseline"], cards["candidate"], read(PROTOCOL))
    valid = all(
        r["valid"]
        for name in cards
        for r in read(run / name / "predictions.json")["rows"]
    )
    return dict(
        status="PASS"
        if valid
        and cards["candidate"]["absolute_quality"] == "PASS"
        and comparison["status"] == "PASS"
        else "FAIL",
        run=run.name,
        partition=read(run / "images.json")["partition"],
        candidate=sha256_file(MODEL),
        baseline=sha256_file(BASELINE),
        freeze_sha256=digest(BASE / "freeze.json"),
        visibility_sha256=digest(run / "visibility.json"),
        score_sha256={k: digest(run / k / "score.json") for k in cards},
        relative=comparison,
        absolute={k: v["absolute_quality"] for k, v in cards.items()},
    )


def verify_nomination():
    record = read(BASE / "nomination.json")
    run = BASE / "runs" / record["run"]
    if (
        run.parent.resolve() != (BASE / "runs").resolve()
        or record["status"] != "PASS"
        or record["partition"] != "development"
        or nomination(run) != record
    ):
        raise ValueError("valid pre-holdout development nomination required")
    return record


def evaluate(run):
    sys.path.insert(0, str(ROOT / "tools"))
    from m10_capture_fresh_quality import allow

    source = read(run / "images.json")
    allow("evaluation", source["partition"])
    if (
        source["phase"] != "evaluation"
        or read(run / "visibility.json")["status"] != "PASS"
    ):
        raise ValueError("accepted evaluation exposures required")
    if source["partition"] == "holdout" and read(run / "server.json")[
        "selection_sha256"
    ] != digest(BASE / "nomination.json"):
        raise ValueError("holdout acquisition must follow exact nomination")
    for name in ("candidate", "baseline"):
        predict(run, name)
        write(run / name / "score.json", score(run, name))
    result = nomination(run)
    write(run / "comparison.json", result)
    if source["partition"] == "development" and result["status"] == "PASS":
        write(BASE / "nomination.json", result)
    print(result, flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    result = evaluate(parser.parse_args().run)
    raise SystemExit(0 if result["status"] == "PASS" else 1)

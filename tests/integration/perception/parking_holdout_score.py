"""Predict from the frozen parking bundle and replay retained outputs against paired labels."""

import hashlib
import time

import numpy as np
from PIL import Image
from fresh_quality_2k_review import digest, read, rgb_bytes, write
from parking_onnx_replay import load_session
from physical_ai.perception.camera_resolution_v1 import unpack
from physical_ai.perception.parking_candidate import detections
from run_resolution_v2 import quality


def predict_candidate(run, bundle, output):
    images = read(run / "images.json")
    if images["phase"] != "evaluation" or len(images["frames"]) != 81:
        raise ValueError("full evaluation image list required")
    output.mkdir(parents=True, exist_ok=False)
    (output / "raw").mkdir()
    begin = time.monotonic_ns()
    session, spec = load_session(bundle)
    init_ns = time.monotonic_ns() - begin
    rows = []
    for i, frame in enumerate(images["frames"]):
        rgb = rgb_bytes(unpack(run / "dataset", frame["rgb_raw"], 2560, 1536))
        if hashlib.sha256(rgb).hexdigest() != frame["rgb_sha256"]:
            raise ValueError("original exposure changed")
        row = {k: frame[k] for k in ("scene", "frame", "source_ns", "rgb_sha256")}
        start = time.monotonic_ns()
        try:
            resized = Image.frombytes("RGB", (2560, 1536), rgb).resize(
                (960, 960), Image.Resampling.BILINEAR
            )
            tensor = np.ascontiguousarray(
                np.asarray(resized, np.float32).transpose(2, 0, 1)[None] / 255
            )
            raw = dict(
                zip(
                    spec["outputs"],
                    session.run(spec["outputs"], {"images": tensor}),
                    strict=True,
                )
            )
            pred = detections(raw, spec)
        except Exception as e:
            row.update(
                valid=False,
                error=repr(e),
                elapsed_ns=time.monotonic_ns() - start,
                detections=[],
            )
        else:
            elapsed = time.monotonic_ns() - start
            path = output / "raw" / f"{i:03d}.npz"
            np.savez_compressed(path, **raw)
            row.update(
                valid=True,
                elapsed_ns=elapsed,
                detections=pred,
                raw=str(path.relative_to(output)),
                raw_sha256=digest(path),
            )
        rows.append(row)
    write(
        output / "predictions.json",
        dict(
            images_sha256=digest(run / "images.json"),
            manifest_sha256=digest(bundle / "manifest.json"),
            model_sha256=spec["model_sha256"],
            providers=session.get_providers(),
            initialization_ns=init_ns,
            rows=rows,
        ),
    )


def replay_candidate(run, bundle, output):
    report = read(output / "predictions.json")
    spec = read(bundle / "manifest.json")
    images = read(run / "images.json")["frames"]
    scenes = read(run / "benchmark.json")["scenes"]
    labels = read(run / "evaluation-only-gt.json")["frames"]
    if (
        len(images) != 81
        or report["images_sha256"] != digest(run / "images.json")
        or report["manifest_sha256"] != digest(bundle / "manifest.json")
        or report["model_sha256"] != spec["model_sha256"]
    ):
        raise ValueError("model or evaluation identity changed")
    rows = []
    for row, frame, scene, gt in zip(
        report["rows"], images, scenes, labels, strict=True
    ):
        if (
            any(
                row[k] != frame[k]
                for k in ("scene", "frame", "source_ns", "rgb_sha256")
            )
            or not row["scene"] == scene["scene"] == gt["scene"]
            or gt["frame"] != row["frame"]
        ):
            raise ValueError("unpaired prediction")
        if row["valid"]:
            path = output / row["raw"]
            if digest(path) != row["raw_sha256"]:
                raise ValueError("retained numerical output changed")
            with np.load(path, allow_pickle=False) as raw:
                if detections(raw, spec) != row["detections"]:
                    raise ValueError("decoder did not reproduce the stored result")
        rows.append((scene, gt, row["detections"], row["valid"], False, None))
    return {k: v for k, v in quality(rows).items() if k != "records"}

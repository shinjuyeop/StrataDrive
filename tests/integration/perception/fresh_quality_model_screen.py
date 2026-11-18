"""Replay registered pretrained alternatives on consumed development images only."""

import argparse
import hashlib
from dataclasses import asdict
from pathlib import Path

import numpy as np
from PIL import Image

from fresh_quality_2k_review import BASE, ROOT, digest, read, rgb_bytes, write
from physical_ai.perception.camera_resolution_v1 import unpack
from physical_ai.perception.contract import CameraFrame, FrameIdentity
from physical_ai.perception.model_screen_v2 import ScreenDetector
from run_resolution_v2 import quality


def screen(output):
    run = BASE / "runs/evaluation-development-01"
    frames = read(run / "images.json")
    scenes, truth = (
        read(run / "benchmark.json")["scenes"],
        read(run / "evaluation-only-gt.json")["frames"],
    )
    paths = read(ROOT / "build/m10-model-screen-v2/models.json")
    candidates = ("yolox-l", "rtdetrv2-r18", "rtv4-s", "damo-s")
    if (
        frames["partition"] != "development"
        or not len(frames["frames"]) == len(scenes) == len(truth) == 81
    ):
        raise ValueError("complete original development exposure set required")
    output.mkdir(exist_ok=False)
    write(
        output / "declaration.json",
        dict(
            models={n: digest(ROOT / paths[n]) for n in candidates},
            source=digest(Path(__file__)),
            images=digest(run / "images.json"),
            configuration="Published 640x384 screen RGB input, registered preprocess, fixed .35 confidence; development only.",
        ),
    )
    cards = {}
    for name in candidates:
        detector = ScreenDetector(name, ROOT / paths[name])
        if detector.session.get_providers()[0] != "CUDAExecutionProvider":
            raise ValueError("CUDA provider required")
        directory = output / name
        directory.mkdir()
        (directory / "raw").mkdir()
        rows, reports = [], []
        for i, (frame, scene, gt) in enumerate(zip(frames["frames"], scenes, truth)):
            if not frame["scene"] == scene["scene"] == gt["scene"]:
                raise ValueError("scene identity")
            pixels = rgb_bytes(unpack(run / "dataset", frame["rgb_raw"], 2560, 1536))
            if hashlib.sha256(pixels).hexdigest() != frame["rgb_sha256"]:
                raise ValueError("original camera pixels")
            image = Image.frombytes("RGB", (2560, 1536), pixels).resize(
                (640, 384), Image.Resampling.BILINEAR
            )
            identity = FrameIdentity(
                frames["epoch"], frames["world"], frame["frame"], frame["source_ns"]
            )
            raw, predictions, timing = detector.infer(
                CameraFrame(identity, image.tobytes())
            )
            detections = [asdict(d) for d in predictions]
            path = directory / "raw" / f"{i:03}.npz"
            np.savez_compressed(path, **raw)
            reports.append(
                dict(
                    scene=frame["scene"],
                    rgb_sha256=frame["rgb_sha256"],
                    raw_sha256=digest(path),
                    raw=path.name,
                    detections=detections,
                    timing=timing,
                )
            )
            rows.append((scene, gt, detections, True, False, None))
        write(directory / "predictions.json", dict(rows=reports))
        card = quality(rows)
        cards[name] = {
            k: card[k]
            for k in (
                "micro",
                "per_class",
                "strata",
                "near_person",
                "gates",
                "absolute_quality",
            )
        }
        write(directory / "score.json", cards[name])
        print(name, cards[name]["micro"], flush=True)
        del detector
    write(output / "scores.json", cards)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("output", type=Path)
    screen(p.parse_args().output)

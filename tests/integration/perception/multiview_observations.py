"""Retain RGB-only multi-scale evidence; inference never reads labels or scene identity."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
from bus_recall import forward
from bus_recall_fit import infer as parent_infer
from person_pair_candidate import frames
from person_zoom_validation import CACHE
from person_proposal_diagnosis import BUNDLE, ROOT, read
from parking_onnx_replay import load_session
from fresh_quality_2k_review import rgb_bytes
from physical_ai.perception.camera_resolution_v1 import unpack

BUS = read(ROOT / "docs/test-plan/evidence/m10_bus_recall_v1/selection.json")["policy"]
CLASSES = (0, 1, 3, 5, 7)
# Subwindows cover the road corridor at two native scales. Full-frame views retain peripheral objects.
VIEWS = (
    ((0, 0, 1, 1, False), (0, 0, 1, 1, True))
    + tuple((x, 0.20, x + 0.5, 0.85, False) for x in (0, 0.25, 0.5))
    + tuple((x, 0.31, x + 0.30, 0.69, False) for x in (0, 0.175, 0.35, 0.525, 0.70))
)


def observe(image, session, spec):
    base, _ = parent_infer(image, session, spec, BUS)
    objects = []
    for view, (x1, y1, x2, y2, flip) in enumerate(VIEWS):
        left, top, right, bottom = map(
            round,
            (x1 * image.width, y1 * image.height, x2 * image.width, y2 * image.height),
        )
        sub = image.crop((left, top, right, bottom))
        if flip:
            sub = ImageOps.mirror(sub)
        raw = forward(sub, session, spec)
        for head, prefix in enumerate(("", "original_")):
            labels = raw[prefix + "labels"].ravel()
            scores = raw[prefix + "scores"].ravel()
            boxes = raw[prefix + "boxes"].reshape(-1, 4)
            for k in np.flatnonzero(np.isin(labels, CLASSES) & (scores >= 0.09)):
                box = boxes[k].clip([0, 0, 0, 0], [640, 384, 640, 384]).astype(float)
                if box[2] <= box[0] or box[3] <= box[1]:
                    continue
                if flip:
                    box[[0, 2]] = 640 - box[[2, 0]]
                # Reject detections clipped against an internal crop edge.
                if (
                    (left > 0 and box[0] < 2)
                    or (right < image.width and box[2] > 638)
                    or (top > 0 and box[1] < 2)
                    or (bottom < image.height and box[3] > 382)
                ):
                    continue
                box[[0, 2]] = (
                    left * 640 / image.width
                    + box[[0, 2]] * (right - left) / image.width
                )
                box[[1, 3]] = (
                    top * 384 / image.height
                    + box[[1, 3]] * (bottom - top) / image.height
                )
                objects.append(
                    [
                        view,
                        head,
                        int(labels[k]),
                        round(float(scores[k]), 6),
                        *np.round(box, 3).tolist(),
                    ]
                )
    return base, objects


def data(split, run=None):
    if run:
        images = read(run / "images.json")["frames"]
        for f, g, s in zip(
            images,
            read(run / "evaluation-only-gt.json")["frames"],
            read(run / "benchmark.json")["scenes"],
            strict=True,
        ):
            if not f["scene"] == g["scene"] == s["scene"]:
                raise ValueError("scene association")
            rgb = rgb_bytes(unpack(run / "dataset", f["rgb_raw"], 2560, 1536))
            yield (
                Image.frombytes("RGB", (2560, 1536), rgb),
                g,
                f["rgb_sha256"],
                s["scene"],
            )
    else:
        for paired in (True, False):
            if split == "validation" and paired:
                continue
            for path, g, key, meta in frames(CACHE, split, paired):
                # Keep all person, cycle and truck training examples, and a deterministic background sample.
                if (
                    split == "train"
                    and not paired
                    and not any(o["class_id"] in (0, 1, 3, 7) for o in g["objects"])
                    and int(key[:4], 16) % 6
                ):
                    continue
                with Image.open(path) as img:
                    yield img.convert("RGB"), g, key, ""


def trace(work, name, run=None):
    session, spec = load_session(BUNDLE)
    dest = work / (name + ".jsonl.gz")
    if dest.exists():
        raise FileExistsError(dest)
    tmp = dest.with_suffix(".partial")
    with gzip.open(tmp, "wt", compresslevel=3) as stream:
        for i, (img, g, key, scene) in enumerate(data(name, run)):
            if hashlib.sha256(img.tobytes()).hexdigest() != key:
                raise ValueError("RGB identity")
            base, obs = observe(img, session, spec)
            stream.write(
                json.dumps(
                    dict(
                        rgb=key,
                        scene=scene,
                        base=base,
                        obs=obs,
                        gt=g["objects"],
                        excluded=g["excluded"],
                    ),
                    separators=(",", ":"),
                )
                + "\n"
            )
            if i % 100 == 0:
                print(i, flush=True)
    tmp.rename(dest)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("work", type=Path)
    p.add_argument("name")
    p.add_argument("--run", type=Path)
    a = p.parse_args()
    trace(a.work, a.name, a.run)

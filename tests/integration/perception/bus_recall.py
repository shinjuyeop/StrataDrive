"""Trace both bus heads and truck competition on model-development RGB only."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from person_proposal_diagnosis import PARK, BUNDLE, MODEL, source_frames, read
from parking_onnx_replay import load_session
from person_pair_candidate import overlaps
from physical_ai.perception.parking_candidate import detections


def forward(image, session, spec):
    arr = np.asarray(image.resize((960, 960), Image.Resampling.BILINEAR), np.float32)
    x = np.ascontiguousarray(arr.transpose(2, 0, 1)[None] / 255)
    return dict(
        zip(spec["outputs"], session.run(spec["outputs"], {"images": x}), strict=True)
    )


def proposals(raw):
    evidence = []
    for prefix in ("original_", ""):
        labels = raw[prefix + "labels"].ravel()
        boxes = raw[prefix + "boxes"].reshape(-1, 4)
        scores = raw[prefix + "scores"].ravel()
        for n in np.flatnonzero((labels == 5) & (scores >= 0.05)):
            box = boxes[n].clip([0, 0, 0, 0], [640, 384, 640, 384])
            if (box[2:] <= box[:2]).any():
                continue
            support = {}
            for source in ("original_", ""):
                lab = raw[source + "labels"].ravel()
                adjacent = raw[source + "boxes"].reshape(-1, 4)
                confidence = raw[source + "scores"].ravel()
                iou = overlaps(np.array([box]), adjacent)[0]
                for cls, threshold in ((5, 0.4), (7, 0.7)):
                    support[("old" if source else "adapted") + str(cls)] = float(
                        confidence[(lab == cls) & (iou >= threshold)].max(initial=0)
                    )
            evidence.append(
                dict(
                    source=prefix or "adapted",
                    score=float(scores[n]),
                    box=box.tolist(),
                    **support,
                )
            )
    return evidence


def trace(out, split):
    session, spec = load_session(BUNDLE)
    if spec["model_sha256"] != MODEL:
        raise ValueError("parent")
    sources = source_frames(split)
    with gzip.open(out / (split + ".jsonl.gz"), "wt") as log:
        for item in read(PARK / "cache/manifest.json")[split]:
            sha = item["source"]
            path, gt, *_ = sources[sha]
            with Image.open(path) as img:
                image = img.convert("RGB")
            if hashlib.sha256(image.tobytes()).hexdigest() != sha:
                raise ValueError("pixels")
            raw = forward(image, session, spec)
            base = [d for d in detections(raw, spec) if d["class_id"] == 5]
            log.write(
                json.dumps(
                    dict(
                        rgb=sha,
                        site=item["site"],
                        base=base,
                        proposals=proposals(raw),
                        truth=[o["box"] for o in gt["objects"] if o["class_id"] == 5],
                    )
                )
                + "\n"
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("split", choices=("train", "validation"))
    args = parser.parse_args()
    trace(args.output, args.split)

"""Measure the final exported graph on the two validation groups without reselecting a model."""

import argparse
from pathlib import Path
import hashlib
from collections import defaultdict

import numpy as np
from PIL import Image
from fresh_quality_2k_review import ROOT, digest, read, write
from parking_onnx_replay import load_session
from physical_ai.perception.parking_candidate import detections
from quality_benchmark_v3 import measure


def inputs(root):
    prev = ROOT / "build/m10-occlusion-transfer-v1"
    files = {}
    for ds in (
        prev / "run-02/dataset",
        prev / "parked-03/dataset",
        root / "Town02_Opt-stock-02/dataset",
    ):
        for r in read(ds / "labels.json"):
            if r["split"] == "validation":
                files[r["rgb_sha256"]] = (ds / (r["id"] + ".png"), r)
    export = ROOT / "build/m10-domain-data-v1/export"
    info = read(export / "dataset.json")["splits"]["validation"]
    path = export / info["annotation_path"]
    if digest(path) != info["annotation_sha256"]:
        raise ValueError("validation annotation identity")
    coco = read(path)
    by_id = defaultdict(lambda: dict(objects=[], excluded=[]))
    for a in coco["annotations"]:
        x, y, w, h = a["bbox"]
        by_id[a["image_id"]][
            "objects" if a["m10_quality_eligible"] else "excluded"
        ].append(dict(class_id=a["category_id"] - 1, box=[x, y, x + w, y + h]))
    for r in coco["images"]:
        files[r["rgb_sha256"]] = (
            prev / "archived-training-images" / r["file_name"],
            by_id[r["id"]],
        )
    entries = read(root / "cache/manifest.json")["validation"]
    if set(files) != {e["source"] for e in entries}:
        raise ValueError("validation split mismatch")
    for entry in entries:
        yield entry, *files[entry["source"]]


def run(root, bundle, output):
    session, spec = load_session(bundle)
    groups = defaultdict(lambda: defaultdict(lambda: dict(tp=0, fp=0, fn=0)))
    counts = defaultdict(int)
    for entry, path, label in inputs(root):
        image = Image.open(path).convert("RGB")
        if hashlib.sha256(image.tobytes()).hexdigest() != entry["source"]:
            raise ValueError("source image changed")
        tensor = (
            np.asarray(
                image.resize((960, 960), Image.Resampling.BILINEAR), np.float32
            ).transpose(2, 0, 1)[None]
            / 255
        )
        raw = dict(
            zip(
                spec["outputs"],
                session.run(spec["outputs"], {"images": np.ascontiguousarray(tensor)}),
                strict=True,
            )
        )
        c = measure(detections(raw, spec), label["objects"], label["excluded"])[0]
        site = entry["site"]
        counts[site] += 1
        for cls, v in c.items():
            for k, n in v.items():
                groups[site][cls][k] += n
    summary = {}
    for site, classes in groups.items():
        tp, fp, fn = (sum(v[k] for v in classes.values()) for k in ("tp", "fp", "fn"))
        summary[site] = dict(
            images=counts[site],
            tp=tp,
            fp=fp,
            fn=fn,
            precision=tp / (tp + fp),
            recall=tp / (tp + fn),
            classes=classes,
        )
    write(output, dict(model=spec["model_sha256"], groups=summary))
    print(summary, flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    p.add_argument("bundle", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    run(a.root, a.bundle, a.output)

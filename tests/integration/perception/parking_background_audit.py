"""Relate unmatched development car detections to original same-frame instance pixels."""

import argparse
from collections import Counter
from pathlib import Path
import zlib

import numpy as np
from PIL import Image, ImageDraw
from evaluate import overlap
from fresh_quality_2k_review import BASE, digest, read, write
from occlusion_transfer_calibrate import detections


def audit(trial, selection, output):
    output.mkdir(exist_ok=False, parents=True)
    chosen = read(selection)["selected"]
    run = BASE / "runs/evaluation-development-01"
    truth = read(run / "evaluation-only-gt.json")["frames"]
    frames = read(run / "dataset/capture.json")["frames"]
    originals = read(trial / "development-predictions.json")
    rows = []
    pictures = []
    for i, (frame, gt, row) in enumerate(zip(frames, truth, originals, strict=True)):
        if frame["scene"] != gt["scene"] or row["scene"] != gt["scene"]:
            raise ValueError("original frame pairing")
        query = trial / "queries" / f"{i:03d}.npz"
        if digest(query) != row["queries_sha256"]:
            raise ValueError("query digest")
        with np.load(query, allow_pickle=False) as data:
            pred = detections(
                {k: data[k] for k in ("labels", "boxes", "scores")},
                chosen["threshold"],
                chosen["nms"],
            )

        def pixels(kind):
            packet = frame[kind]
            path = run / "dataset" / packet["path"]
            if digest(path) != packet["stored_sha256"]:
                raise ValueError("camera packet digest")
            return np.frombuffer(zlib.decompress(path.read_bytes()), np.uint8).reshape(
                1536, 2560, 4
            )

        tags = pixels("instance")[:, :, 2]
        used = set()
        for d in pred:
            if d["class_id"] != 2:
                continue
            boxes = [
                (overlap(d["box"], o["box"]), j)
                for j, o in enumerate(gt["objects"])
                if o["class_id"] == 2
            ]
            best = max(
                (a for a in boxes if a[1] not in used),
                default=(0, -1),
                key=lambda v: (v[0], -v[1]),
            )
            if best[0] >= 0.5:
                used.add(best[1])
                continue
            x, y, r, b = d["box"]
            crop = tags[
                int(y * 4) : int(np.ceil(b * 4)), int(x * 4) : int(np.ceil(r * 4))
            ]
            car_fraction = float((crop == 14).mean())
            small = max(
                (
                    overlap(d["box"], o["box"])
                    for o in gt["excluded"]
                    if o["class_id"] == 2
                ),
                default=0.0,
            )
            item = dict(
                scene=gt["scene"],
                box=d["box"],
                score=d["score"],
                car_pixel_fraction=car_fraction,
                majority_tag=int(np.bincount(crop.flatten()).argmax()),
                best_included_iou=max((a[0] for a in boxes), default=0.0),
                best_excluded_iou=small,
            )
            rows.append(item)
            if i in (0, 1, 2, 20) and len(pictures) < 12:
                rgb = Image.fromarray(pixels("rgb")[:, :, 2::-1].copy())
                region = (
                    max(0, int(4 * x) - 36),
                    max(0, int(4 * y) - 36),
                    min(2560, int(4 * r) + 36),
                    min(1536, int(4 * b) + 36),
                )
                draw = ImageDraw.Draw(rgb)
                draw.rectangle(
                    (4 * x, 4 * y, 4 * r, 4 * b), outline=(255, 70, 30), width=2
                )
                thumb = rgb.crop(region)
                thumb.thumbnail((240, 120))
                pictures.append(thumb)
    if not len(frames) == 81:
        raise ValueError("development denominator")
    low = [r for r in rows if r["best_included_iou"] < 0.1]
    write(
        output / "audit.json",
        dict(
            frames=81,
            car_fp=len(rows),
            low_overlap=len(low),
            zero_car_pixels=sum(r["car_pixel_fraction"] == 0 for r in low),
            overlaps_excluded_car=sum(r["best_excluded_iou"] >= 0.5 for r in low),
            low_overlap_majority_tags=dict(Counter(r["majority_tag"] for r in low)),
            rows=rows,
        ),
    )
    panel = Image.new("RGB", (240 * 3, 120 * ((len(pictures) + 2) // 3)), "white")
    for i, image in enumerate(pictures):
        panel.paste(image, (240 * (i % 3), 120 * (i // 3)))
    panel.save(output / "examples.jpg", quality=92)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("trial", "selection", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    audit(args.trial, args.selection, args.output)

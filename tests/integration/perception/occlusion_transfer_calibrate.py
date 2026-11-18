"""Select a finite car confidence/NMS configuration exclusively on the training validation split."""

import argparse
from pathlib import Path

import numpy as np
import torch
from occlusion_transfer_train import (
    BATCH,
    add_archived,
    digest,
    inputs,
    network,
    read,
    write,
)
from evaluate import overlap
from fresh_quality_2k_review import BASE
from physical_ai.perception.class_calibration_v1 import decode
from physical_ai.perception.resolution_car_v1 import VECTOR
from quality_benchmark_v3 import measure
from run_resolution_v2 import quality


def detections(raw, threshold, nms):
    vector = list(VECTOR)
    vector[2] = threshold
    decoded = decode(raw, vector)
    result = []
    cars = []
    for d in decoded:
        box = list(d.box)
        if d.class_id == 2:
            if nms is not None and any(overlap(box, b) > nms for b in cars):
                continue
            cars.append(box)
        result.append(dict(class_id=d.class_id, score=d.score, box=box))
    return result


def calibrate(base, archived, parent, out):
    out.mkdir(exist_ok=False)
    write(
        out / "protocol.json",
        dict(
            parent_sha256=digest(parent / "decoder.pt"),
            car_thresholds=[0.35, 0.4, 0.5, 0.6, 0.7],
            car_nms_iou=[None, 0.5, 0.65, 0.8],
            selection="Prioritize validation precision >= 85%, recall >= 80% and per-class recall >= 70% jointly, then validation recall, precision; first tie. All other class thresholds fixed.",
        ),
    )
    # Reuse only validation images from the independently declared training data.
    samples = inputs(base, set())
    add_archived(samples, archived)
    validation = samples["validation"]
    del samples
    model = network()
    if (
        digest(parent / "decoder.pt")
        != read(parent / "selection.json")["decoder_sha256"]
    ):
        raise ValueError("confidence candidate digest")
    model.detector.decoder.load_state_dict(
        torch.load(parent / "decoder.pt", weights_only=True)
    )
    cached = []
    with torch.inference_mode():
        for start in range(0, len(validation), BATCH):
            batch = validation[start : start + BATCH]
            images = torch.stack([image for image, _ in batch]).cuda().float() / 255
            sizes = torch.tensor([[640, 384]], device="cuda").expand(len(batch), 2)
            values = [v.cpu().numpy() for v in model(images, sizes)]
            for i, (_, r) in enumerate(batch):
                cached.append(
                    (
                        {
                            k: v[i : i + 1]
                            for k, v in zip(("labels", "boxes", "scores"), values)
                        },
                        r,
                    )
                )
    candidates = []
    for confidence in (0.35, 0.4, 0.5, 0.6, 0.7):
        for nms in (None, 0.5, 0.65, 0.8):
            counts = np.zeros((8, 3), dtype=np.int64)
            for raw, row in cached:
                result = measure(
                    detections(raw, confidence, nms), row["objects"], row["excluded"]
                )[0]
                for k, v in result.items():
                    counts[int(k)] += [v[t] for t in ("tp", "fp", "fn")]
            tp, fp, fn = map(int, counts.sum(axis=0))
            precision = tp / (tp + fp)
            recall = tp / (tp + fn)
            per_class = min(int(a) / (a + c) for a, _, c in counts if a + c)
            candidates.append(
                dict(
                    threshold=confidence,
                    nms=nms,
                    precision=precision,
                    recall=recall,
                    tp=tp,
                    fp=fp,
                    fn=fn,
                    minimum_class_recall=float(per_class),
                    gates=bool(
                        precision >= 0.85 and recall >= 0.8 and per_class >= 0.7
                    ),
                )
            )
    selected = max(candidates, key=lambda v: (v["gates"], v["recall"], v["precision"]))
    write(
        out / "selection.json",
        dict(validation_frames=len(cached), selected=selected, candidates=candidates),
    )
    run = BASE / "runs/evaluation-development-01"
    preds = read(parent / "development-predictions.json")
    scenes = read(run / "benchmark.json")["scenes"]
    truth = read(run / "evaluation-only-gt.json")["frames"]
    if not len(preds) == len(scenes) == len(truth) == 81:
        raise ValueError("development denominator")
    observations = []
    for i, (pred, s, g) in enumerate(zip(preds, scenes, truth)):
        path = parent / "queries" / f"{i:03d}.npz"
        if (
            digest(path) != pred["queries_sha256"]
            or not pred["scene"] == s["scene"] == g["scene"]
        ):
            raise ValueError("numerical output provenance")
        with np.load(path, allow_pickle=False) as data:
            result = detections(
                {k: data[k] for k in ("labels", "boxes", "scores")},
                selected["threshold"],
                selected["nms"],
            )
        observations.append((s, g, result, True, False, None))
    score = quality(observations)
    write(
        out / "development-score.json",
        {k: v for k, v in score.items() if k != "records"},
    )
    print(selected, score["micro"], score["gates"], flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for name in ("dataset", "archived", "parent", "output"):
        p.add_argument(name, type=Path)
    a = p.parse_args()
    torch.set_num_threads(4)
    calibrate(a.dataset, a.archived, a.parent, a.output)

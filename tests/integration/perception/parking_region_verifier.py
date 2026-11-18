"""Train and evaluate a region-based car verifier on road- and map-separated SIL images."""

import argparse
import hashlib
from pathlib import Path
import random
import numpy as np
import torch
from PIL import Image
from torch import nn
from torchvision.ops import box_convert, box_iou, nms, roi_align

from occlusion_transfer_train import (
    BASE,
    ROOT,
    add_archived,
    digest,
    inputs,
    network,
    read,
    rgb_bytes,
    tensor,
    unpack,
    write,
)
from occlusion_transfer_calibrate import detections
from quality_benchmark_v3 import measure
from run_resolution_v2 import quality

SEED = 51973
PREVIOUS = ROOT / "build/m10-occlusion-transfer-v1"
PARENT = PREVIOUS / "car-score-01"
THRESHOLDS = (0.35, 0.4, 0.5, 0.6, 0.7)
EPOCHS = 10
WIDTH = 640
HEIGHT = 384


def detector():
    if (
        digest(PARENT / "decoder.pt")
        != read(PARENT / "selection.json")["decoder_sha256"]
    ):
        raise ValueError("parent detector checkpoint")
    model = network()
    model.detector.decoder.load_state_dict(
        torch.load(PARENT / "decoder.pt", weights_only=True)
    )
    return model.requires_grad_(False)


def truth_boxes(row):
    return torch.tensor(
        [o["box"] for o in row["objects"] if o["class_id"] == 2], dtype=torch.float32
    ).reshape(-1, 4)


def jitter(truth, generator):
    # Matched objects, tight vehicle fragments, and padded/misaligned proposals.
    if not len(truth):
        return truth
    wh = truth[:, 2:] - truth[:, :2]
    parts = [truth]
    for factor in (0.38, 0.65, 0.92, 1.12, 1.5):
        size = wh * factor
        center = (truth[:, 2:] + truth[:, :2]) / 2 + (
            torch.rand(wh.shape, generator=generator) - 0.5
        ) * wh * (abs(factor - 1) + 0.18)
        parts.append(torch.cat((center - size / 2, center + size / 2), dim=1))
    return (
        torch.cat(parts)
        .clamp(min=0)
        .minimum(torch.tensor([WIDTH, HEIGHT, WIDTH, HEIGHT]))
    )


@torch.inference_mode()
def extract(model, image, row, generator=None):
    image = image[None].cuda().float() / 255
    feats = model.detector.encoder(model.detector.backbone(image))
    queries = model.detector.decoder(feats)
    scale = image.new_tensor([WIDTH, HEIGHT, WIDTH, HEIGHT])
    coords = box_convert(queries["pred_boxes"][0], "cxcywh", "xyxy").clamp(0, 1) * scale
    logits = queries["pred_logits"][0, :, 2].cpu()
    gt = truth_boxes(row)
    all_boxes = (
        torch.cat((coords, jitter(gt, generator).cuda()))
        if generator is not None
        else coords
    )
    norm = all_boxes / scale
    center = (norm[:, 2:] + norm[:, :2]) / 2
    radius = (norm[:, 2:] - norm[:, :2]) * 0.85
    context = torch.cat((center - radius, center + radius), 1).clamp(0, 1)
    chunks = []
    for grid, boxes, size in [
        (feats[0], norm, 2),
        (feats[0], context, 2),
        (feats[1], norm, 1),
    ]:
        h, w = grid.shape[-2:]
        regions = boxes * boxes.new_tensor([w, h, w, h])
        values = roi_align(grid, [regions], size, aligned=True, sampling_ratio=2)
        chunks.append(
            torch.nn.functional.layer_norm(values.flatten(1), (values[0].numel(),))
        )
    descriptor = torch.cat(chunks, 1).cpu().half()
    boxes = all_boxes.cpu()
    match = box_iou(boxes, gt).amax(1) if len(gt) else torch.zeros(len(boxes))
    numeric = model.post(queries, torch.tensor([[WIDTH, HEIGHT]], device="cuda"))
    raw = {k: v.cpu().numpy() for k, v in zip(("labels", "boxes", "scores"), numeric)}
    parent = detections(raw, 0.35, 0.5)
    other = [d for d in parent if d["class_id"] != 2]
    return dict(
        features=descriptor,
        boxes=boxes,
        prior=logits,
        match=match,
        other=other,
        parent=parent,
        objects=row["objects"],
        excluded=row["excluded"],
        rgb_sha256=row["rgb_sha256"],
    )


def cache(root, data):
    dest = root / "cache"
    dest.mkdir(parents=True, exist_ok=True)
    seen = set()
    manifest = {"train": [], "validation": []}
    stats = {"train": {}, "validation": {}}
    if data:
        previous = read(dest / "previous.json")
        if previous["parent"] != digest(PARENT / "decoder.pt"):
            raise ValueError("cached parent decoder")
        manifest, stats = previous["manifest"], previous["stats"]
        seen.update(row["source"] for entries in manifest.values() for row in entries)
        batch = {"train": [], "validation": []}
    else:
        batch = inputs(PREVIOUS / "run-02/dataset", seen)
        extra = inputs(PREVIOUS / "parked-03/dataset", seen, parked=True)
        for split, rows in extra.items():
            batch[split].extend(rows)
        del extra
        add_archived(batch, PREVIOUS / "archived-training-images")
    sites = {split: ["previous"] * len(rows) for split, rows in batch.items()}
    for directory in data:
        name = read(directory / "plan.json")["map"].split("/")[-1]
        if name not in ("Town10HD_Opt", "Town06_Opt", "Town02_Opt"):
            raise ValueError("independent parking map")
        extra = inputs(directory, seen, parking_map=name)
        for split, rows in extra.items():
            batch[split].extend(rows)
            sites[split].extend([name] * len(rows))
    if data and (
        not any(name != "previous" for name in sites["train"])
        or "Town02_Opt" not in sites["validation"]
    ):
        raise ValueError("independent training and validation captures required")
    model = detector()
    generator = torch.Generator().manual_seed(SEED)
    for split, rows in batch.items():
        entries = manifest[split]
        counts = stats[split]
        for i, (im, row) in enumerate(rows):
            x = extract(model, im, row, generator if split == "train" else None)
            site = sites[split][i]
            eligible = x["prior"].sigmoid() >= 0.35
            hard = eligible & (x["match"][: len(eligible)] < 0.1)
            partial = (
                eligible
                & (x["match"][: len(eligible)] >= 0.1)
                & (x["match"][: len(eligible)] < 0.5)
            )
            c = counts.setdefault(
                site,
                dict(images=0, cars=0, confident_low_overlap=0, confident_partial=0),
            )
            for key, num in (
                ("images", 1),
                ("cars", len(truth_boxes(row))),
                ("confident_low_overlap", int(hard.sum())),
                ("confident_partial", int(partial.sum())),
            ):
                c[key] += num
            path = dest / f"{site}-{split}-{i:04d}.pt"
            if path.exists():
                raise FileExistsError(path)
            torch.save(x, path)
            entries.append(
                dict(
                    file=path.name,
                    sha256=digest(path),
                    source=row["rgb_sha256"],
                    site=site,
                )
            )
        manifest[split] = entries
        stats[split] = counts
    if not data:
        write(
            dest / "previous.json",
            dict(parent=digest(PARENT / "decoder.pt"), manifest=manifest, stats=stats),
        )
        return
    write(dest / "manifest.json", manifest)
    write(dest / "stats.json", stats)
    print(stats, flush=True)


def head(size):
    return nn.Sequential(
        nn.Linear(size, 96), nn.LayerNorm(96), nn.GELU(), nn.Linear(96, 1)
    ).cuda()


def load_rows(dest, entries):
    rows = []
    for e in entries:
        path = dest / e["file"]
        if digest(path) != e["sha256"]:
            raise ValueError("feature cache digest")
        row = torch.load(path, weights_only=True)
        if row["rgb_sha256"] != e["source"]:
            raise ValueError("feature cache source")
        rows.append(row)
    return rows


def car_predictions(sample, scores, threshold):
    boxes = sample["boxes"][: len(scores)]
    indices = torch.where(
        (scores >= threshold)
        & (boxes[:, 2] > boxes[:, 0])
        & (boxes[:, 3] > boxes[:, 1])
    )[0]
    indices = indices[nms(boxes[indices], scores[indices], 0.55)]
    return [
        dict(class_id=2, score=float(scores[i]), box=boxes[i].tolist()) for i in indices
    ]


@torch.inference_mode()
def scores_for(net, row):
    prior = row["prior"]
    verify = net(row["features"][: len(prior)].float().cuda()).flatten().cpu()
    return (0.65 * verify + 0.35 * prior).sigmoid()


def metrics(rows, sites, net, thresholds=THRESHOLDS):
    totals = {t: {} for t in thresholds}
    for row, site in zip(rows, sites, strict=True):
        scores = scores_for(net, row)
        for threshold, group in totals.items():
            pred = car_predictions(row, scores, threshold) + row["other"]
            cells = measure(pred, row["objects"], row["excluded"])[0]
            counts = group.setdefault(site, np.zeros(3, np.int64))
            counts += [sum(v[k] for v in cells.values()) for k in ("tp", "fp", "fn")]
    result = []
    for t, group in totals.items():
        cards = {}
        for site, (tp, fp, fn) in group.items():
            cards[site] = dict(
                tp=int(tp),
                fp=int(fp),
                fn=int(fn),
                p=float(tp / max(1, tp + fp)),
                r=float(tp / max(1, tp + fn)),
            )
        margin = min(min(c["p"] / 0.85, c["r"] / 0.8) for c in cards.values())
        result.append(dict(threshold=t, groups=cards, minimum_margin=margin))
    return result


def fit(root, previous_only=False):
    dest = root / "cache"
    out = root / ("previous-fit" if previous_only else "fit")
    out.mkdir(exist_ok=False)
    index = dest / ("previous.json" if previous_only else "manifest.json")
    manifest = read(index)
    if previous_only:
        manifest = manifest["manifest"]
    train = load_rows(dest, manifest["train"])
    val = load_rows(dest, manifest["validation"])
    baseline = {}
    for row, entry in zip(val, manifest["validation"], strict=True):
        cells = measure(row["parent"], row["objects"], row["excluded"])[0]
        counts = baseline.setdefault(entry["site"], dict(tp=0, fp=0, fn=0))
        for k in counts:
            counts[k] += sum(c[k] for c in cells.values())
    write(out / "parent-validation.json", baseline)
    torch.manual_seed(SEED)
    rng = random.Random(SEED)
    net = head(train[0]["features"].shape[1])
    optimizer = torch.optim.AdamW(net.parameters(), lr=0.0004)
    write(
        out / "protocol.json",
        dict(
            seed=SEED,
            epochs=EPOCHS,
            thresholds=THRESHOLDS,
            car_nms=0.55,
            region_logit_weight=0.65,
            parent=digest(PARENT / "decoder.pt"),
            cache=digest(index),
            selection="Maximize the lower of precision/0.85 and recall/0.80 on both independent validation groups; first tie.",
        ),
    )
    history = []
    best = -1
    for e in range(EPOCHS):
        rng.shuffle(train)
        net.train()
        for start in range(0, len(train), 12):
            features = []
            labels = []
            for row in train[start : start + 12]:
                match = row["match"]
                positive = torch.where(match >= 0.5)[0]
                prior = row["prior"]
                # Keep both hard background and poor boxes around real vehicles.
                false = torch.where(match[: len(prior)] < 0.5)[0]
                hard = false[prior[false].argsort(descending=True)[:20]]
                synthetic = torch.where(match[len(prior) :] < 0.5)[0] + len(prior)
                ids = torch.cat(
                    [positive, hard, synthetic, torch.randperm(len(prior))[:8]]
                ).unique()
                features.append(row["features"][ids])
                labels.append(match[ids] >= 0.5)
            target = torch.cat(labels).cuda().float()
            logits = net(torch.cat(features).cuda().float()).flatten()
            loss = nn.functional.binary_cross_entropy_with_logits(
                logits, target, pos_weight=target.new_tensor(2.0)
            )
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
        candidates = metrics(
            val, [r["site"] for r in manifest["validation"]], net.eval()
        )
        chosen = max(candidates, key=lambda x: x["minimum_margin"])
        print(e + 1, chosen, flush=True)
        history.append(candidates)
        if chosen["minimum_margin"] > best:
            best = chosen["minimum_margin"]
            selection = dict(epoch=e + 1, **chosen)
            torch.save(net.state_dict(), out / "verifier.pt")
    write(
        out / "selection.json",
        dict(selected=selection, history=history, weights=digest(out / "verifier.pt")),
    )


def development(root, previous_only=False, *, adjust=None, output=None):
    if not (root / "fit/selection.json").exists():
        raise ValueError("select the full candidate before any development comparison")
    out = root / ("previous-fit" if previous_only else "fit")
    frozen = read(out / "selection.json")
    if digest(out / "verifier.pt") != frozen["weights"]:
        raise ValueError("verifier identity")
    model = detector()
    run = BASE / "runs/evaluation-development-01"
    frames = read(run / "images.json")["frames"]
    scenes = read(run / "benchmark.json")["scenes"]
    truth = read(run / "evaluation-only-gt.json")["frames"]
    if not len(frames) == len(scenes) == len(truth) == 81:
        raise ValueError("development denominator")
    net = None
    predictions = []
    observations = []
    for f, s, g in zip(frames, scenes, truth, strict=True):
        rgb = rgb_bytes(unpack(run / "dataset", f["rgb_raw"], 2560, 1536))
        if (
            hashlib.sha256(rgb).hexdigest() != f["rgb_sha256"]
            or not f["scene"] == s["scene"] == g["scene"]
        ):
            raise ValueError("source pairing")
        # Ground truth is only attached for evaluation after prediction.
        row = extract(
            model,
            tensor(Image.frombytes("RGB", (2560, 1536), rgb)),
            dict(rgb_sha256=f["rgb_sha256"], objects=[], excluded=[]),
        )
        if net is None:
            net = head(row["features"].shape[1])
            net.load_state_dict(torch.load(out / "verifier.pt", weights_only=True))
            net.eval()
        scores = scores_for(net, row)
        if adjust is not None:
            row = adjust(row)
        pred = (
            car_predictions(row, scores, frozen["selected"]["threshold"]) + row["other"]
        )
        predictions.append(
            dict(scene=f["scene"], rgb_sha256=f["rgb_sha256"], detections=pred)
        )
        observations.append((s, g, pred, True, False, None))
    card = quality(observations)
    out = output or out
    write(out / "development-predictions.json", predictions)
    write(
        out / "development-score.json",
        {k: v for k, v in card.items() if k != "records"},
    )
    print(card["micro"], card["gates"], flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument(
        "action",
        choices=("cache", "previous-fit", "fit", "development", "previous-development"),
    )
    p.add_argument("root", type=Path)
    p.add_argument("datasets", nargs="*", type=Path)
    a = p.parse_args()
    torch.set_num_threads(4)
    if a.action == "cache":
        cache(a.root, a.datasets)
    elif a.action in ("fit", "previous-fit"):
        fit(a.root, a.action == "previous-fit")
    else:
        development(a.root, a.action == "previous-development")

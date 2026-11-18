"""Train a small score correction for adjacent car queries and select on mask-confirmed occlusions."""

import argparse
import random
from pathlib import Path

import torch
from torch import nn
from torchvision.ops import box_iou

from parking_box_refinement import adjusted
from parking_overlap_calibration import detect, models, neighbor_mask
from parking_pair_review import review
from parking_region_verifier import (
    SEED,
    development,
    digest,
    load_rows,
    measure,
    read,
    scores_for,
    truth_boxes,
    write,
)


def partial_instances(dataset):
    verified = review(dataset)
    if verified["partially_occluded_actor_observations"] == 0:
        raise ValueError("no measured partial occlusions")
    frames = {r["id"]: r for r in read(dataset / "labels.json")}
    known = {}
    for case in verified["pairs"]:
        if case["ratio"] is None or not 0.05 <= case["ratio"] <= 0.85:
            continue
        frame = frames[case["group"] + "-both"]
        index = ("front", "rear").index(case["role"])
        known.setdefault(frame["rgb_sha256"], set()).add(
            frame["actor_ids"][index] % 65536
        )
    return known


def correction(size):
    layer = nn.Linear(size, 1).cuda()
    nn.init.zeros_(layer.weight)
    nn.init.zeros_(layer.bias)
    return layer


def replay_rows(root, entries, known, score_net, loc, fraction):
    records = []
    for raw in load_rows(root / "cache", entries):
        row = adjusted(raw, loc, fraction)
        row = dict(row, boxes=row["boxes"][: len(row["prior"])])
        scores = scores_for(score_net, row)
        near = neighbor_mask(row["boxes"], scores)
        # Apply the specialist in the same neighborhood in training and inference.
        cars = [o for o in row["objects"] if o["class_id"] == 2]
        partial = known.get(row["rgb_sha256"], set())
        ids = [i for i, o in enumerate(cars) if partial and o["instance_id"] in partial]
        records.append((row, scores, near, ids))
    return records


def examples(records):
    rows = []
    for row, scores, near, ids in records:
        chosen = near & (scores >= 0.1)
        if not chosen.any():
            continue
        boxes = row["boxes"][chosen]
        gt = truth_boxes(row)
        match = box_iou(boxes, gt) if len(gt) else torch.empty((len(boxes), 0))
        target = (
            match.amax(1) >= 0.5
            if len(gt)
            else torch.zeros(len(boxes), dtype=torch.bool)
        )
        weight = torch.ones(len(boxes))
        if ids:
            weight[match[:, ids].amax(1) >= 0.5] = 8
        rows.append(
            (
                row["features"][: len(scores)][chosen],
                scores[chosen].logit(),
                target.float(),
                weight,
            )
        )
    return rows


@torch.inference_mode()
def rescore(row, scores, near, layer, scale):
    revised = scores.clone()
    chosen = near & (scores >= 0.1)
    if chosen.any():
        x = row["features"][: len(scores)][chosen].cuda().float()
        revised[chosen] = (
            scores[chosen].logit() + scale * layer(x).flatten().cpu().clamp(-1.5, 1.5)
        ).sigmoid()
    return revised


def report(records, entries, layer, cutoffs, scale):
    groups = {}
    caught = denominator = 0
    for (row, scores, near, ids), entry in zip(records, entries, strict=True):
        revised = rescore(row, scores, near, layer, scale)
        pred = (
            detect(row, revised, cutoffs["near"], cutoffs["ordinary"], near)
            + row["other"]
        )
        cells, used, *_ = measure(pred, row["objects"], row["excluded"])
        group = groups.setdefault(entry["site"], dict(tp=0, fp=0, fn=0))
        for key in group:
            group[key] += sum(v[key] for v in cells.values())
        indices = [i for i, o in enumerate(row["objects"]) if o["class_id"] == 2]
        denominator += len(ids)
        caught += sum(indices[k] in used for k in ids)
    for c in groups.values():
        c.update(
            p=c["tp"] / max(1, c["tp"] + c["fp"]), r=c["tp"] / max(1, c["tp"] + c["fn"])
        )
    return dict(
        groups=groups,
        visible_partial=denominator,
        detected_partial=caught,
        min_p=min(v["p"] for v in groups.values()),
        min_r=min(v["r"] for v in groups.values()),
    )


def fit(root, train_data, val_data, shrink=False):
    out = root / ("occluded-shrink" if shrink else "occluded-fit")
    out.mkdir()
    cutoffs = read(root / "overlap-calibration/selection.json")["selected"]
    for dataset, town in ((train_data, "Town10HD_Opt"), (val_data, "Town02_Opt")):
        if read(dataset / "plan.json")["map"].split("/")[-1] != town:
            raise ValueError("parking split mismatch")
    manifest = read(root / "cache/manifest.json")
    score_net, loc, fraction = models(root)
    train = examples(
        replay_rows(
            root,
            manifest["train"],
            partial_instances(train_data),
            score_net,
            loc,
            fraction,
        )
    )
    validation = replay_rows(
        root,
        manifest["validation"],
        partial_instances(val_data),
        score_net,
        loc,
        fraction,
    )
    layer = correction(train[0][0].shape[1])
    optimizer = torch.optim.AdamW(layer.parameters(), lr=0.00006)
    order = random.Random(SEED)
    scales = (0.125, 0.25, 0.5, 0.75, 1.0) if shrink else (1.0,)
    write(
        out / "protocol.json",
        dict(
            correction_scales=scales,
            positive_partial_weight=8,
            epochs=5,
            learning_rate=0.00006,
            cutoffs=cutoffs,
            score_clip=1.5,
            training_labels=digest(train_data / "labels.json"),
            validation_labels=digest(val_data / "labels.json"),
            parent_verifier=digest(root / "fit/verifier.pt"),
            parent_regressor=digest(root / "box-fit/regressor.pt"),
            selection="Meet P >= .85 and R >= .80 in each validation group. Maximize matched partial-car detections, then worst-group recall, then precision. Include unchanged baseline.",
        ),
    )
    best_key = None
    history = []
    for epoch in range(6):
        if epoch:
            order.shuffle(train)
            for i in range(0, len(train), 16):
                x, prior, y, w = map(torch.cat, zip(*train[i : i + 16]))
                delta = layer(x.cuda().float()).flatten().clamp(-1.5, 1.5)
                loss = (
                    nn.functional.binary_cross_entropy_with_logits(
                        prior.cuda() + delta, y.cuda(), weight=w.cuda()
                    )
                    + 0.03 * delta.square().mean()
                )
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
        for scale in scales if epoch else (0.0,):
            result = dict(
                epoch=epoch,
                scale=scale,
                **report(validation, manifest["validation"], layer, cutoffs, scale),
            )
            history.append(result)
            if result["min_p"] >= 0.85 and result["min_r"] >= 0.80:
                key = (result["detected_partial"], result["min_r"], result["min_p"])
                if best_key is None or key > best_key:
                    best_key = key
                    best = result
                    torch.save(layer.state_dict(), out / "correction.pt")
            print(result, flush=True)
    if best_key is None:
        raise ValueError("no qualified validation candidate")
    write(
        out / "selection.json",
        dict(selected=best, history=history, weights=digest(out / "correction.pt")),
    )


def evaluate(root, shrink=False):
    out = root / ("occluded-shrink" if shrink else "occluded-fit")
    selected = read(out / "selection.json")
    protocol = read(out / "protocol.json")
    if (
        digest(out / "correction.pt") != selected["weights"]
        or digest(root / "fit/verifier.pt") != protocol["parent_verifier"]
        or digest(root / "box-fit/regressor.pt") != protocol["parent_regressor"]
    ):
        raise ValueError("selected weights changed")
    weights = torch.load(out / "correction.pt", weights_only=True)
    layer = correction(weights["weight"].shape[1])
    layer.load_state_dict(weights)
    _, loc, fraction = models(root)
    c = protocol["cutoffs"]

    def predict(row, scores, _threshold):
        near = neighbor_mask(row["boxes"], scores)
        return detect(
            row,
            rescore(row, scores, near, layer, selected["selected"].get("scale", 1.0)),
            c["near"],
            c["ordinary"],
            near,
        )

    development(
        root,
        adjust=lambda row: adjusted(row, loc, fraction),
        output=out,
        predict_car=predict,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=("fit", "development"))
    p.add_argument("root", type=Path)
    p.add_argument("data", type=Path, nargs="*")
    p.add_argument("--shrink", action="store_true")
    a = p.parse_args()
    torch.set_num_threads(2)
    if a.action == "fit":
        fit(a.root, *a.data, shrink=a.shrink)
    else:
        evaluate(a.root, shrink=a.shrink)

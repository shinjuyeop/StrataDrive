"""Compare fixed car scores with and without learned box regression on independent parking maps."""

import argparse
import random
from pathlib import Path

import torch
from torch import nn
from torchvision.ops import box_iou

from parking_region_verifier import (
    HEIGHT,
    WIDTH,
    SEED,
    development,
    digest,
    head,
    load_rows,
    metrics,
    read,
    truth_boxes,
    write,
)

EPOCHS = 6
FRACTIONS = (0.5, 1.0)


def regressor(size):
    net = nn.Sequential(
        nn.Linear(size, 96), nn.LayerNorm(96), nn.GELU(), nn.Linear(96, 4)
    )
    nn.init.zeros_(net[-1].weight)
    nn.init.zeros_(net[-1].bias)
    return net.cuda()


def dimensions(boxes):
    return (boxes[:, :2] + boxes[:, 2:]) / 2, (boxes[:, 2:] - boxes[:, :2]).clamp_min(1)


def training_examples(row):
    gt = truth_boxes(row)
    if not len(gt):
        return None
    iou, index = box_iou(row["boxes"], gt).max(1)
    chosen = iou >= 0.2
    if not chosen.any():
        return None
    center, size = dimensions(row["boxes"][chosen])
    target_center, target_size = dimensions(gt[index[chosen]])
    target = torch.cat(((target_center - center) / size, (target_size / size).log()), 1)
    return row["features"][chosen], target


@torch.inference_mode()
def adjusted(row, net, fraction):
    # Apply corrections only to genuine detector proposals. Synthetic boxes exist only at training time.
    if not fraction:
        return row
    n = len(row["prior"])
    delta = net(row["features"][:n].cuda().float()).cpu().clamp(-1, 1) * fraction
    center, size = dimensions(row["boxes"][:n])
    center = center + size * delta[:, :2]
    size = size * delta[:, 2:].exp()
    boxes = torch.cat((center - size / 2, center + size / 2), 1)
    return dict(
        row,
        boxes=boxes.clamp_min(0).minimum(
            boxes.new_tensor([WIDTH, HEIGHT, WIDTH, HEIGHT])
        ),
    )


def fit(root):
    cache = root / "cache"
    out = root / "box-fit"
    out.mkdir()
    manifest = read(cache / "manifest.json")
    frozen = read(root / "fit/selection.json")
    if frozen["weights"] != digest(root / "fit/verifier.pt"):
        raise ValueError("verifier weights changed")
    threshold = frozen["selected"]["threshold"]
    train = [
        example
        for row in load_rows(cache, manifest["train"])
        if (example := training_examples(row)) is not None
    ]
    val = load_rows(cache, manifest["validation"])
    sites = [v["site"] for v in manifest["validation"]]
    score_net = head(val[0]["features"].shape[1]).eval()
    score_net.load_state_dict(torch.load(root / "fit/verifier.pt", weights_only=True))
    torch.manual_seed(SEED)
    order = random.Random(SEED)
    net = regressor(val[0]["features"].shape[1])
    optimizer = torch.optim.AdamW(net.parameters(), lr=0.0003)
    base = metrics(val, sites, score_net, (threshold,))[0]
    best = dict(epoch=0, fraction=0, **base)
    history = [best]
    write(
        out / "protocol.json",
        dict(
            seed=SEED,
            epochs=EPOCHS,
            fractions=FRACTIONS,
            original=base,
            parent_verifier=frozen["weights"],
            threshold=threshold,
            match_min_iou=0.2,
            selection="Same worst-group precision/recall margin as score-only verifier. Retain original boxes on ties.",
        ),
    )
    torch.save(net.state_dict(), out / "regressor.pt")
    for epoch in range(1, EPOCHS + 1):
        order.shuffle(train)
        net.train()
        for i in range(0, len(train), 24):
            x, y = zip(*train[i : i + 24])
            prediction = net(torch.cat(x).cuda().float())
            loss = nn.functional.smooth_l1_loss(
                prediction, torch.cat(y).cuda(), beta=0.1
            )
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        net.eval()
        for fraction in FRACTIONS:
            rows = [adjusted(row, net, fraction) for row in val]
            result = dict(
                epoch=epoch,
                fraction=fraction,
                **metrics(rows, sites, score_net, (threshold,))[0],
            )
            history.append(result)
            if result["minimum_margin"] > best["minimum_margin"]:
                best = result
                torch.save(net.state_dict(), out / "regressor.pt")
        print(epoch, best, flush=True)
    write(
        out / "selection.json",
        dict(selected=best, history=history, weights=digest(out / "regressor.pt")),
    )


def evaluate(root):
    out = root / "box-fit"
    selection = read(out / "selection.json")
    protocol = read(out / "protocol.json")
    if (
        digest(out / "regressor.pt") != selection["weights"]
        or digest(root / "fit/verifier.pt") != protocol["parent_verifier"]
    ):
        raise ValueError("selected checkpoint changed")
    weights = torch.load(out / "regressor.pt", weights_only=True)
    net = regressor(weights["0.weight"].shape[1]).eval()
    net.load_state_dict(weights)
    development(
        root,
        adjust=lambda row: adjusted(row, net, selection["selected"]["fraction"]),
        output=out,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=("fit", "development"))
    p.add_argument("root", type=Path)
    args = p.parse_args()
    torch.set_num_threads(2)
    (fit if args.action == "fit" else evaluate)(args.root)

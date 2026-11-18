"""Choose fixed score cutoffs for adjacent car proposals on independent validation frames."""

import argparse
from collections import defaultdict
from pathlib import Path

import torch
from torchvision.ops import nms
from parking_box_refinement import adjusted, regressor
from parking_region_verifier import (
    car_predictions,
    development,
    digest,
    head,
    load_rows,
    measure,
    read,
    scores_for,
    write,
)

GRID = (0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80)
ANCHOR = 0.70
OVERLAP = 0.10


def models(root):
    box = read(root / "box-fit/selection.json")
    verifier = read(root / "fit/selection.json")
    if (
        digest(root / "box-fit/regressor.pt") != box["weights"]
        or digest(root / "fit/verifier.pt") != verifier["weights"]
    ):
        raise ValueError("source model identity changed")
    weights = torch.load(root / "box-fit/regressor.pt", weights_only=True)
    size = weights["0.weight"].shape[1]
    loc = regressor(size).eval()
    loc.load_state_dict(weights)
    net = head(size).eval()
    net.load_state_dict(torch.load(root / "fit/verifier.pt", weights_only=True))
    return net, loc, box["selected"]["fraction"]


def neighbor_mask(boxes, scores):
    good = torch.where((scores >= ANCHOR) & (boxes[:, 2:] > boxes[:, :2]).all(1))[0]
    if not len(good):
        return torch.zeros_like(scores, dtype=torch.bool)
    anchors = good[nms(boxes[good], scores[good], 0.55)]
    intersection = (
        (
            torch.minimum(boxes[:, None, 2:], boxes[anchors][None, :, 2:])
            - torch.maximum(boxes[:, None, :2], boxes[anchors][None, :, :2])
        )
        .clamp_min(0)
        .prod(2)
    )
    # An anchor cannot serve as its own neighbor.
    intersection[anchors, torch.arange(len(anchors))] = 0
    area = (boxes[:, 2:] - boxes[:, :2]).clamp_min(0).prod(1).clamp_min(1)
    return (intersection.amax(1) / area) >= OVERLAP


def detect(row, scores, near, ordinary, adjacent=None):
    if near == ordinary:
        return car_predictions(row, scores, ordinary)
    if adjacent is None:
        adjacent = neighbor_mask(row["boxes"], scores)
    allowed = torch.where(adjacent, scores >= near, scores >= ordinary)
    return car_predictions(row, scores.masked_fill(~allowed, -1), min(near, ordinary))


def calibrate(root):
    out = root / "overlap-calibration"
    out.mkdir()
    cache = root / "cache"
    entries = read(cache / "manifest.json")["validation"]
    net, loc, fraction = models(root)
    pairs = [(near, ordinary) for ordinary in GRID for near in GRID if near <= ordinary]
    totals = {pair: defaultdict(lambda: [0, 0, 0]) for pair in pairs}
    write(
        out / "protocol.json",
        dict(
            grid=GRID,
            anchor=ANCHOR,
            intersection_over_proposal_area=OVERLAP,
            verifier=digest(root / "fit/verifier.pt"),
            regressor=digest(root / "box-fit/regressor.pt"),
            validation_manifest=digest(cache / "manifest.json"),
            selection="Both validation groups must meet P >= .85 and R >= .80. Maximize the smaller group recall, then precision, then prefer uniform and higher cutoffs.",
        ),
    )
    for raw, entry in zip(load_rows(cache, entries), entries, strict=True):
        row = adjusted(raw, loc, fraction)
        scores = scores_for(net, row)
        adjacent = neighbor_mask(row["boxes"], scores)
        for near, ordinary in pairs:
            pred = detect(row, scores, near, ordinary, adjacent) + row["other"]
            counts = measure(pred, row["objects"], row["excluded"])[0]
            aggregate = totals[near, ordinary][entry["site"]]
            for idx, key in enumerate(("tp", "fp", "fn")):
                aggregate[idx] += sum(v[key] for v in counts.values())
    history = []
    for (near, ordinary), group in totals.items():
        cards = {
            k: dict(tp=t, fp=p, fn=n, p=t / max(1, t + p), r=t / max(1, t + n))
            for k, (t, p, n) in group.items()
        }
        history.append(
            dict(
                near=near,
                ordinary=ordinary,
                groups=cards,
                min_p=min(v["p"] for v in cards.values()),
                min_r=min(v["r"] for v in cards.values()),
            )
        )
    valid = [v for v in history if v["min_p"] >= 0.85 and v["min_r"] >= 0.80]
    selected = (
        max(
            valid,
            key=lambda v: (
                v["min_r"],
                v["min_p"],
                v["near"] == v["ordinary"],
                v["near"],
                v["ordinary"],
            ),
        )
        if valid
        else None
    )
    write(
        out / "selection.json",
        dict(selected=selected, admissible=len(valid), history=history),
    )
    print(selected, flush=True)


def evaluate(root):
    out = root / "overlap-calibration"
    selected = read(out / "selection.json")["selected"]
    if selected is None:
        raise ValueError("no validation-qualified cutoffs")
    _, loc, fraction = models(root)
    development(
        root,
        adjust=lambda row: adjusted(row, loc, fraction),
        output=out,
        predict_car=lambda row, scores, _: detect(
            row, scores, selected["near"], selected["ordinary"]
        ),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=("fit", "development"))
    p.add_argument("root", type=Path)
    args = p.parse_args()
    torch.set_num_threads(2)
    (calibrate if args.action == "fit" else evaluate)(args.root)

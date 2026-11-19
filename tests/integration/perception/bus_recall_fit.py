"""Fit an RGB-only bus recovery rule on training frames and verify it on untouched splits."""

import argparse
from collections import Counter, defaultdict
import gzip
import json
from itertools import product
from pathlib import Path

from bus_recall import forward, proposals
from fresh_quality_2k_review import ROOT, read, write
from person_zoom_validation import crop_bounds, detect, merge
from person_additive import combine
from physical_ai.perception.parking_candidate import detections

PERSON = ROOT / "docs/test-plan/evidence/m10_person_additive_v2/additive-selection.json"


def iou(a, b):
    w = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    h = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    return (
        w
        * h
        / max(
            1e-12, (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - w * h
        )
    )


def recover(base, raw, policy):
    accepted = list(base)
    for p in sorted(raw, key=lambda v: -v["score"]):
        if (
            p["score"] < policy["score"]
            or min(p["old5"], p["adapted5"]) < policy["support"]
        ):
            continue
        if p["adapted7"] >= policy.get("truck_max", 2.0):
            continue
        if p["score"] < policy["ratio"] * max(p["adapted7"], p["old7"]):
            continue
        if any(iou(p["box"], d["box"]) >= 0.45 for d in accepted):
            continue
        accepted.append(dict(class_id=5, box=p["box"], score=p["score"]))
    return accepted


def matched(pred, truth):
    used = set()
    for d in sorted(pred, key=lambda det: -det["score"]):
        val, idx = max(
            ((iou(d["box"], b), i) for i, b in enumerate(truth) if i not in used),
            default=(0, -1),
            key=lambda a: (a[0], -a[1]),
        )
        if val >= 0.5:
            used.add(idx)
    return used


def evaluate(rows, policy):
    groups = defaultdict(Counter)
    for r in rows:
        pred = recover(r["base"], r["proposals"], policy) if policy else r["base"]
        n = len(matched(pred, r["truth"]))
        groups[r["site"]].update(
            frames=1, tp=n, fp=len(pred) - n, fn=len(r["truth"]) - n
        )
    return dict(groups)


def diagnose(rows):
    missed = Counter()
    for r in rows:
        found = matched(r["base"], r["truth"])
        for i, b in enumerate(r["truth"]):
            if i in found:
                continue
            old = [
                p
                for p in r["proposals"]
                if p["source"] == "original_" and iou(p["box"], b) >= 0.5
            ]
            alt = [
                p
                for p in r["proposals"]
                if p["source"] == "adapted" and iou(p["box"], b) >= 0.5
            ]
            if any(p["score"] >= 0.5 and p["adapted7"] >= 0.2 for p in old):
                reason = "original_bus_vetoed_by_truck"
            elif old:
                reason = "original_bus_below_confidence"
            elif alt:
                reason = "adapted_head_only"
            else:
                reason = "neither_head_has_matching_bus_at_0.05"
            missed[reason] += 1
    return missed


def passes(before, after):
    return all(
        after[k]["tp"] >= b["tp"] and after[k]["fp"] <= b["fp"] + b["frames"] // 300
        for k, b in before.items()
    ) and sum(v["tp"] for v in after.values()) > sum(v["tp"] for v in before.values())


def load_rows(work, split):
    with gzip.open(work / (split + ".jsonl.gz"), "rt") as f:
        return [json.loads(line) for line in f]


def fit(work):
    rows = load_rows(work, "train")
    before = evaluate(rows, None)
    # Identical scores for rows without bus proposals under every operating point.
    active = [r for r in rows if r["proposals"]]
    constant = evaluate([r for r in rows if not r["proposals"]], None)
    winners = []
    for s, support, ratio in product(
        (0.25, 0.35, 0.45, 0.5, 0.6, 0.7, 0.8),
        (0, 0.05, 0.15, 0.25, 0.35),
        (0.6, 0.85, 1, 1.25, 1.5, 2),
    ):
        policy = dict(score=s, support=support, ratio=ratio)
        after = evaluate(active, policy)
        for k, v in constant.items():
            after.setdefault(k, Counter()).update(v)
        if passes(before, after):
            rank = (
                sum(v["tp"] for v in after.values()),
                -sum(v["fp"] for v in after.values()),
                s,
                support,
                ratio,
            )
            winners.append((rank, policy, after))
    if not winners:
        raise ValueError("no training improvement within FP budget")
    _, policy, after = max(winners, key=lambda x: x[0])
    write(
        work / "selection.json",
        dict(
            passed=True,
            policy=policy,
            qualified=len(winners),
            before=before,
            after=after,
            misses=diagnose(rows),
        ),
    )


def calibrate(work):
    """Retain a training-qualified candidate only if it also rejects known negative scenes."""
    train = load_rows(work, "train")
    negatives = [r for r in load_rows(work, "validation") if not r["truth"]]
    before = evaluate(train, None)
    active = [r for r in train if r["proposals"]]
    constant = evaluate([r for r in train if not r["proposals"]], None)
    negative_active = [r for r in negatives if r["proposals"]]
    winners = []
    for truck, s, support, ratio in product(
        (0.25, 0.3, 0.35, 0.4, 0.5, 0.65),
        (0.4, 0.5, 0.6, 0.7),
        (0.15, 0.25, 0.35),
        (0.6, 1, 1.25),
    ):
        policy = dict(score=s, support=support, ratio=ratio, truck_max=truck)
        if any(
            len(recover(r["base"], r["proposals"], policy)) != len(r["base"])
            for r in negative_active
        ):
            continue
        after = evaluate(active, policy)
        for k, v in constant.items():
            after.setdefault(k, Counter()).update(v)
        if passes(before, after):
            rank = (
                sum(v["tp"] for v in after.values()),
                -sum(v["fp"] for v in after.values()),
                -truck,
                s,
                support,
                ratio,
            )
            winners.append((rank, policy, after))
    if not winners:
        raise ValueError("no hard-negative qualified candidate")
    _, policy, after = max(winners, key=lambda x: x[0])
    write(
        work / "selection.json",
        dict(
            passed=True,
            policy=policy,
            qualified=len(winners),
            before=before,
            after=after,
            negative_calibration_frames=len(negatives),
            added_negative_detections=0,
        ),
    )


def validate(work):
    rows = load_rows(work, "validation")
    if {r["rgb"] for r in rows} & {r["rgb"] for r in load_rows(work, "train")}:
        raise ValueError("train/validation RGB overlap")
    before = evaluate(rows, None)
    after = evaluate(rows, read(work / "selection.json")["policy"])
    write(
        work / "validation.json",
        dict(
            passed=passes(before, after),
            before=before,
            after=after,
            misses=diagnose(rows),
        ),
    )


def infer(image, session, spec, policy):
    raw = forward(image, session, spec)
    base = detections(raw, spec)
    people = [d for d in base if d["class_id"] == 0]
    zoom = people
    bounds = None
    anchor = max(
        (d for d in base if d["class_id"] in (1, 3)),
        key=lambda d: d["score"],
        default=None,
    )
    if anchor:
        bounds = crop_bounds(image.size, anchor["box"])
        local, _ = detect(image.crop(bounds), session, spec)
        zoom = merge(people, local, bounds, image.size)
    bus = [d for d in base if d["class_id"] == 5]
    obs = proposals(raw)
    primary = (
        [d for d in base if d["class_id"] not in (0, 5)]
        + recover(bus, obs, policy)
        + combine(people, zoom, read(PERSON)["config"])
    )
    return primary, dict(
        full=people, zoom=zoom, bounds=bounds, bus_full=bus, bus_observations=obs
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("work", type=Path)
    p.add_argument("action", choices=("fit", "calibrate", "validate", "development"))
    a = p.parse_args()
    if a.action == "development":
        from person_support_replay import six_class
        from fresh_quality_2k_review import BASE

        six_class(
            a.work,
            BASE / "runs/evaluation-development-01",
            read(a.work / "selection.json")["policy"],
            detector=infer,
        )
    else:
        {"fit": fit, "calibrate": calibrate, "validate": validate}[a.action](a.work)

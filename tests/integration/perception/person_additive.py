"""Keep full-frame people and admit distinct, well-supported zoom observations."""

import argparse
from collections import Counter
from pathlib import Path

import numpy as np
from person_support_replay import (
    CACHE,
    PREVIOUS,
    TRAIN,
    MODEL,
    rows,
    frames,
    overlaps,
    score,
    read,
    dump,
)
from person_support_audit import fresh_rows


def combine(full, zoom, config):
    selected = list(full)
    boxes = [d["box"] for d in selected]
    for det in sorted(zoom, key=lambda d: -d["score"]):
        x1, y1, x2, y2 = det["box"]
        width, height = x2 - x1, y2 - y1
        if (
            det["score"] < config["confidence"]
            or min(width, height) < config["minimum"]
            or width * height < 25
        ):
            continue
        if overlaps(np.array([det["box"]]), boxes).max(initial=0) >= config["iou"]:
            continue
        selected.append(det)
        boxes.append(det["box"])
    return selected


def evaluate(records, config):
    before, after = Counter(), Counter()
    for r, gt, scene in records:
        original = r["full"]
        chosen = combine(original, r["zoom"], config)
        for pred, c in ((original, before), (chosen, after)):
            c.update(score(pred, gt, scene.get("role", "archive"))[0])
    paired = before["both_eligible"] > 0
    gates = dict(
        walker=after["pedestrian_tp"] >= before["pedestrian_tp"] + int(paired),
        rider=after["rider_tp"] >= before["rider_tp"],
        fp=after["fp"] <= before["fp"] + before["frames"] // 100,
        precision=after["tp"] >= 0.85 * (after["tp"] + after["fp"]),
    )
    if paired:
        gates["both"] = after["both_matched"] > before["both_matched"]
    return dict(before=before, after=after, gates=gates, passed=all(gates.values()))


def fit(out):
    training = list(rows(TRAIN, frames(CACHE, "train", True)))
    candidates = []
    for conf in (0.60, 0.70, 0.80, 0.85, 0.90):
        for minimum in (4, 4.5, 5, 5.5, 6, 7, 8):
            for iou in (0.25, 0.35, 0.45):
                config = dict(minimum=minimum, iou=iou, confidence=conf)
                result = evaluate(training, config)
                c = result["after"]
                if result["passed"]:
                    ranking = (
                        -c["fp"],
                        c["both_matched"],
                        c["pedestrian_tp"],
                        conf,
                        minimum,
                        -iou,
                    )
                    candidates.append((ranking, config, result))
    if not candidates:
        raise ValueError("no training-qualified additive candidate")
    _, config, train = max(candidates, key=lambda item: item[0])
    dump(out / "selection.json", dict(config=config, train=train, model=MODEL))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("fit", "validate"))
    p.add_argument("out", type=Path)
    p.add_argument("--support", type=Path)
    a = p.parse_args()
    a.out.mkdir(exist_ok=True, parents=True)
    if a.action == "fit":
        fit(a.out)
    else:
        config = read(a.out / "selection.json")["config"]
        results = {
            name: evaluate(
                rows(
                    PREVIOUS / (name + ".jsonl.gz"), frames(CACHE, "validation", paired)
                ),
                config,
            )
            for name, paired in (
                ("archive-validation", False),
                ("pairs-validation", True),
            )
        }
        results["Town05"] = evaluate(fresh_rows(a.support), config)
        dump(a.out / "validation.json", results)

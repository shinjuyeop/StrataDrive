"""Select among additive views on known development roads, reserving new roads for replication."""

import argparse
from collections import Counter
from pathlib import Path
from itertools import product

from person_additive import combine, evaluate
from person_support_audit import fresh_rows
from person_support_replay import (
    CACHE,
    MODEL,
    PREVIOUS,
    TRAIN,
    dump,
    frames,
    read,
    rows,
    score,
)


def infer_additive(image, session, spec, config):
    from person_support_replay import infer

    primary, trace = infer(image, session, spec, config["minimum"])
    retained = [d for d in primary if d["class_id"] != 0]
    people = combine(trace["full"], trace["zoom"], config)
    retained.extend(people)
    return retained, {k: trace[k] for k in ("bounds", "full", "zoom")}


def check_replication(out, first):
    data = list(fresh_rows(out))
    if len(data) != 120:
        raise ValueError("replication denominator")
    historical = {row["rgb"] for row, _, _ in fresh_rows(first)}
    if any(r["rgb"] in historical for r, _, _ in data):
        raise ValueError("RGB overlap with earlier Town05")
    old = read(first / "Town05_Opt/dataset/plan.json")
    new = read(out / "Town05_Opt/dataset/plan.json")
    import math

    old_poses = [s["camera"]["location"] for s in old["scenes"]]

    def roads(p):
        return {r for s in p["scenes"] for r in s["roads"]}

    distance = min(
        math.dist([s["camera"]["location"][k] for k in "xyz"], [pt[k] for k in "xyz"])
        for s in new["scenes"]
        for pt in old_poses
    )
    if (
        new["xodr_sha256"] != old["xodr_sha256"]
        or roads(old) & roads(new)
        or distance < 50
    ):
        raise ValueError("unqualified replication roads")
    config = read(out / "additive-selection.json")["config"]
    result = evaluate(data, config)
    result.update(
        roads=sorted(roads(new)),
        previous_roads=sorted(roads(old)),
        minimum_camera_separation_m=distance,
    )
    dump(out / "replication.json", result)


def fit(out, first):
    splits = dict(
        Town01=list(rows(TRAIN, frames(CACHE, "train", True))),
        Town02=list(
            rows(
                PREVIOUS / "pairs-validation.jsonl.gz",
                frames(CACHE, "validation", True),
            )
        ),
        Town05=list(fresh_rows(first)),
    )
    prepared = {}
    for name, split in splits.items():
        base = Counter()
        samples = []
        for row, gt, scene in split:
            count = score(row["full"], gt, scene["role"])[0]
            base.update(count)
            samples.append((row, gt, scene, {tuple(id(d) for d in row["full"]): count}))
        prepared[name] = (base, samples)
    winners = []
    for conf, minimum, iou in product(
        (0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9),
        (4, 4.25, 4.5, 4.75, 5, 5.5, 6, 7),
        (0.25, 0.35, 0.45, 0.5, 0.55),
    ):
        config = dict(confidence=conf, minimum=minimum, iou=iou)
        both = []
        walkers = []
        fp = []
        for base, samples in prepared.values():
            total = Counter()
            for row, gt, scene, cache in samples:
                selected = combine(row["full"], row["zoom"], config)
                key = tuple(id(d) for d in selected)
                if key not in cache:
                    cache[key] = score(selected, gt, scene["role"])[0]
                total.update(cache[key])
            walker = total["pedestrian_tp"] - base["pedestrian_tp"]
            pair = total["both_matched"] - base["both_matched"]
            extra = total["fp"] - base["fp"]
            if (
                walker < 1
                or pair < 1
                or extra > base["frames"] // 100
                or total["rider_tp"] < base["rider_tp"]
                or total["tp"] < 0.85 * (total["tp"] + total["fp"])
            ):
                break
            both.append(pair)
            walkers.append(walker)
            fp.append(extra)
        if len(both) == len(splits):
            ranking = (
                min(walkers),
                min(both),
                -max(fp),
                sum(both),
                sum(walkers),
                -sum(fp),
                conf,
                minimum,
                -iou,
            )
            winners.append((ranking, config))
    if not winners:
        raise ValueError("no setting met the same gates on all three known roads")
    rank, config = max(winners, key=lambda item: item[0])
    dump(
        out / "additive-selection.json",
        dict(
            model=MODEL,
            config=config,
            qualifying_configs=len(winners),
            rank=rank,
            scores={k: evaluate(v, config) for k, v in splits.items()},
        ),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("out", type=Path)
    p.add_argument("first", type=Path)
    p.add_argument(
        "--action", choices=("fit", "archive", "replicate", "six"), default="fit"
    )
    p.add_argument("--run", type=Path)
    a = p.parse_args()
    if a.action == "fit":
        fit(a.out, a.first)
    elif a.action == "replicate":
        check_replication(a.out, a.first)
    else:
        config = read(a.out / "additive-selection.json")["config"]
        if a.action == "six":
            from person_support_replay import six_class

            six_class(a.out, a.run, config, detector=infer_additive)
        else:
            dump(
                a.out / "archive.json",
                evaluate(
                    rows(
                        PREVIOUS / "archive-validation.jsonl.gz",
                        frames(CACHE, "validation", False),
                    ),
                    config,
                ),
            )

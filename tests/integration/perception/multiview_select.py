"""Select four class thresholds only from archived validation and two development roads."""

import argparse
from collections import Counter
from pathlib import Path

from multiview_detector import TARGET, combine, records, score_run
from fresh_quality_2k_review import BASE, read, write
from bus_recall_fit import matched
from person_proposal_diagnosis import PARK

GRID = (
    0.12,
    0.16,
    0.20,
    0.25,
    0.30,
    0.35,
    0.40,
    0.45,
    0.50,
    0.55,
    0.60,
    0.65,
    0.70,
    0.75,
    0.80,
    0.85,
    0.9,
    0.95,
    1.01,
)


def totals(rows, negative_scene, cls, threshold):
    c = Counter()
    for row in rows:
        pred = [d for d in row["base"] if d["class_id"] == cls] + [
            d for d in row["extras"][cls] if d["score"] >= threshold
        ]
        boxes = [o["box"] for o in row["gt"] if o["class_id"] == cls]
        tp = len(matched(pred, boxes))
        fp = len(pred) - tp
        c.update(
            tp=tp,
            fp=fp,
            fn=len(boxes) - tp,
            negative_fp=fp if row["rgb"] in negative_scene else 0,
        )
    return c


def summarize(c):
    p = c["tp"] / max(1, c["tp"] + c["fp"])
    r = c["tp"] / max(1, c["tp"] + c["fn"])
    return dict(c, precision=p, recall=r, f2=5 * p * r / max(1e-9, 4 * p + r))


def select(work):
    dev = {
        "dev90": BASE / "runs/evaluation-development-01",
        "dev608": work / "native/runs/evaluation-development-01",
    }
    sets = {
        n: list(records(work / (n + "-verified.jsonl.gz")))
        for n in (*dev, "validation")
    }
    negatives = set()
    for run in dev.values():
        for f, s in zip(
            read(run / "images.json")["frames"],
            read(run / "benchmark.json")["scenes"],
            strict=True,
        ):
            if s["stratum"] == "negative":
                negatives.add(f["rgb_sha256"])
    memberships = {
        r["source"]: r["site"] for r in read(PARK / "cache/manifest.json")["validation"]
    }
    archive = sets.pop("validation")
    for r in archive:
        sets.setdefault(memberships[r["rgb"]], []).append(r)
    if sum(len(s) for s in sets.values()) != 861:
        raise ValueError("calibration denominator")
    seen = {r["rgb"] for r in records(work / "train.jsonl.gz")}
    for ds in sets.values():
        for r in ds:
            if r["rgb"] in seen:
                raise ValueError("cross-split RGB")
            seen.add(r["rgb"])
            combined = combine(r["base"], r["new"], {str(c): min(GRID) for c in TARGET})
            r["extras"] = {
                c: [d for d in combined[len(r["base"]) :] if d["class_id"] == c]
                for c in TARGET
            }
    policy = {}
    chosen = {}
    for c in TARGET:
        parent = {
            n: summarize(totals(ds, negatives, c, 1.01)) for n, ds in sets.items()
        }
        options = []
        for t in GRID:
            cards = {
                n: summarize(totals(ds, negatives, c, t)) for n, ds in sets.items()
            }
            if any(
                v["tp"] < parent[n]["tp"] or v["negative_fp"] > parent[n]["negative_fp"]
                for n, v in cards.items()
            ):
                continue
            if any(cards[n]["recall"] < 0.70 for n in dev):
                continue
            # Precision on sparse subsets is compared using counts to avoid unstable ratios.
            if any(
                v["fp"] - parent[n]["fp"] > max(2, (v["tp"] - parent[n]["tp"]) * 1.5)
                for n, v in cards.items()
            ):
                continue
            rank = (
                min(v["f2"] for v in cards.values()),
                sum(v["f2"] for v in cards.values()),
                -sum(v["fp"] for v in cards.values()),
                t,
            )
            options.append((rank, t, cards))
        if not options:
            raise ValueError(f"no qualified calibration for class {c}")
        _, t, cards = max(options, key=lambda v: v[0])
        policy[str(c)] = t
        chosen[str(c)] = dict(parent=parent, selected=cards)
    res = {}
    for n, run in dev.items():
        card, _ = score_run(run, sets[n], policy)
        base, _ = score_run(run, sets[n], {str(c): 1.01 for c in TARGET})
        res[n] = dict(score=card, parent=base["card"]["per_class"])
    for n, ds in sets.items():
        if n not in dev:
            parent_stats = {}
            selected = {}
            for c in (0, 1, 2, 3, 5, 7):
                parent_stats[c] = (
                    summarize(totals(ds, negatives, c, 1.01))
                    if c in TARGET
                    else summarize_static(ds, c)
                )
                selected[c] = (
                    chosen[str(c)]["selected"][n] if c in TARGET else parent_stats[c]
                )
            micro = summarize(
                Counter(
                    {
                        k: sum(v[k] for v in selected.values())
                        for k in ("tp", "fp", "fn")
                    }
                )
            )
            res[n] = dict(
                micro=micro,
                selected=selected,
                parent=parent_stats,
                passed=micro["recall"] >= 0.8 and micro["precision"] >= 0.85,
            )
    selection = dict(
        thresholds=policy,
        model_sha256=read(work / "training.json")["model_sha256"],
        classes=chosen,
    )
    write(work / "selection.json", selection)
    write(
        work / "validation.json",
        dict(
            passed=all(res[n]["score"]["passed"] for n in dev)
            and all(res[n]["passed"] for n in sets if n not in dev),
            groups=res,
        ),
    )


def summarize_static(ds, c):
    total = Counter()
    for row in ds:
        pred = [d for d in row["base"] if d["class_id"] == c]
        boxes = [o["box"] for o in row["gt"] if o["class_id"] == c]
        n = len(matched(pred, boxes))
        total.update(tp=n, fp=len(pred) - n, fn=len(boxes) - n)
    return summarize(total)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("work", type=Path)
    select(p.parse_args().work)

"""Attribute person false positives against full validation labels using production matching."""

import argparse
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from person_pair_candidate import dump, frames, overlaps, predictions, read
from quality_benchmark_v3 import measure


def false_positives(detections, truth):
    people = [o["box"] for o in truth["objects"] if o["class_id"] == 0]
    small = [o["box"] for o in truth["excluded"] if o["class_id"] == 0]
    other = [o["box"] for o in truth["objects"] if o["class_id"] != 0]
    used = set()
    misses = []
    for i in sorted(range(len(detections)), key=lambda i: -detections[i]["score"]):
        box = np.array([detections[i]["box"]])
        scores = overlaps(box, people)[0]
        best = max(
            (j for j in range(len(people)) if j not in used),
            key=lambda j: scores[j],
            default=None,
        )
        if best is not None and scores[best] >= 0.5:
            used.add(best)
            continue
        person = scores.max(initial=0)
        if person >= 0.5:
            reason = "duplicate"
        elif overlaps(box, small).max(initial=0) >= 0.5:
            reason = "excluded_small_person"
        elif person >= 0.1:
            reason = "mislocalized_person"
        elif overlaps(box, other).max(initial=0) >= 0.5:
            reason = "other_class_box"
        else:
            reason = "no_close_eligible_box"
        misses.append((i, reason))
    if (
        len(misses)
        != measure(detections, truth["objects"], truth["excluded"])[0]["0"]["fp"]
    ):
        raise ValueError("false positive attribution disagrees with benchmark")
    return misses


def paired_walkers(observations):
    report = defaultdict(Counter)
    for roles in observations.values():
        for role in ("car", "cycle"):
            clear, blocked = roles["clear"], roles[role]
            if clear is None or blocked is None:
                report[role]["ineligible"] += 1
                continue
            report[role]["both_eligible"] += 1
            outcome = {
                (True, True): "both_detected",
                (False, False): "neither_detected",
                (True, False): "clear_only",
                (False, True): "blocked_only",
            }[clear, blocked]
            report[role][outcome] += 1
    return report


def audit(root, split, paired):
    folder = root / (("pairs-" if paired else "archive-") + split)
    labels = {rgb: gt for _, gt, rgb, _ in frames(root, split, paired)}
    head = read(root / "person-head.json")
    counts = defaultdict(Counter)
    walkers = defaultdict(lambda: defaultdict(dict))
    for row in read(folder / "index.json"):
        with np.load(folder / row["file"]) as data:
            cand = predictions(row, data, head)
        for name, pred in (("baseline", row["original"]), ("candidate", cand)):
            if paired and row["role"] in ("clear", "car", "cycle"):
                truth = labels[row["rgb"]]
                actor = truth["actor_ids"][0] % 65536
                target = next(
                    (
                        i
                        for i, o in enumerate(truth["objects"])
                        if o["semantic_tags"] == [12] and o["instance_id"] == actor
                    ),
                    None,
                )
                used = measure(pred, truth["objects"], truth["excluded"])[1]
                walkers[name][row["group"]][row["role"]] = (
                    target in used if target is not None else None
                )
            for i, reason in false_positives(pred, labels[row["rgb"]]):
                counts[name][reason] += 1
                if i >= len(row["original"]):
                    counts["added_query_fp"][reason] += 1
    return dict(
        false_positives=counts,
        matched_walker_pairs={k: paired_walkers(v) for k, v in walkers.items()},
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("root", type=Path)
    p.add_argument("--paired", action="store_true")
    args = p.parse_args()
    dump(
        args.root / ("fp-pairs.json" if args.paired else "fp-archive.json"),
        audit(args.root, "validation", args.paired),
    )

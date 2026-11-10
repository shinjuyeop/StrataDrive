"""Offline class confidence vectors on the unchanged native DETR export."""

from itertools import product
import math

from .model_screen_v2 import decode as scalar_decode

CLASS_ORDER = (0, 1, 2, 3, 5, 7)
GRID = (0.35, 0.4, 0.5, 0.6, 0.7)


def validate_vector(vector):
    if (
        not isinstance(vector, (tuple, list))
        or len(vector) != 6
        or any(
            type(v) not in (int, float) or not math.isfinite(v) or v not in GRID
            for v in vector
        )
    ):
        raise ValueError("class confidence vector/floor")
    return dict(zip(CLASS_ORDER, vector))


def decode(raw, vector):
    thresholds = validate_vector(vector)
    # Conservatively validate the unchanged complete0.35 list before filtering.
    return tuple(
        d
        for d in scalar_decode(raw, "rtdetr", 0.35)
        if d.score >= thresholds[d.class_id]
    )


def scorecard(vector, points, baseline):
    validate_vector(vector)
    values = [points[str(t)]["per_class"][str(c)] for c, t in zip(CLASS_ORDER, vector)]
    near = points[str(vector[0])]["near_person"]
    negative = sum(
        points[str(t)]["negative_fp_by_class"][str(c)]
        for c, t in zip(CLASS_ORDER, vector)
    )
    return from_counts(
        vector,
        dict(zip(map(str, CLASS_ORDER), values)),
        near,
        negative,
        points["0.35"]["negative_frames"],
        sum(points[str(t)]["errors"] for t in vector),
        baseline,
    )


def from_counts(vector, counts, near, negative, negative_frames, errors, baseline):
    validate_vector(vector)
    values = [counts[str(c)] for c in CLASS_ORDER]
    tp, fp, fn = (sum(row[key] for row in values) for key in ("tp", "fp", "fn"))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn)
    f1 = 2 * tp / (2 * tp + fp + fn)
    recalls = [row["tp"] / (row["tp"] + row["fn"]) for row in values]
    macro_f1 = (
        sum(2 * row["tp"] / (2 * row["tp"] + row["fp"] + row["fn"]) for row in values)
        / 6
    )
    absolute = dict(
        no_model_errors=errors == 0,
        precision=precision >= 0.85,
        recall=recall >= 0.8,
        per_class_recall=min(recalls) >= 0.7,
        near_person=near["tp"] / (near["tp"] + near["fn"]) >= 0.9,
        negative_fp=negative / negative_frames <= 1 / 3,
    )
    relative = dict(
        precision_gain_3pp=precision - baseline["micro"]["precision"] >= 0.03 - 1e-12,
        recall_gain_3pp=recall - baseline["micro"]["recall"] >= 0.03 - 1e-12,
        no_class_recall_drop=all(
            r >= baseline["per_class"][str(c)]["recall"]
            for c, r in zip(CLASS_ORDER, recalls)
        ),
    )
    return dict(
        vector=list(vector),
        tp=tp,
        fp=fp,
        fn=fn,
        precision=precision,
        recall=recall,
        f1=f1,
        macro_f1=macro_f1,
        minimum_class_recall=min(recalls),
        negative_fp=negative,
        absolute=absolute,
        relative=relative,
        absolute_pass=all(absolute.values()),
        relative_pass=all(relative.values()),
    )


def rank(card):
    return (
        card["absolute_pass"] and card["relative_pass"],
        card["absolute_pass"],
        card["macro_f1"],
        card["minimum_class_recall"],
        card["f1"],
        tuple(card["vector"]),
    )


def search(points, baseline):
    cards = [scorecard(vector, points, baseline) for vector in product(GRID, repeat=6)]
    return dict(
        scorecards=cards,
        selected=max(cards, key=rank),
        combinations=len(cards),
        absolute_pass_count=sum(c["absolute_pass"] for c in cards),
        absolute_and_relative_pass_count=sum(
            c["absolute_pass"] and c["relative_pass"] for c in cards
        ),
    )

"""One-to-one, subtype-aware rescue of person boxes in crowded views."""

import argparse
from collections import Counter, defaultdict
from pathlib import Path

import joblib
import numpy as np
from scipy.optimize import linear_sum_assignment
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.linear_model import Ridge

from person_pair_candidate import CONFIDENCE, MODEL, digest, dump, overlaps, read
from quality_benchmark_v3 import measure

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / "build/m10-person-pairs-v1"
EVIDENCE = ROOT / "docs/test-plan/evidence/m10_person_pairs_v1"


def load_rows(split):
    folder = CACHE / split
    rows = read(folder / "index.json")
    if split.endswith("-train"):
        expected = read(EVIDENCE / "person-head.json")["training_indices"][split]
        if digest(folder / "index.json") != expected:
            raise ValueError("training index changed")
    for r in rows:
        with np.load(folder / r["file"], allow_pickle=False) as src:
            yield r, {k: src[k] for k in ("boxes", "p", "x")}


def features(data):
    boxes, p = data["boxes"], data["p"]
    wh = boxes[:, 2:] - boxes[:, :2]
    # Neighbouring query support and relative geometry, independent of annotations.
    iou = overlaps(boxes, boxes)
    np.fill_diagonal(iou, 0)
    support = [np.sum(iou >= t, axis=1) for t in (0.25, 0.5, 0.75)]
    votes = [
        np.where(iou >= t, p[None, :], 0).max(axis=1, initial=0)
        for t in (0.25, 0.5, 0.75)
    ]
    return np.column_stack(
        [data["x"], p, np.log1p(wh), np.log(wh[:, 0] / wh[:, 1]), *support, *votes]
    )


def refine(boxes, x, reg):
    if not len(boxes):
        return boxes.copy()
    scale = np.tile(boxes[:, 2:] - boxes[:, :2], (1, 2))
    corrected = (boxes + scale * np.clip(reg.predict(x), -0.30, 0.30)).clip(
        0, [640, 384, 640, 384]
    )
    valid = (corrected[:, 2:] > corrected[:, :2]).all(axis=1)
    return np.where(valid[:, None], corrected, boxes)


def assign(iou, p):
    """Prefer more valid object-query pairs, then their IoU and frozen confidence."""
    affinity = np.where(
        iou >= 0.5, 1 + min(iou.shape) + 0.8 * iou + 0.2 * p[:, None], 0
    )
    q, g = linear_sum_assignment(affinity, maximize=True)
    keep = affinity[q, g] > 0
    return q[keep], g[keep]


def fit(out):
    rows = []
    fx, targets, weights = [], [], []
    for split in ("archive-train", "pairs-train"):
        for row, data in load_rows(split):
            x = features(data)
            boxes = data["boxes"]
            truth = np.array([o["box"] for o in row["objects"]]).reshape(-1, 4)
            iou = overlaps(boxes, truth)
            w = 4 if split == "pairs-train" else 1
            if len(truth):
                selected = iou.max(axis=1) >= 0.30
                if selected.any():
                    b = boxes[selected]
                    delta = (truth[iou[selected].argmax(axis=1)] - b) / np.tile(
                        b[:, 2:] - b[:, :2], (1, 2)
                    )
                    fx.extend(x[selected])
                    targets.extend(delta.clip(-0.5, 0.5))
                    weights.extend([w] * len(b))
            rows.append((row, data, x, truth, w))
    reg = Ridge(alpha=100, solver="cholesky").fit(fx, targets, sample_weight=weights)
    xs, ys, ws = [], [], []
    counts = Counter()
    for row, data, x, truth, w in rows:
        b = refine(data["boxes"], x, reg)
        iou = overlaps(b, truth)
        peak = iou.max(axis=1, initial=0)
        pos, gi = assign(iou, data["p"])
        label = np.zeros(len(b), dtype=int)
        for i, j in zip(pos, gi, strict=True):
            label[i] = {(12,): 1, (13,): 2}[tuple(row["objects"][j]["semantic_tags"])]
        hard = (label == 0) & (peak >= 0.10)
        neg = np.flatnonzero((label == 0) & ~hard)
        keep = np.r_[
            pos,
            np.flatnonzero(hard),
            neg[np.argsort(-data["p"][neg], kind="stable")[:16]],
        ]
        counts.update(
            dict(
                assigned=len(pos),
                duplicate=int(((label == 0) & (peak >= 0.5)).sum()),
                fragment=int(((peak >= 0.1) & (peak < 0.5)).sum()),
            )
        )
        xs.extend(x[keep])
        ys.extend(label[keep])
        ws.extend(np.where(label[keep] > 0, 3 * w, w))
    classifier = ExtraTreesClassifier(
        n_estimators=120,
        min_samples_leaf=2,
        max_features=0.35,
        random_state=104,
        n_jobs=4,
    )
    classifier.fit(xs, ys, sample_weight=ws)
    joblib.dump((reg, classifier), out / "model.joblib", compress=3)
    dump(
        out / "fit.json",
        dict(
            parent=MODEL,
            model_sha256=digest(out / "model.joblib"),
            targets=counts,
            train_frames=len(rows),
        ),
    )


def predict(row, data, model):
    reg, clf = model
    b = data["boxes"]
    base = list(row["original"])
    if not len(b):
        return base, [], []
    x = features(data)
    corrected = refine(b, x, reg)
    probs = clf.predict_proba(x)[:, 1:]
    typ = probs.argmax(axis=1)
    score = probs.max(axis=1)
    kept = [d["box"] for d in base]
    tags = []
    for d in base:
        idx = overlaps(b, [d["box"]])[:, 0].argmax()
        tags.append(typ[idx])
    qualified = []
    for i in np.argsort(-score, kind="stable"):
        if score[i] < CONFIDENCE:
            break
        box = corrected[i]
        qualified.append(box)
        threshold = np.where(np.asarray(tags) == typ[i], 0.45, 0.80)
        if (overlaps(box[None, :], kept)[0] >= threshold).any():
            continue
        kept.append(box)
        tags.append(typ[i])
        base.append(dict(class_id=0, box=box.tolist(), score=float(score[i])))
    return base, corrected, qualified


def evaluate(out):
    fit_record = read(out / "fit.json")
    if fit_record["parent"] != MODEL or fit_record["model_sha256"] != digest(
        out / "model.joblib"
    ):
        raise ValueError("fitted candidate identity")
    model = joblib.load(out / "model.joblib")
    previous = read(EVIDENCE / "comparison.json")
    seen = {
        r["rgb"]
        for k in ("archive-train", "pairs-train")
        for r in read(CACHE / k / "index.json")
    }
    result = {}
    gates = {}
    for split in ("archive-validation", "pairs-validation"):
        groups = defaultdict(lambda: defaultdict(Counter))
        misses = Counter()
        for row, data in load_rows(split):
            if row["rgb"] in seen:
                raise ValueError("duplicate validation image")
            seen.add(row["rgb"])
            candidate, corrected, qualified = predict(row, data, model)
            objs = row["objects"]
            for name, dets in (("baseline", row["original"]), ("candidate", candidate)):
                counts, used, *_ = measure(dets, objs, row["excluded"])
                for group in ["all"] + ([row["role"]] if "role" in row else []):
                    s = groups[group][name]
                    s.update(counts["0"])
                    s["frames"] += 1
                    for i, o in enumerate(objs):
                        t = {(12,): "pedestrian", (13,): "rider"}[
                            tuple(o["semantic_tags"])
                        ]
                        s[t + ("_tp" if i in used else "_fn")] += 1
                    if row.get("role") == "cycle" and {
                        tuple(o["semantic_tags"]) for o in objs
                    } == {(12,), (13,)}:
                        s["eligible_both"] += 1
                        s["matched_both"] += int(len(used) == len(objs))
                if name == "candidate" and row.get("role") == "cycle":
                    for i, o in enumerate(objs):
                        if i in used or o["semantic_tags"] != [12]:
                            continue

                        def has(boxes):
                            return (
                                overlaps(
                                    np.asarray(boxes).reshape(-1, 4), [o["box"]]
                                ).max(initial=0)
                                >= 0.5
                            )

                        if has(qualified):
                            reason = "qualified_but_suppressed_or_unmatched"
                        elif has(corrected):
                            reason = "corrected_box_below_score"
                        elif has(data["boxes"]):
                            reason = "lost_after_correction"
                        else:
                            reason = "no_matching_input_or_corrected_box"
                        misses[reason] += 1
        base, cand = (groups["all"][k] for k in ("baseline", "candidate"))
        recorded = previous["counts"][split]["all"]["baseline"]
        if any(
            base[k] != recorded.get(k, 0)
            for k in ("tp", "fp", "fn", "frames", "pedestrian_tp", "rider_tp")
        ):
            raise ValueError("frozen baseline parity")
        gates[split] = dict(
            pedestrian=cand["pedestrian_tp"]
            >= base["pedestrian_tp"] + (split == "pairs-validation"),
            rider=cand["rider_tp"] >= base["rider_tp"],
            fp=cand["fp"] <= base["fp"] + base["frames"] // 100,
            precision=cand["tp"] >= 0.85 * (cand["tp"] + cand["fp"]),
        )
        if split == "pairs-validation":
            gates[split]["simultaneous_pair_gain"] = (
                cand["matched_both"] > base["matched_both"]
            )
        result[split] = dict(groups=groups, cycle_pedestrian_misses=misses)
    dump(
        out / "result.json",
        dict(
            splits=result,
            gates=gates,
            passed=all(all(g.values()) for g in gates.values()),
            model_sha256=fit_record["model_sha256"],
        ),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=("fit", "evaluate"))
    p.add_argument("output", type=Path)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    {"fit": fit, "evaluate": evaluate}[args.action](args.output)

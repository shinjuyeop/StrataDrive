"""Evaluate the existing multi-view verifier features in a single compiled pass."""

import math

from numba import njit
import numpy as np
import cv2
from multiview_detector import TARGET, GRID

CLASSES = (0, 1, 3, 5, 7)
SLOT = (0, 1, -1, 2, -1, 3, -1, 4)


@njit(cache=True)
def overlap(a, b):
    w = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    h = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = w * h
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / max(1e-7, union)


@njit(cache=True)
def geometry(boxes, observations, parents):
    out = np.zeros((len(boxes), 58), np.float32)
    for i, b in enumerate(boxes):
        width = b[2] - b[0]
        height = b[3] - b[1]
        out[i, :3] = (math.log1p(width), math.log1p(height), width / height)
        row = np.zeros(55, np.float64)
        seen = np.zeros((5, 3, 10), np.bool_)
        for ob in observations:
            view, head, cls = int(ob[0]), int(ob[1]), int(ob[2])
            if view < 0 or view >= 10 or head not in (0, 1):
                raise ValueError("view identity")
            slot = SLOT[cls]
            ov = overlap(b, ob[4:])
            idx = slot * 10
            row[idx + 9] = max(row[idx + 9], ov * ob[3])
            for j in range(3):
                if ov < (j + 1) * 0.25:
                    break
                v = idx + 3 * j
                row[v + head] = max(row[v + head], ob[3])
                if ob[3] >= 0.30 and not seen[slot, j, view]:
                    seen[slot, j, view] = True
                    row[v + 2] += 1
        for p in parents:
            cls = int(p[0])
            if cls in CLASSES:
                j = 50 + SLOT[cls]
                row[j] = max(row[j], p[1] * overlap(b, p[2:]))
        out[i, 3:] = row
    return out


# Cell offsets combine all twelve 8x8 orientation histograms in one reduction.
CELLS = ((np.arange(32)[:, None] // 8) * 3 + np.arange(24)[None, :] // 8) * 6


@njit(cache=True)
def distinct(boxes, threshold, min_side):
    kept = np.empty(len(boxes), np.int32)
    n = 0
    for i, box in enumerate(boxes):
        if min(box[2] - box[0], box[3] - box[1]) < min_side:
            continue
        if any_overlap(box, boxes, kept, n, threshold):
            continue
        kept[n] = i
        n += 1
    return kept[:n]


@njit(cache=True)
def any_overlap(box, boxes, kept, count, threshold):
    for j in range(count):
        if overlap(box, boxes[kept[j]]) > threshold:
            return True
    return False


def boxes_for(cls, raw, parent, shapes):
    seeds = [(p[1], p[2:]) for p in parent if p[0] == cls]
    allowed = {0: (0,), 1: (1, 3), 3: (1, 3), 7: (5, 7)}[cls]
    seeds.extend(
        (p[3] if p[2] == cls else p[3] * 0.6, p[4:]) for p in raw if p[2] in allowed
    )
    sources = {0: (1, 3), 1: (0,), 3: (0,), 7: ()}[cls]
    for source in sources:
        refs = raw[(raw[:, 2] == source) & (raw[:, 3] >= 0.30)]
        refs = refs[np.argsort(-refs[:, 3], kind="stable")]
        shape = shapes[f"{source if cls == 0 else cls}-{cls}"]
        for i in distinct(refs[:, 4:], 0.55, 0.0):
            p = refs[i]
            b = p[4:]
            guesses = np.clip(
                np.tile(b[:2], 2) + np.tile(b[2:] - b[:2], 2) * shape, 0, GRID
            )
            seeds.extend((0.45 * p[3], guess) for guess in guesses)
    if not seeds:
        return np.empty((0, 4))
    boxes = np.asarray([p[1] for p in sorted(seeds, key=lambda p: -p[0])])
    return boxes[distinct(boxes, 0.82, 2.0)]


def appearances(rgb, boxes):
    # Process the exact 24x32 OpenCV patches together. The guard rows give
    # each patch its own REFLECT_101 border before each Sobel derivative.
    height, width = rgb.shape[:2]
    rects = np.rint(boxes * np.array([width / 640, height / 384] * 2)).astype(int)
    rects, inverse = np.unique(rects, axis=0, return_inverse=True)
    patches = []
    for x, y, right, bottom in rects:
        patch = rgb[
            max(0, y) : min(height, max(y + 1, bottom)),
            max(0, x) : min(width, max(x + 1, right)),
        ]
        patches.append(cv2.resize(patch, (24, 32), interpolation=cv2.INTER_AREA))
    rois = np.stack(patches)
    n = len(rois)
    gray = cv2.cvtColor(rois.reshape(-1, 24, 3), cv2.COLOR_RGB2GRAY).reshape(n, 32, 24)
    padded = np.concatenate((gray[:, 1:2], gray, gray[:, -2:-1]), axis=1).reshape(
        -1, 24
    )
    dx = cv2.Sobel(padded, cv2.CV_32F, 1, 0)
    dy = cv2.Sobel(padded, cv2.CV_32F, 0, 1)
    mag, angle = cv2.cartToPolar(dx, dy, angleInDegrees=True)
    bins = (angle.reshape(n, 34, 24)[:, 1:-1] % 180 / 30).astype(int).clip(0, 5)
    offsets = np.arange(n)[:, None, None] * 72 + CELLS
    hist = np.bincount(
        (bins + offsets).ravel(),
        weights=mag.reshape(n, 34, 24)[:, 1:-1].ravel(),
        minlength=n * 72,
    ).reshape(n, 12, 6)
    small = (
        cv2.resize(gray.reshape(-1, 24), (6, n * 8), interpolation=cv2.INTER_AREA)
        .reshape(n, 48)
        .astype(float)
    )
    desc = np.concatenate(
        (
            (hist / (hist.sum(axis=2, keepdims=True) + 1)).reshape(n, 72),
            (small - small.mean(axis=1, keepdims=True))
            / (small.std(axis=1, keepdims=True) + 8),
            rois.mean(axis=(1, 2)) / 255,
        ),
        axis=1,
    )
    return desc[inverse].astype(np.float32)


@njit(cache=True)
def unexplained(boxes, fixed):
    keep = np.ones(len(boxes), np.bool_)
    for i, b in enumerate(boxes):
        for p in fixed:
            if overlap(b, p) >= 0.4:
                keep[i] = False
                break
    return boxes[keep]


def proposals(bundle, rgb, row, classifiers):
    rgb = np.asarray(rgb)
    observations = np.asarray(row["obs"], dtype=float).reshape(-1, 8)
    parents = np.asarray(
        [[d["class_id"], d["score"], *d["box"]] for d in row["base"]], dtype=float
    ).reshape(-1, 6)
    groups = {c: boxes_for(c, observations, parents, bundle["shapes"]) for c in TARGET}
    # The frozen fusion unconditionally drops same-class proposals overlapping
    # a base box at IoU >= .4. Bicycles also feed the rider proposal stage, so
    # all bicycle scores must remain available there.
    for c in (0, 3, 7):
        fixed = parents[parents[:, 0] == c, 2:]
        if len(fixed) and len(groups[c]):
            groups[c] = unexplained(groups[c], fixed)
    boxes = np.concatenate(list(groups.values()))
    if not len(boxes):
        return {}
    vec = np.hstack((geometry(boxes, observations, parents), appearances(rgb, boxes)))
    result = {}
    start = 0
    for c, items in groups.items():
        if not len(items):
            continue
        conf = classifiers[c].probability(vec[start : start + len(items)])
        start += len(items)
        result[str(c)] = [
            dict(class_id=c, box=box.tolist(), score=round(float(sc), 6))
            for box, sc in zip(items, conf, strict=True)
        ]
    return result


@njit(cache=True)
def tree_sum(samples, roots, children, features, thresholds, values):
    out = np.zeros(len(samples), np.float64)
    for j, sample in enumerate(samples):
        for root in roots:
            node = root
            while children[node, 0] >= 0:
                branch = 0 if sample[features[node]] <= thresholds[node] else 1
                node = children[node, branch]
            out[j] += values[node]
    return out


def pack(trees):
    roots = []
    links = []
    indices = []
    splits = []
    leaves = []
    offset = 0
    for left, right, feature, threshold, value in trees:
        roots.append(offset)
        link = np.column_stack((left, right)).astype(np.int32)
        link[link >= 0] += offset
        links.append(link)
        indices.append(feature)
        splits.append(threshold)
        leaves.append(value)
        offset += len(link)
    return (
        np.asarray(roots, np.int32),
        np.concatenate(links),
        np.concatenate(indices).astype(np.int32),
        np.concatenate(splits),
        np.concatenate(leaves),
    )


class PackedForest:
    def __init__(self, forest):
        def trees():
            for est in forest.estimators_:
                t = est.tree_
                counts = t.value[:, 0]
                yield (
                    t.children_left,
                    t.children_right,
                    t.feature,
                    t.threshold,
                    counts[:, 1] / counts.sum(axis=1),
                )

        self.nodes = pack(trees())
        self.count = len(forest.estimators_)

    def probability(self, samples):
        # sklearn decision trees convert input to float32 before traversing.
        return tree_sum(np.asarray(samples, dtype=np.float32), *self.nodes) / self.count


class PackedClassifier:
    def __init__(self, models):
        forest, boost = models

        def predictions():
            for iteration in boost._predictors:
                n = iteration[0].nodes
                if n["is_categorical"].any() or len(iteration) != 1:
                    raise ValueError("numeric binary verifier required")
                yield (
                    np.where(n["is_leaf"], -1, n["left"].astype(np.int32)),
                    np.where(n["is_leaf"], -1, n["right"].astype(np.int32)),
                    n["feature_idx"],
                    n["num_threshold"],
                    n["value"],
                )

        self.forest = PackedForest(forest)
        self.boost = pack(predictions())
        self.bias = float(boost._baseline_prediction[0, 0])

    def probability(self, samples):
        if not np.isfinite(samples).all():
            raise ValueError("nonfinite verifier input")
        f = self.forest.probability(samples)
        h = tree_sum(samples, *self.boost) + self.bias
        return (f + 1 / (1 + np.exp(-h))) / 2


@njit(cache=True)
def rider_strengths(seeds, verified, zoom, votes, bikes, people):
    """Score the frozen rider rule in stable seed order, retaining its accepted-box NMS."""
    result = np.zeros(len(seeds))
    accepted = np.empty(len(seeds), np.int64)
    count = 0
    for i, b in enumerate(seeds):
        duplicate = False
        for p in bikes:
            if overlap(b, p) >= 0.4:
                duplicate = True
                break
        if not duplicate:
            for j in accepted[:count]:
                if overlap(b, seeds[j]) > 0.87:
                    duplicate = True
                    break
        if duplicate:
            continue
        score = 0.0
        for p in verified:
            if overlap(b, p[1:]) >= 0.55:
                score = max(score, p[0])
        local = 0.0
        for p in zoom:
            if overlap(b, p[1:]) >= 0.5:
                local = max(local, p[0])
        if local < 0.45:
            aligned = False
            for p in people:
                if (
                    b[0] <= (p[0] + p[2]) / 2 <= b[2]
                    and p[1] < (b[1] + b[3]) / 2
                    and b[1] <= p[3] <= b[3] + 0.35 * (b[3] - b[1])
                ):
                    aligned = True
                    break
            if not aligned:
                continue
        global_score = 0.0
        views = 0
        seen = 0
        for p in votes:
            if overlap(b, p[2:]) >= 0.45:
                global_score = max(global_score, p[1])
                bit = 1 << int(p[0])
                if p[1] >= 0.2 and not (seen & bit):
                    seen |= bit
                    views += 1
        confirm = max(
            local,
            min(global_score, score),
            min(global_score, 0.8) if views >= 3 else 0.0,
        )
        strength = max((score * confirm) ** 0.5, (local * global_score) ** 0.5)
        if strength:
            accepted[count] = i
            count += 1
            result[i] = strength
    return result


def rider_suggestions(verified, parent, observations, local):
    zoom = [d for d in local if d["class_id"] == 1]
    seeds = sorted([*verified, *zoom], key=lambda d: -d["score"])
    if not seeds:
        return []

    def scored(rows):
        return np.array([[d["score"], *d["box"]] for d in rows], float).reshape(-1, 5)

    strength = rider_strengths(
        np.array([d["box"] for d in seeds], float),
        scored(verified),
        scored(zoom),
        np.array(
            [[p[0], p[3], *p[4:]] for p in observations if p[2] == 1], float
        ).reshape(-1, 6),
        np.array([p["box"] for p in parent if p["class_id"] == 1], float).reshape(
            -1, 4
        ),
        np.array(
            [
                p["box"]
                for p in [*parent, *local]
                if p["class_id"] == 0 and p["score"] >= 0.35
            ],
            float,
        ).reshape(-1, 4),
    )
    return [
        dict(class_id=1, box=d["box"], score=round(float(s), 6))
        for d, s in zip(seeds, strength, strict=True)
        if s
    ]

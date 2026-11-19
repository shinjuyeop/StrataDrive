"""Fuse independent RGB views with class-specific, location-independent proposal verification."""

import argparse
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path

import cv2
import joblib
import numpy as np
from sklearn.cluster import KMeans
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.ensemble import HistGradientBoostingClassifier

from multiview_observations import CLASSES, data
from person_pair_candidate import dump
from fresh_quality_2k_review import read
from run_resolution_v2 import quality
from fresh_quality_2k_score import PROTOCOL
from quality_benchmark import relative
from bus_recall_fit import iou

TARGET = (0, 1, 3, 7)
GRID = np.array([640, 384, 640, 384], float)


def records(path):
    with gzip.open(path, "rt") as stream:
        for line in stream:
            yield json.loads(line)


def overlap(box, others):
    if len(others) == 0:
        return np.zeros(0)
    inter = np.maximum(
        0, np.minimum(box[2:], others[:, 2:]) - np.maximum(box[:2], others[:, :2])
    ).prod(axis=1)
    return inter / np.maximum(
        1e-7,
        (box[2:] - box[:2]).prod()
        + (others[:, 2:] - others[:, :2]).prod(axis=1)
        - inter,
    )


def prototypes(rows):
    ratios = defaultdict(list)
    for row in rows:
        people = {
            o["instance_id"]: np.array(o["box"])
            for o in row["gt"]
            if o["class_id"] == 0 and 13 in o["semantic_tags"]
        }
        for obj in row["gt"]:
            if obj["class_id"] not in (1, 3) or obj["instance_id"] not in people:
                continue
            bike = np.array(obj["box"])
            rider = people[obj["instance_id"]]
            for src, dst, c in ((bike, rider, 0), (rider, bike, obj["class_id"])):
                ratios[(obj["class_id"], c)].append(
                    (dst - np.tile(src[:2], 2)) / np.tile(src[2:] - src[:2], 2)
                )
    result = {}
    for (bike, c), samples in ratios.items():
        model = KMeans(n_clusters=4, n_init=5, random_state=23).fit(samples)
        result[f"{bike}-{c}"] = model.cluster_centers_.tolist()
    return result


def candidate_boxes(c, raw, base, shapes):
    seeds = [(d["score"], d["box"]) for d in base if d["class_id"] == c]
    allowed = {0: (0,), 1: (1, 3), 3: (1, 3), 7: (5, 7)}[c]
    seeds.extend(
        (p[3] * (1 if int(p[2]) == c else 0.6), p[4:])
        for p in raw
        if int(p[2]) in allowed
    )
    sources = (1, 3) if c == 0 else ((0,) if c in (1, 3) else ())
    for src in sources:
        refs = []
        for p in sorted(
            (p for p in raw if p[2] == src and p[3] >= 0.30), key=lambda p: -p[3]
        ):
            if any(iou(p[4:], r[4:]) > 0.55 for r in refs):
                continue
            refs.append(p)
            box = np.array(p[4:])
            wh = np.tile(box[2:] - box[:2], 2)
            for v in shapes[f"{src if c == 0 else c}-{c}"]:
                guess = (np.tile(box[:2], 2) + wh * v).clip(0, GRID)
                seeds.append((0.45 * p[3], guess))
    kept = []
    for _, box in sorted(seeds, key=lambda v: -v[0]):
        if min(box[2] - box[0], box[3] - box[1]) < 2 or any(
            iou(box, b) > 0.82 for b in kept
        ):
            continue
        kept.append(np.asarray(box))
    return kept


def appearance(rgb, box):
    h, w, _ = rgb.shape
    x, y, right, bottom = np.rint(box * np.array([w / 640, h / 384] * 2)).astype(int)
    patch = rgb[
        max(0, y) : min(h, max(y + 1, bottom)), max(0, x) : min(w, max(x + 1, right))
    ]
    if not patch.size:
        raise ValueError("empty ROI")
    roi = cv2.resize(patch, (24, 32), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)
    dx = cv2.Sobel(gray, cv2.CV_32F, 1, 0)
    dy = cv2.Sobel(gray, cv2.CV_32F, 0, 1)
    mag, angle = cv2.cartToPolar(dx, dy, angleInDegrees=True)
    bins = (angle % 180 / 30).astype(int).clip(0, 5)
    feat = []
    for iy in range(0, 32, 8):
        for ix in range(0, 24, 8):
            r = np.s_[iy : iy + 8, ix : ix + 8]
            hist = np.bincount(bins[r].ravel(), weights=mag[r].ravel(), minlength=6)
            feat.extend(hist / (hist.sum() + 1))
    # Normalized appearance preserves shape under weather and exposure changes.
    small = cv2.resize(gray, (6, 8), interpolation=cv2.INTER_AREA).astype(float)
    feat.extend(((small - small.mean()) / (small.std() + 8)).ravel())
    feat.extend((roi.mean(axis=(0, 1)) / 255).tolist())
    return feat


def describe(rgb, c, box, raw, parent):
    w, h = box[2:] - box[:2]
    out = [np.log1p(w), np.log1p(h), w / h]
    boxes = raw[:, 4:]
    ov = overlap(box, boxes)
    for k in CLASSES:
        mask = raw[:, 2] == k
        for lo in (0.25, 0.5, 0.75):
            v = raw[mask & (ov >= lo)]
            out.extend([v[v[:, 1] == j, 3].max(initial=0) for j in (0, 1)])
            out.append(len(np.unique(v[v[:, 3] >= 0.30, 0])))
        out.append(np.max(ov[mask] * raw[mask, 3], initial=0))
    for d in (0, 1, 3, 5, 7):
        out.append(
            max(
                (p["score"] * iou(p["box"], box) for p in parent if p["class_id"] == d),
                default=0,
            )
        )
    return out + appearance(rgb, box)


def features(image, row, shapes):
    rgb = np.asarray(image)
    raw = np.asarray(row["obs"], dtype=float).reshape(-1, 8)
    out = {}
    for c in TARGET:
        boxes = candidate_boxes(c, row["obs"], row["base"], shapes)
        if boxes:
            out[c] = (
                np.asarray(boxes, dtype=float),
                np.asarray(
                    [describe(rgb, c, b, raw, row["base"]) for b in boxes], np.float32
                ),
            )
    return out


def paired_rows(work, name, run=None):
    # Resolve training/development originals by SHA in exactly the recorded order.
    for row, (im, g, key, scene) in zip(
        records(work / (name + ".jsonl.gz")), data(name, run), strict=True
    ):
        if row["rgb"] != key or row["gt"] != g["objects"] or scene != row["scene"]:
            raise ValueError("input association")
        yield row, im


def training_rows(work):
    """Stream complete rows while the GPU collector writes its temporary gzip file."""
    import time

    dest = work / "train.jsonl.gz"
    count = 0
    while True:
        complete = dest.exists()
        path = dest if complete else dest.with_suffix(".partial")
        try:
            for i, row in enumerate(records(path)):
                if i >= count:
                    count += 1
                    yield row
        except (FileNotFoundError, EOFError):
            if complete:
                raise
        if complete:
            return
        time.sleep(5)


def init_worker(shapes):
    global train_shapes
    train_shapes = shapes
    cv2.setNumThreads(1)


def training_features(item):
    from PIL import Image

    row, path = item
    values = {}
    with Image.open(path) as img:
        image = img.convert("RGB")
    if hashlib.sha256(image.tobytes()).hexdigest() != row["rgb"]:
        raise ValueError("training image association")
    for c, (boxes, vec) in features(image, row, train_shapes).items():
        gt = np.asarray([o["box"] for o in row["gt"] if o["class_id"] == c]).reshape(
            -1, 4
        )
        y = np.array([overlap(b, gt).max(initial=0) >= 0.5 for b in boxes])
        values[c] = vec, y
    return values


def fit(work):
    from multiprocessing import Pool
    from person_pair_candidate import frames
    from person_zoom_validation import CACHE

    sources = {}
    labels = []
    for paired in (True, False):
        for path, g, key, _ in frames(CACHE, "train", paired):
            if (
                not paired
                and not any(o["class_id"] in TARGET for o in g["objects"])
                and int(key[:4], 16) % 6
            ):
                continue
            if key in sources:
                raise ValueError("duplicate training RGB")
            sources[key] = path
            labels.append(dict(gt=g["objects"]))
    shapes = prototypes(labels)
    xs = defaultdict(list)
    ys = defaultdict(list)

    def tasks():
        seen = set()
        for row in training_rows(work):
            key = row["rgb"]
            if key in seen:
                raise ValueError("duplicate trace")
            seen.add(key)
            yield row, sources[key]
        if seen != sources.keys():
            raise ValueError("training denominator")

    with Pool(6, initializer=init_worker, initargs=(shapes,)) as pool:
        for i, values in enumerate(pool.imap(training_features, tasks(), chunksize=3)):
            for c, (vec, y) in values.items():
                xs[c].append(vec)
                ys[c].append(y)
            if i % 100 == 0:
                print("features", i, flush=True)
    models = {}
    summary = {}
    for c in TARGET:
        x = np.concatenate(xs[c])
        y = np.concatenate(ys[c])
        summary[c] = [len(y), int(y.sum())]
        forest = ExtraTreesClassifier(
            n_estimators=72,
            min_samples_leaf=3,
            max_features=0.55,
            n_jobs=4,
            random_state=81,
            class_weight="balanced_subsample",
        ).fit(x, y)
        boosted = HistGradientBoostingClassifier(
            max_iter=110, min_samples_leaf=18, max_leaf_nodes=15, random_state=81
        ).fit(x, y)
        models[c] = (forest, boosted)
    joblib.dump(
        dict(shapes=shapes, models=models), work / "verifier.joblib", compress=3
    )
    dump(
        work / "training.json",
        dict(
            samples_and_positives=summary,
            model_sha256=hashlib.sha256(
                (work / "verifier.joblib").read_bytes()
            ).hexdigest(),
        ),
    )


def predict_proposals(bundle, image, row):
    result = {}
    for c, (boxes, vec) in features(image, row, bundle["shapes"]).items():
        f, b = bundle["models"][c]
        conf = (f.predict_proba(vec)[:, 1] + b.predict_proba(vec)[:, 1]) / 2
        result[str(c)] = [
            dict(class_id=c, box=box.tolist(), score=round(float(score), 6))
            for box, score in zip(boxes, conf, strict=True)
        ]
    return result


def combine(base, suggestions, policy):
    result = list(base)
    for c in TARGET:
        picked = [o["box"] for o in base if o["class_id"] == c]
        for d in sorted(suggestions.get(str(c), []), key=lambda v: -v["score"]):
            if d["score"] < policy[str(c)]:
                break
            if any(iou(d["box"], p) >= 0.4 for p in picked):
                continue
            picked.append(d["box"])
            result.append(d)
    return result


def load_verifier(work):
    bundle = joblib.load(work / "verifier.joblib")
    for forest, _ in bundle["models"].values():
        forest.n_jobs = 1
    return bundle


def verified_row(bundle, row, image):
    return dict(
        rgb=row["rgb"],
        base=row["base"],
        new=predict_proposals(bundle, image, row),
        gt=row["gt"],
        excluded=row["excluded"],
    )


def init_validation_worker(work):
    global validation_bundle
    cv2.setNumThreads(1)
    validation_bundle = load_verifier(work)


def verify_archive_row(item):
    from PIL import Image

    row, (path, gt, key, _) = item
    with Image.open(path) as im:
        image = im.convert("RGB")
    if (
        row["gt"] != gt["objects"]
        or row["rgb"] != key
        or hashlib.sha256(image.tobytes()).hexdigest() != key
    ):
        raise ValueError("validation image association")
    return verified_row(validation_bundle, row, image)


def cache_predictions(work, name, run=None):
    from multiprocessing import Pool
    from person_pair_candidate import frames
    from person_zoom_validation import CACHE

    dest = work / (name + "-verified.jsonl.gz")
    temp = dest.with_suffix(".partial")
    with gzip.open(temp, "wt", compresslevel=3) as out:

        def write_rows(rows):
            for r in rows:
                out.write(json.dumps(r, separators=(",", ":")) + "\n")

        if run is None and name == "validation":
            pairs = zip(
                records(work / "validation.jsonl.gz"),
                frames(CACHE, "validation", False),
                strict=True,
            )
            with Pool(6, initializer=init_validation_worker, initargs=(work,)) as pool:
                write_rows(pool.imap(verify_archive_row, pairs, chunksize=4))
        else:
            bundle = load_verifier(work)
            write_rows(
                verified_row(bundle, r, im) for r, im in paired_rows(work, name, run)
            )
    temp.rename(dest)


def score_run(run, rows, policy):
    scores = []
    traces = []
    for r, src, gt, scene in zip(
        rows,
        read(run / "images.json")["frames"],
        read(run / "evaluation-only-gt.json")["frames"],
        read(run / "benchmark.json")["scenes"],
        strict=True,
    ):
        if (
            r["rgb"] != src["rgb_sha256"]
            or not src["scene"] == gt["scene"] == scene["scene"]
            or ("gt" in r and r["gt"] != gt["objects"])
        ):
            raise ValueError("score pairing")
        pred = combine(r["base"], r["new"], policy)
        scores.append((scene, gt, pred, True, False, None))
        traces.append(dict(rgb=r["rgb"], detections=pred))
    card = {k: v for k, v in quality(scores).items() if k != "records"}
    rel = relative(read(run / "baseline/score.json"), card, read(PROTOCOL))
    return dict(
        card=card,
        relative=rel,
        passed=card["absolute_quality"] == "PASS" and rel["status"] == "PASS",
    ), traces


class Detector:
    """Fixed offline RGB candidate with no scene or annotation input."""

    def __init__(self, work, selection):
        from parking_onnx_replay import load_session
        from person_proposal_diagnosis import BUNDLE

        path = work / "verifier.joblib"
        if hashlib.sha256(path.read_bytes()).hexdigest() != selection["model_sha256"]:
            raise ValueError("selected verifier changed")
        self.bundle = joblib.load(path)
        for forest, _ in self.bundle["models"].values():
            forest.n_jobs = 1
        self.session, self.spec = load_session(BUNDLE)
        self.policy = selection["thresholds"]

    def observe(self, image):
        from multiview_observations import observe

        base, obs = observe(image, self.session, self.spec)
        suggestions = predict_proposals(self.bundle, image, dict(obs=obs, base=base))
        return base, suggestions

    def predict(self, image):
        base, suggestions = self.observe(image)
        return combine(base, suggestions, self.policy)


def evaluate_run(run, work, selection, name="holdout"):
    import time
    from PIL import Image
    from fresh_quality_2k_review import rgb_bytes
    from physical_ai.perception.camera_resolution_v1 import unpack

    model = Detector(work, selection)
    binding = dict(
        selection=hashlib.sha256(
            json.dumps(selection, sort_keys=True).encode()
        ).hexdigest(),
        images=hashlib.sha256((run / "images.json").read_bytes()).hexdigest(),
    )
    dest = work / (name + "-verified.jsonl.gz")
    if not dest.exists():
        tmp = dest.with_suffix(".partial")
        with gzip.open(tmp, "wt", compresslevel=3) as out:
            for f in read(run / "images.json")["frames"]:
                rgb = rgb_bytes(unpack(run / "dataset", f["rgb_raw"], 2560, 1536))
                if hashlib.sha256(rgb).hexdigest() != f["rgb_sha256"]:
                    raise ValueError("holdout RGB")
                im = Image.frombytes("RGB", (2560, 1536), rgb)
                start = time.perf_counter()
                base, new = model.observe(im)
                pred = combine(base, new, model.policy)
                elapsed = time.perf_counter() - start
                out.write(
                    json.dumps(
                        dict(
                            binding=binding,
                            rgb=f["rgb_sha256"],
                            base=base,
                            new=new,
                            detections=pred,
                            elapsed_s=elapsed,
                        ),
                        separators=(",", ":"),
                    )
                    + "\n"
                )
        tmp.rename(dest)
    rows = list(records(dest))
    if len(rows) != 81 or any(r["binding"] != binding for r in rows):
        raise ValueError("evaluation manifest or selected model changed")
    score, traces = score_run(run, rows, selection["thresholds"])
    if any(
        t["detections"] != r["detections"] for t, r in zip(traces, rows, strict=True)
    ):
        raise ValueError("detector replay drift")
    dump(work / (name + "-score.json"), score)
    dump(work / (name + "-detections.json"), traces)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("fit", "cache"))
    p.add_argument("work", type=Path)
    p.add_argument("--name")
    p.add_argument("--run", type=Path)
    a = p.parse_args()
    if a.action == "fit":
        fit(a.work)
    else:
        cache_predictions(a.work, a.name, a.run)

"""Learn vehicle type from independent YOLOX and D-FINE crop responses under box competition."""

import argparse
from collections import Counter
import hashlib
import time

import joblib
import numpy as np
from PIL import Image
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier

import vehicle_conflict as prior
from vehicle_class_plan import ROOT, WORK, read
from vehicle_conflict import (
    cycle,
    records,
    score_run,
    write_stream,
    dump,
    iou,
    containment,
    data,
)
from fresh_quality_2k_score import BASELINE
from physical_ai.perception.yolox import YoloX, GRIDS, STRIDES, preprocess
from physical_ai.perception.contract import CameraFrame, FrameIdentity
from physical_ai.perception.camera_resolution_v1 import unpack
from fresh_quality_2k_review import rgb_bytes
from multiview_detector import overlap

FIX = read(ROOT / "docs/test-plan/evidence/m10_vehicle_conflict_v1/selection.json")
TYPE = (2, 7, 5)


def sessions():
    return (*prior.model_pair(), YoloX(BASELINE, "cuda"))


def recognition(image, box, detector, yolox):
    b = np.asarray(box)
    cx, cy = (b[:2] + b[2:]) / 2
    width = min(640, max(55, 3.5 * (b[2] - b[0]), 5 * (b[3] - b[1])))
    height = width * 0.6
    x = np.clip(cx - width / 2, 0, 640 - width)
    y = np.clip(cy - height / 2, 0, 384 - height)
    scale = np.array([image.width / 640, image.height / 384] * 2)
    rect = np.rint(np.array([x, y, x + width, y + height]) * scale).astype(int)
    patch = image.crop(tuple(rect))
    bounds = rect / scale
    target = (b - np.tile(bounds[:2], 2)) / np.tile(
        (bounds[2:] - bounds[:2]) / [640, 384], 2
    )
    raw = prior.forward(patch, detector.session, detector.spec)
    feat = []
    for head in ("original_", ""):
        boxes = raw[head + "boxes"].reshape(-1, 4)
        ov = overlap(target, boxes)
        labels = raw[head + "labels"].ravel()
        conf = raw[head + "scores"].ravel()
        for c in TYPE:
            mask = labels == c
            feat.extend(
                [conf[mask & (ov >= t)].max(initial=0) for t in (0.3, 0.5, 0.7)]
            )
            feat.append((ov[mask] * conf[mask]).max(initial=0))
    rgb = patch.resize((640, 384), Image.Resampling.BILINEAR).tobytes()
    tensor, _ = preprocess(CameraFrame(FrameIdentity(1, 1, 1, 1), rgb))
    a = yolox.session.run(None, {"images": tensor})[0][0]
    centers = (a[:, :2] + GRIDS) * STRIDES
    sizes = np.exp(a[:, 2:4].astype(float)) * STRIDES
    boxes = np.column_stack((centers - sizes / 2, centers + sizes / 2))
    ov = overlap(target, boxes)
    for c in TYPE:
        confidence = a[:, 4] * a[:, 5 + c]
        feat.extend(confidence[ov >= t].max(initial=0) for t in (0.3, 0.5, 0.7))
        feat.append((ov * confidence).max(initial=0))
    return np.asarray(feat).tolist()


def train():
    detector, _, yolo = sessions()
    xs = []
    ys = []
    for r, (im, g, key, _) in zip(
        records(cycle.PARENT / "train.jsonl.gz"), data("train"), strict=True
    ):
        if r["rgb"] != key or hashlib.sha256(im.tobytes()).hexdigest() != key:
            raise ValueError("train RGB")
        # Include observed car boxes even when the frozen parent gave a real truck a car label.
        for c in (2, 7):
            truth = [o["box"] for o in g["objects"] if o["class_id"] == c]
            candidates = []
            for gt in truth:
                matches = [
                    p
                    for p in r["base"]
                    if p["class_id"] == 2 and iou(p["box"], gt) >= 0.5
                ]
                box = max(matches, key=lambda v: v["score"])["box"] if matches else gt
                candidates.append(box)
            if len(candidates) > 2:
                rng = np.random.default_rng(int(key[:12], 16))
                candidates = [
                    candidates[j] for j in rng.choice(len(candidates), 2, replace=False)
                ]
            for b in candidates:
                xs.append(recognition(im, b, detector, yolo))
                ys.append(c == 2)
    forest = ExtraTreesClassifier(
        n_estimators=100,
        min_samples_leaf=4,
        class_weight="balanced",
        random_state=23,
        n_jobs=3,
    ).fit(xs, ys)
    boosted = HistGradientBoostingClassifier(
        max_leaf_nodes=9, max_iter=80, random_state=23
    ).fit(xs, ys)
    forest.n_jobs = 1
    joblib.dump((forest, boosted), WORK / "arbiter.joblib", compress=3)
    dump(
        WORK / "training.json",
        dict(
            samples=len(ys),
            cars=sum(ys),
            trucks=len(ys) - sum(ys),
            sha256=hashlib.sha256((WORK / "arbiter.joblib").read_bytes()).hexdigest(),
        ),
    )


def classifier():
    if (
        hashlib.sha256((WORK / "arbiter.joblib").read_bytes()).hexdigest()
        != read(WORK / "training.json")["sha256"]
    ):
        raise ValueError("arbiter identity")
    return joblib.load(WORK / "arbiter.joblib")


def probability(features, models):
    return float(np.mean([m.predict_proba([features])[0, 1] for m in models]))


def competition(image, parent, detector, yolo, models):
    cars = [d for d in parent if d["class_id"] == 2 and d["score"] >= 0.75]
    checks = {}
    cache = {}
    for i, d in enumerate(parent):
        if d["class_id"] != 7:
            continue
        scores = [
            (containment(d["box"], v["box"]), v["score"], k) for k, v in enumerate(cars)
        ]
        if not scores:
            continue
        covered, _, k = max(scores)
        if covered < 0.5:
            continue
        if k not in cache:
            cache[k] = probability(
                recognition(image, cars[k]["box"], detector, yolo), models
            )
        checks[str(i)] = dict(car_evidence=cache[k], covered=covered)
    return checks


def make(name):
    detector, _, yolo = sessions()
    models = classifier()
    if name == "calibration":

        def rows():
            for n in ("validation", "dev90", "dev608"):
                for r, (im, g, k, _) in zip(
                    records(cycle.PARENT / (n + ".jsonl.gz")),
                    data(n, prior.DEV.get(n)),
                    strict=True,
                ):
                    if r["rgb"] != k or hashlib.sha256(im.tobytes()).hexdigest() != k:
                        raise ValueError("challenge RGB")
                    for car in (
                        p
                        for p in r["base"]
                        if p["class_id"] == 2 and p["score"] >= 0.75
                    ):
                        if not any(
                            v[2] == 7
                            and iou(v[4:], car["box"]) > 0.4
                            and containment(v[4:], car["box"]) >= 0.5
                            for v in r["obs"]
                        ):
                            continue
                        types = {
                            o["class_id"]
                            for o in g["objects"]
                            if iou(car["box"], o["box"]) >= 0.5
                        }
                        if types not in ({2}, {7}):
                            continue
                        yield dict(
                            rgb=k,
                            group=n,
                            truth=next(iter(types)),
                            car_evidence=probability(
                                recognition(im, car["box"], detector, yolo), models
                            ),
                        )
    else:

        def rows():
            for r, (im, g, k, _) in zip(
                records(prior.WORK / (name + ".jsonl.gz")),
                data(name, prior.DEV.get(name)),
                strict=True,
            ):
                if (
                    r["rgb"] != k
                    or g["objects"] != r["gt"]
                    or hashlib.sha256(im.tobytes()).hexdigest() != k
                ):
                    raise ValueError("development RGB")
                ds = prior.filter_detections(r["parent"], r["checks"], FIX["threshold"])
                yield dict(
                    rgb=k,
                    gt=r["gt"],
                    parent=ds,
                    checks=competition(im, ds, detector, yolo, models),
                )

    write_stream(WORK / (name + ".jsonl.gz"), rows())


def select():
    rows = list(records(WORK / "calibration.jsonl.gz"))
    counts = Counter(r["truth"] for r in rows)
    native = {n: list(records(WORK / (n + ".jsonl.gz"))) for n in prior.DEV}
    arch = list(records(WORK / "validation.jsonl.gz"))
    sites = {
        r["source"]: r["site"]
        for r in read(cycle.PARK / "cache/manifest.json")["validation"]
    }
    if len(arch) != 699 or any(len(ds) != 81 for ds in native.values()):
        raise ValueError("validation denominator")
    options = []
    best = None
    for t in [1.01, *np.arange(0.99, 0.04, -0.025)]:
        t = float(round(t, 3))
        fixed = [prior.resolved(r, t) for r in arch]
        summaries = {
            n: cycle.archive([r for r in fixed if sites[r["rgb"]] == n], 1.01)
            for n in sorted(set(sites.values()))
        }
        cards = {
            n: score_run(prior.DEV[n], [prior.resolved(r, t) for r in ds], cycle.OFF)[0]
            for n, ds in native.items()
        }
        rate = sum(r["car_evidence"] >= t for r in rows if r["truth"] == 2) / counts[2]
        retain = sum(r["car_evidence"] < t for r in rows if r["truth"] == 7) / counts[7]
        eligible = (
            all(v["passed"] for v in cards.values())
            and all(
                v["precision"] >= 0.85 and v["recall"] >= 0.80
                for v in summaries.values()
            )
            and retain >= 0.70
        )
        if t == 1.01:
            parent = summaries
        lost = sum(parent[n]["tp"] - s["tp"] for n, s in summaries.items())
        rank = (rate, -lost, retain, t)
        options.append(
            dict(
                t=t,
                eligible=eligible,
                car_rejected=rate,
                truck_retained=retain,
                lost=lost,
            )
        )
        if eligible and (best is None or rank > best[0]):
            best = (
                rank,
                dict(
                    passed=True,
                    threshold=t,
                    thresholds=cycle.OFF,
                    classes=cards,
                    archive=summaries,
                    training_sha256=read(WORK / "training.json")["sha256"],
                ),
            )
    if best is None:
        raise ValueError("qualification")
    dump(
        WORK / "selection.json", dict(best[1], options=options, challenge_counts=counts)
    )


def evaluate(run, name, selection, retained=None):
    model, app, yolo = sessions()
    models = classifier()
    if selection["training_sha256"] != read(WORK / "training.json")["sha256"]:
        raise ValueError("selection identity")
    old = iter(records(retained)) if retained else None
    rows = []
    for f in read(run / "images.json")["frames"]:
        raw = rgb_bytes(unpack(run / "dataset", f["rgb_raw"], 2560, 1536))
        if hashlib.sha256(raw).hexdigest() != f["rgb_sha256"]:
            raise ValueError("evaluation RGB")
        im = Image.frombytes("RGB", (2560, 1536), raw)
        start = time.perf_counter()
        if old is None:
            pred = prior.parent_predictions(model, im)
            ds = prior.filter_detections(
                pred, prior.evidence(im, pred, model, app), FIX["threshold"]
            )
        else:
            r = next(old)
            if r["rgb"] != f["rgb_sha256"]:
                raise ValueError("paired parent")
            ds = r["detections"]
        checks = competition(im, ds, model, yolo, models)
        det = prior.filter_detections(ds, checks, selection["threshold"])
        rows.append(
            dict(
                rgb=f["rgb_sha256"],
                original_parent=ds,
                checks=checks,
                base=det,
                new={},
                detections=det,
                elapsed_s=time.perf_counter() - start,
            )
        )
    if old is not None and next(old, None) is not None:
        raise ValueError("parent cardinality")
    write_stream(WORK / (name + "-verified.jsonl.gz"), rows)
    score, _ = score_run(run, rows, cycle.OFF)
    dump(WORK / (name + "-score.json"), score)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("train", "cache", "select"))
    p.add_argument("name", nargs="?")
    a = p.parse_args()
    if a.action == "train":
        train()
    elif a.action == "cache":
        make(a.name)
    else:
        select()

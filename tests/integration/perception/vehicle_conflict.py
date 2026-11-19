"""Disambiguate a truck hypothesis that competes for the same pixels as a passenger car."""

import argparse
from collections import Counter
import gzip
import hashlib
import json
import time

import joblib
import numpy as np
from PIL import Image
from sklearn.ensemble import ExtraTreesClassifier

import cycle_transfer as cycle
from bus_recall import forward
from bus_recall_fit import iou
from multiview_detector import Detector, appearance, combine, records, score_run
from multiview_observations import data
from person_pair_candidate import dump
from vehicle_conflict_plan import WORK
from fresh_quality_2k_review import read, rgb_bytes
from physical_ai.perception.camera_resolution_v1 import unpack

PARENT = cycle.WORK
POLICY = read(cycle.EVIDENCE / "selection.json")["thresholds"]
DEV = dict(cycle.DEV, dev15=WORK / "native/runs/evaluation-development-01")
LIMIT = np.array([640, 384, 640, 384], float)


def area(box):
    return (box[2] - box[0]) * (box[3] - box[1])


def containment(inner, outer):
    w = max(0, min(inner[2], outer[2]) - max(inner[0], outer[0]))
    h = max(0, min(inner[3], outer[3]) - max(inner[1], outer[1]))
    return w * h / max(1e-6, area(inner))


def appearance_features(rgb, b):
    b = np.asarray(b, dtype=float)
    context = np.tile((b[2:] - b[:2]) * 0.16, 2) * [-1, -1, 1, 1]
    return appearance(rgb, b) + appearance(rgb, (b + context).clip(0, LIMIT))


def train():
    xs = []
    ys = []
    for image, g, key, _ in data("train"):
        if hashlib.sha256(image.tobytes()).hexdigest() != key:
            raise ValueError("train RGB")
        rgb = np.asarray(image)
        for o in g["objects"]:
            if o["class_id"] not in (2, 7):
                continue
            b = np.array(o["box"])
            for delta in (
                (0, 0, 0, 0),
                (-0.06, -0.05, 0.06, 0.05),
                (0.08, 0.02, 0.12, -0.04),
            ):
                box = (b + np.tile(b[2:] - b[:2], 2) * delta).clip(0, LIMIT)
                xs.append(appearance_features(rgb, box))
                ys.append(o["class_id"] == 2)
    m = ExtraTreesClassifier(
        n_estimators=96,
        min_samples_leaf=2,
        max_features=0.65,
        class_weight="balanced",
        random_state=177,
        n_jobs=4,
    ).fit(xs, ys)
    m.n_jobs = 1
    joblib.dump(m, WORK / "appearance.joblib", compress=3)
    dump(
        WORK / "training.json",
        dict(
            vehicles={str(k): v for k, v in Counter(ys).items()},
            sha256=hashlib.sha256(
                (WORK / "appearance.joblib").read_bytes()
            ).hexdigest(),
        ),
    )


def crop_evidence(image, box, session, spec):
    b = np.asarray(box)
    cx, cy = (b[:2] + b[2:]) / 2
    width = min(640, max(64, 4 * (b[2] - b[0]), 5.5 * (b[3] - b[1])))
    height = width * 384 / 640
    x = np.clip(cx - width / 2, 0, 640 - width)
    y = np.clip(cy - height / 2, 0, 384 - height)
    scale = np.array([image.width / 640, image.height / 384] * 2)
    rect = np.rint(np.array([x, y, x + width, y + height]) * scale).astype(int)
    bounds = rect / scale
    ratio = np.tile((bounds[2:] - bounds[:2]) / [640, 384], 2)
    out = forward(image.crop(tuple(rect)), session, spec)
    votes = {2: 0.0, 7: 0.0, 5: 0.0}
    for prefix in ("original_", ""):
        boxes = out[prefix + "boxes"].reshape(-1, 4) * ratio + np.tile(bounds[:2], 2)
        labels = out[prefix + "labels"].ravel()
        scores = out[prefix + "scores"].ravel()
        for ix in np.flatnonzero(np.isin(labels, (2, 5, 7)) & (scores > 0.05)):
            if iou(boxes[ix], b) >= 0.35:
                cls = int(labels[ix])
                votes[cls] = max(votes[cls], float(scores[ix]))
    return votes


def evidence(image, detections, model, appearance_model):
    cars = [d for d in detections if d["class_id"] == 2 and d["score"] >= 0.75]
    candidates = {}
    rgb = None
    local = {}
    for i, d in enumerate(detections):
        if d["class_id"] != 7:
            continue
        overlaps = [
            (containment(d["box"], car["box"]), car["score"], j)
            for j, car in enumerate(cars)
        ]
        if not overlaps:
            continue
        covered, conf, j = max(overlaps)
        if covered < 0.65:
            continue
        car = cars[j]
        if j not in local:
            if rgb is None:
                rgb = np.asarray(image)
            app = float(
                appearance_model.predict_proba([appearance_features(rgb, car["box"])])[
                    0, 1
                ]
            )
            votes = crop_evidence(image, car["box"], model.session, model.spec)
            local[j] = (app, votes)
        app, votes = local[j]
        # Independent appearance and the localized detector each compare the vehicle's type.
        local_car = votes[2] / max(0.15, votes[2] + max(votes[5], votes[7]))
        car_evidence = (app + local_car) / 2
        candidates[str(i)] = dict(
            covered=covered,
            car_score=conf,
            truck_score=d["score"],
            appearance_car=app,
            local_car=votes[2],
            local_truck=votes[7],
            local_bus=votes[5],
            car_evidence=car_evidence,
        )
    return candidates


def filter_detections(detections, candidates, threshold):
    return [
        d
        for i, d in enumerate(detections)
        if str(i) not in candidates or candidates[str(i)]["car_evidence"] < threshold
    ]


def write_stream(path, items):
    tmp = path.with_suffix(".partial")
    with gzip.open(tmp, "wt") as stream:
        for row in items:
            stream.write(json.dumps(row, separators=(",", ":")) + "\n")
    tmp.rename(path)


def restored_cycle(base, new):
    return combine(cycle.resolve_vehicle_conflicts(base), new, POLICY)


def model_pair():
    if (
        hashlib.sha256((WORK / "appearance.joblib").read_bytes()).hexdigest()
        != read(WORK / "training.json")["sha256"]
    ):
        raise ValueError("appearance model")
    return Detector(cycle.PARENT, cycle.FIX), joblib.load(WORK / "appearance.joblib")


def parent_predictions(model, image):
    fixed, sug = cycle.expand(model, image, *cycle.predict_raw(model, image))
    return restored_cycle(fixed, {"1": sug})


def cache(name):
    model, app = model_pair()
    run = DEV.get(name)

    def rows():
        if name == "dev15":
            for im, g, key in cycle.rows_from_run(run):
                ds = parent_predictions(model, im)
                yield dict(
                    rgb=key,
                    gt=g["objects"],
                    parent=ds,
                    checks=evidence(im, ds, model, app),
                )
        else:
            for r, (im, g, key, _) in zip(
                records(PARENT / (name + ".jsonl.gz")), data(name, run), strict=True
            ):
                if (
                    r["rgb"] != key
                    or r["gt"] != g["objects"]
                    or hashlib.sha256(im.tobytes()).hexdigest() != key
                ):
                    raise ValueError("cache association")
                ds = restored_cycle(r["base"], r["new"])
                yield dict(
                    rgb=key,
                    gt=g["objects"],
                    parent=ds,
                    checks=evidence(im, ds, model, app),
                )

    write_stream(WORK / (name + ".jsonl.gz"), rows())


def challenge():
    """Evaluate type verification where a real truck proposal competes for a car detection."""
    detector, app = model_pair()
    diagnostics = []
    for name in ("validation", "dev90", "dev608"):
        for r, (image, truth, key, _) in zip(
            records(cycle.PARENT / (name + ".jsonl.gz")),
            data(name, DEV.get(name)),
            strict=True,
        ):
            if r["rgb"] != key or hashlib.sha256(image.tobytes()).hexdigest() != key:
                raise ValueError("challenge RGB")
            for car in (
                p for p in r["base"] if p["class_id"] == 2 and p["score"] >= 0.75
            ):
                proposals = [
                    p
                    for p in r["obs"]
                    if p[2] == 7
                    and iou(p[4:], car["box"]) > 0.4
                    and containment(p[4:], car["box"]) >= 0.65
                ]
                if not proposals:
                    continue
                types = {
                    g["class_id"]
                    for g in truth["objects"]
                    if iou(g["box"], car["box"]) >= 0.5
                }
                if types not in ({2}, {7}):
                    continue
                p = max(proposals, key=lambda q: q[3])
                det = [car, dict(class_id=7, box=p[4:], score=p[3])]
                checks = evidence(image, det, detector, app)
                diagnostics.append(
                    dict(source=name, rgb=key, truth=next(iter(types)), **checks["1"])
                )
    dump(WORK / "challenge.json", diagnostics)


def resolved(r, t):
    return dict(
        rgb=r["rgb"],
        gt=r["gt"],
        base=filter_detections(r["parent"], r["checks"], t),
        new={},
    )


def select():
    native = {n: list(records(WORK / (n + ".jsonl.gz"))) for n in DEV}
    arch = list(records(WORK / "validation.jsonl.gz"))
    if len(arch) != 699 or any(len(v) != 81 for v in native.values()):
        raise ValueError("calibration denominator")
    members = {
        r["source"]: r["site"]
        for r in read(cycle.PARK / "cache/manifest.json")["validation"]
    }
    all_keys = [r["rgb"] for ds in [arch, *native.values()] for r in ds]
    if len(set(all_keys)) != len(all_keys) or set(all_keys) & {
        r["rgb"] for r in records(cycle.PARENT / "train.jsonl.gz")
    }:
        raise ValueError("calibration overlap")
    challenge_rows = read(WORK / "challenge.json")
    best = None
    options = []
    for t in (
        1.01,
        0.95,
        0.9,
        0.85,
        0.8,
        0.75,
        0.7,
        0.65,
        0.6,
        0.55,
        0.5,
        0.45,
        0.4,
        0.35,
        0.3,
        0.25,
        0.2,
    ):
        fixed = [resolved(r, t) for r in arch]
        summary = {
            n: cycle.archive([r for r in fixed if members[r["rgb"]] == n], 1.01)
            for n in sorted(set(members.values()))
        }
        cards = {
            n: score_run(DEV[n], [resolved(r, t) for r in rows], cycle.OFF)[0]
            for n, rows in native.items()
        }
        if t == 1.01:
            original = summary
            original_native = cards
        qualified = all(card["passed"] for card in cards.values()) and all(
            v["precision"] >= 0.85 and v["recall"] >= 0.80 for v in summary.values()
        )
        # Rank using how many spurious vehicle labels are removed for each real truck lost.
        lost = sum(original[n]["tp"] - s["tp"] for n, s in summary.items()) + sum(
            original_native[n]["card"]["micro"]["tp"] - s["card"]["micro"]["tp"]
            for n, s in cards.items()
        )
        removed = sum(original[n]["fp"] - s["fp"] for n, s in summary.items()) + sum(
            original_native[n]["card"]["micro"]["fp"] - s["card"]["micro"]["fp"]
            for n, s in cards.items()
        )
        car = [v for v in challenge_rows if v["truth"] == 2]
        truck = [v for v in challenge_rows if v["truth"] == 7]
        rejected_cars = sum(v["car_evidence"] >= t for v in car) / len(car)
        retained_trucks = sum(v["car_evidence"] < t for v in truck) / len(truck)
        rank = (
            min(rejected_cars, retained_trucks),
            rejected_cars + retained_trucks,
            removed - 2 * lost,
            -t,
        )
        options.append(
            dict(
                threshold=t,
                eligible=qualified,
                lost=lost,
                removed=removed,
                challenge_car_rejection=rejected_cars,
                challenge_truck_retention=retained_trucks,
                car_examples=len(car),
                truck_examples=len(truck),
            )
        )
        if qualified and (best is None or rank > best[0]):
            best = (
                rank,
                dict(
                    passed=True,
                    threshold=t,
                    thresholds=cycle.OFF,
                    classes=cards,
                    archive=summary,
                    model_sha256=read(WORK / "training.json")["sha256"],
                ),
            )
    dump(WORK / "diagnosis.json", options)
    if best is None:
        raise ValueError("no qualifying development policy")
    dump(WORK / "selection.json", dict(best[1], options=options))


def evaluate(run, name, selection, retained=None):
    model, app = model_pair()
    if selection["model_sha256"] != read(WORK / "training.json")["sha256"]:
        raise ValueError("nominated appearance model")
    old = iter(records(retained)) if retained else None
    rows = []
    for f in read(run / "images.json")["frames"]:
        raw = rgb_bytes(unpack(run / "dataset", f["rgb_raw"], 2560, 1536))
        if hashlib.sha256(raw).hexdigest() != f["rgb_sha256"]:
            raise ValueError("replay RGB")
        image = Image.frombytes("RGB", (2560, 1536), raw)
        start = time.perf_counter()
        if old is None:
            parent = parent_predictions(model, image)
        else:
            rec = next(old)
            if rec["rgb"] != f["rgb_sha256"]:
                raise ValueError("retrospective association")
            parent = rec["detections"]
        checks = evidence(image, parent, model, app)
        pred = filter_detections(parent, checks, selection["threshold"])
        rows.append(
            dict(
                rgb=f["rgb_sha256"],
                base=pred,
                new={},
                original_parent=parent,
                detections=pred,
                checks=checks,
                elapsed_s=time.perf_counter() - start,
            )
        )
    if old is not None and next(old, None) is not None:
        raise ValueError("parent denominator")
    write_stream(WORK / (name + "-verified.jsonl.gz"), rows)
    score, _ = score_run(run, rows, cycle.OFF)
    dump(WORK / (name + "-score.json"), score)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("train", "cache", "select", "challenge"))
    p.add_argument("name", nargs="?")
    a = p.parse_args()
    if a.action == "train":
        train()
    elif a.action == "challenge":
        challenge()
    elif a.action == "cache":
        cache(a.name)
    else:
        select()

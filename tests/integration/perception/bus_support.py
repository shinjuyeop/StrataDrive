"""Resolve frontal bus proposals with independent crop evidence and learned RGB appearance."""

import argparse
import hashlib
import time

import joblib
import numpy as np
from PIL import Image
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier

import small_car as tiles
import visible_car as visible
from small_car import (
    typed,
    cycle,
    prior,
    records,
    score_run,
    read,
    dump,
    data,
    write_stream,
    iou,
)
from bus_support_plan import WORK, EVIDENCE
from physical_ai.perception.camera_resolution_v1 import unpack
from fresh_quality_2k_review import rgb_bytes
from physical_ai.perception.yolox import preprocess, postprocess
from physical_ai.perception.contract import CameraFrame, FrameIdentity
from multiview_audit import audit

MASK = read(visible.EVIDENCE / "selection.json")["calibration"]


def features(rgb, box):
    b = np.array(box, dtype=float)
    return [
        np.log(max(1, b[2] - b[0]) / max(1, b[3] - b[1]))
    ] + prior.appearance_features(rgb, b)


def train():
    xs = []
    ys = []
    seen = set()
    for im, g, key, _ in data("train"):
        if key in seen or hashlib.sha256(im.tobytes()).hexdigest() != key:
            raise ValueError("training RGB identity")
        seen.add(key)
        rgb = np.asarray(im)
        for c in (2, 5, 7):
            objects = [v for v in g["objects"] if v["class_id"] == c]
            if len(objects) > 3:
                rng = np.random.default_rng(int(key[:12], 16))
                objects = [
                    objects[i] for i in rng.choice(len(objects), 3, replace=False)
                ]
            for obj in objects:
                b = np.asarray(obj["box"], float)
                for shifts in (
                    (0, 0, 0, 0),
                    (-0.05, 0.04, 0.03, 0.06),
                    (0.04, -0.06, -0.04, 0.02),
                ):
                    a = (b + np.tile(b[2:] - b[:2], 2) * shifts).clip(0, prior.LIMIT)
                    xs.append(features(rgb, a))
                    ys.append(c == 5)
                    flip = a.copy()
                    flip[[0, 2]] = 640 - a[[2, 0]]
                    xs.append(features(rgb[:, ::-1], flip))
                    ys.append(c == 5)
    forest = ExtraTreesClassifier(
        n_estimators=100,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=240,
        n_jobs=4,
    ).fit(xs, ys)
    boosted = HistGradientBoostingClassifier(
        max_iter=110, max_leaf_nodes=15, min_samples_leaf=10, random_state=240
    ).fit(xs, ys)
    forest.n_jobs = 1
    joblib.dump((forest, boosted), WORK / "appearance.joblib", compress=3)
    dump(
        WORK / "training.json",
        dict(
            images=len(seen),
            samples=len(ys),
            positive=sum(ys),
            sha256=hashlib.sha256(
                (WORK / "appearance.joblib").read_bytes()
            ).hexdigest(),
        ),
    )


def classifier():
    if (
        hashlib.sha256((WORK / "appearance.joblib").read_bytes()).hexdigest()
        != read(WORK / "training.json")["sha256"]
    ):
        raise ValueError("bus appearance classifier identity")
    return joblib.load(WORK / "appearance.joblib")


def proposals(im, model, yolo, models):
    resized = im.resize((640, 384), Image.Resampling.BILINEAR)
    tensor, ratio = preprocess(
        CameraFrame(FrameIdentity(1, 1, 1, 1), resized.tobytes())
    )
    raw = yolo.session.run(["output"], {"images": tensor})[0]
    out = []
    for obj in postprocess(raw, ratio):
        if obj.class_id != 5:
            continue
        box = list(obj.box)
        vec = typed.recognition(im, box, model, yolo)
        appearance = typed.probability(features(np.asarray(im), box), models)
        # Each head is ordered passenger car, truck, bus with four overlap features per class.
        bus = max(vec[9], vec[21], vec[33])
        out.append(
            dict(
                class_id=5,
                score=obj.score,
                box=box,
                appearance=appearance,
                crop_bus=bus,
            )
        )
    return out


def add(parent, candidates, policy):
    out = list(parent)
    for d in sorted(candidates, key=lambda x: -x["score"]):
        if (
            d["score"] < policy["full"]
            or d["appearance"] < policy["appearance"]
            or d["crop_bus"] < policy["crop"]
        ):
            continue
        if any(
            p["class_id"] == 5
            and (
                iou(p["box"], d["box"]) >= 0.40
                or prior.containment(d["box"], p["box"]) >= 0.8
            )
            for p in out
        ):
            continue
        out.append({k: d[k] for k in ("class_id", "score", "box")})
    return out


def cache(name):
    model, _, yolo = typed.sessions()
    cls = classifier()

    def rows():
        for r, (im, g, key, _) in zip(
            records(tiles.WORK / (name + ".jsonl.gz")),
            data(name, prior.DEV.get(name)),
            strict=True,
        ):
            if (
                r["rgb"] != key
                or r["gt"] != g["objects"]
                or hashlib.sha256(im.tobytes()).hexdigest() != key
            ):
                raise ValueError("development RGB association")
            full = tiles.add(r["parent"], r["candidates"], visible.FIX["cutoff"])
            base = visible.select_boxes(r["parent"], full, MASK)
            yield dict(
                rgb=key,
                gt=r["gt"],
                parent=base,
                candidates=proposals(im, model, yolo, cls),
            )

    write_stream(WORK / (name + ".jsonl.gz"), rows())


def select():
    groups = {n: list(records(WORK / (n + ".jsonl.gz"))) for n in prior.DEV}
    archive = list(records(WORK / "validation.jsonl.gz"))
    sites = {
        r["source"]: r["site"]
        for r in read(cycle.PARK / "cache/manifest.json")["validation"]
    }
    for n in set(sites.values()):
        groups[n] = [r for r in archive if sites[r["rgb"]] == n]
    seen = {r["rgb"] for r in records(cycle.PARENT / "train.jsonl.gz")}
    controls = {}
    frontal = []
    for n, rows in groups.items():
        cases = []
        for r in rows:
            if r["rgb"] in seen:
                raise ValueError("development split")
            seen.add(r["rgb"])
            for g in r["gt"]:
                if g["class_id"] != 5:
                    continue
                candidates = [
                    d for d in r["candidates"] if iou(d["box"], g["box"]) >= 0.5
                ]
                if candidates:
                    cases.append(candidates)
                    box = g["box"]
                    if box[2] - box[0] <= 1.6 * (box[3] - box[1]):
                        frontal.append(candidates)
        controls[n] = cases
    if len(archive) != 699 or any(len(groups[n]) != 81 for n in prior.DEV):
        raise ValueError("development denominator")
    best = None
    for full in (0.35, 0.45, 0.55):
        for app in (0.05, 0.15, 0.30, 0.45, 0.60, 0.75, 0.90):
            for crop in (0, 0.05, 0.20, 0.40, 0.60):
                policy = dict(full=full, appearance=app, crop=crop)
                eligible = {}
                ctrl = {}
                for n, rows in groups.items():
                    scored = [
                        dict(
                            rgb=r["rgb"],
                            gt=r["gt"],
                            new={},
                            base=add(r["parent"], r["candidates"], policy),
                        )
                        for r in rows
                    ]
                    eligible[n] = (
                        score_run(prior.DEV[n], scored, cycle.OFF)[0]
                        if n in prior.DEV
                        else cycle.archive(scored, 1.01)
                    )
                    ctrl[n] = dict(
                        recovered=sum(bool(add([], ds, policy)) for ds in controls[n]),
                        cases=len(controls[n]),
                    )
                ctrl["frontal"] = dict(
                    recovered=sum(bool(add([], ds, policy)) for ds in frontal),
                    cases=len(frontal),
                )
                native = {n: eligible[n] for n in prior.DEV}
                ar = {n: eligible[n] for n in groups if n not in native}
                if not all(v["passed"] for v in native.values()) or not all(
                    v["precision"] >= 0.85 and v["recall"] >= 0.8 for v in ar.values()
                ):
                    continue
                rates = [
                    v["recovered"] / v["cases"] for v in ctrl.values() if v["cases"]
                ]
                if not rates or min(rates) < 0.65:
                    continue
                cards = [s["card"]["micro"] for s in native.values()] + list(
                    ar.values()
                )
                rank = (
                    min(rates),
                    sum(rates),
                    sum(v["tp"] for v in cards),
                    -sum(v["fp"] for v in cards),
                    app,
                    crop,
                    full,
                )
                if best is None or rank > best[0]:
                    best = (
                        rank,
                        dict(
                            passed=True,
                            policy=policy,
                            thresholds=cycle.OFF,
                            classes=native,
                            archive=ar,
                            controls=ctrl,
                        ),
                    )
    if not best:
        raise ValueError("no qualified bus support")
    dump(EVIDENCE / "selection.json", best[1])


def evaluate(run, name, selection, source=None):
    from m10_bus_support_quality import binding

    if binding() != read(EVIDENCE / "development-lock.json"):
        raise ValueError("development nomination changed")
    if source is None and not (EVIDENCE / "nomination.json").exists():
        raise ValueError("missing prospective nomination")
    if source is None:
        tiles.evaluate(run, "bus-final-parent", visible.FIX)
        retained = tiles.WORK / "bus-final-parent-verified.jsonl.gz"
    else:
        retained = visible.WORK / (source + "-verified.jsonl.gz")
    model, _, yolo = typed.sessions()
    cls = classifier()
    rows = []
    for f, r in zip(
        read(run / "images.json")["frames"], records(retained), strict=True
    ):
        raw = rgb_bytes(unpack(run / "dataset", f["rgb_raw"], 2560, 1536))
        if (
            hashlib.sha256(raw).hexdigest() != f["rgb_sha256"]
            or r["rgb"] != f["rgb_sha256"]
        ):
            raise ValueError("inference RGB")
        im = Image.frombytes("RGB", (2560, 1536), raw)
        start = time.perf_counter()
        base = (
            visible.select_boxes(r["original_parent"], r["detections"], MASK)
            if source is None
            else r["detections"]
        )
        candidates = proposals(im, model, yolo, cls)
        det = add(base, candidates, selection["policy"])
        rows.append(
            dict(
                rgb=r["rgb"],
                original_parent=base,
                base=det,
                new={},
                candidates=candidates,
                detections=det,
                elapsed_s=(r["elapsed_s"] if source is None else 0)
                + time.perf_counter()
                - start,
            )
        )
    card, _ = score_run(run, rows, cycle.OFF)
    write_stream(WORK / (name + "-verified.jsonl.gz"), rows)
    dump(WORK / (name + "-score.json"), card)


def audit_score(run, name):
    rows = list(records(WORK / (name + "-verified.jsonl.gz")))
    choice = read(EVIDENCE / "selection.json")["policy"]
    for r in rows:
        if add(r["original_parent"], r["candidates"], choice) != r["detections"]:
            raise ValueError("bus support decision")
    if name == "previous101":
        old = visible.EVIDENCE
        try:
            visible.EVIDENCE = EVIDENCE
            report = visible.audit_legacy(
                run, rows, read(WORK / (name + "-score.json")), name
            )
        finally:
            visible.EVIDENCE = old
    else:
        report = audit(run, WORK, EVIDENCE, name)
    if name != "holdout":
        src = "holdout" if name == "previous60" else name
        old = read(visible.EVIDENCE / (src + ".json"))
        if (
            report["capture_sha256"] != old["capture_sha256"]
            or report["baseline"]["micro"] != old["baseline"]["micro"]
        ):
            raise ValueError("paired parent capture")
    dump(
        EVIDENCE / (name + "-additions.json"),
        [
            dict(rgb=r["rgb"], added=r["detections"][len(r["original_parent"]) :])
            for r in rows
        ],
    )
    return report


if __name__ == "__main__":
    from pathlib import Path

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("train", "cache", "select", "history", "audit"))
    p.add_argument("name", nargs="?")
    p.add_argument("run", nargs="?", type=Path)
    a = p.parse_args()
    if a.action == "train":
        train()
    elif a.action == "cache":
        cache(a.name)
    elif a.action == "select":
        select()
    else:
        if a.action == "history":
            evaluate(
                a.run,
                a.name,
                read(EVIDENCE / "selection.json"),
                "holdout" if a.name == "previous60" else a.name,
            )
        audit_score(a.run, a.name)

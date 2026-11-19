"""Verify ambiguous two-wheelers using rider evidence and an object-centered RGB view."""

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image

from bus_recall import forward
from bus_recall_fit import iou, matched
from fresh_quality_2k_review import BASE as DEV90, read, rgb_bytes
from multiview_detector import Detector, combine, records, score_run, TARGET
from multiview_observations import data
from person_pair_candidate import dump
from person_proposal_diagnosis import PARK
from physical_ai.perception.camera_resolution_v1 import unpack
from cycle_transfer_plan import WORK, EVIDENCE, ROOT

PARENT = ROOT / "build/m10-multiview-v1"
FIX = read(ROOT / "docs/test-plan/evidence/m10_multiview_v1/selection.json")
OFF = {str(c): 1.01 for c in TARGET}
DEV = {
    "dev90": DEV90 / "runs/evaluation-development-01",
    "dev608": PARENT / "native/runs/evaluation-development-01",
    "dev07": WORK / "native/runs/evaluation-development-01",
}


def fused_metrics(base, new):
    return combine(base, new, FIX["thresholds"])


def resolve_vehicle_conflicts(detections):
    """Remove a motorcycle duplicate of a much stronger, nearly identical car box."""
    cars = [d for d in detections if d["class_id"] == 2 and d["score"] >= 0.9]
    return [
        d
        for d in detections
        if d["class_id"] != 3
        or not any(
            car["score"] - d["score"] >= 0.20 and iou(car["box"], d["box"]) >= 0.80
            for car in cars
        )
    ]


def alignment(b, r):
    # A rider overlaps the upper part of the two-wheeler. Require their horizontal centers to agree.
    mid = (r[0] + r[2]) / 2
    return (
        b[0] <= mid <= b[2]
        and r[1] < (b[1] + b[3]) / 2
        and b[1] <= r[3] <= b[3] + 0.35 * (b[3] - b[1])
    )


def regions(verified, detections):
    seeds = [(r["score"], r["box"]) for r in verified if r["score"] >= 0.04]
    seeds.extend((d["score"], d["box"]) for d in detections if d["class_id"] in (0, 3))
    bikes = [d["box"] for d in detections if d["class_id"] == 1]
    chosen = []
    for _, b in sorted(seeds, key=lambda item: -item[0]):
        if any(iou(b, x) >= 0.45 for x in bikes):
            continue
        cx = (b[0] + b[2]) / 2
        cy = (b[1] + b[3]) / 2
        width = min(640, max(80, 6 * (b[2] - b[0]), 7 * (b[3] - b[1])))
        height = width * 384 / 640
        x = min(640 - width, max(0, cx - width / 2))
        y = min(384 - height, max(0, cy - height / 2))
        bounds = [x, y, x + width, y + height]
        if all(iou(bounds, q) < 0.55 for q in chosen):
            chosen.append(bounds)
    return chosen


def local_proposals(image, regions, session, spec):
    result = []
    for bounds in regions:
        rect = np.rint(
            np.asarray(bounds) * np.array([image.width / 640, image.height / 384] * 2)
        ).astype(int)
        out = forward(image.crop(tuple(rect)), session, spec)
        scale = np.array(
            [(rect[2] - rect[0]) / image.width, (rect[3] - rect[1]) / image.height] * 2
        )
        offset = np.array(
            [rect[0] * 640 / image.width, rect[1] * 384 / image.height] * 2
        )
        for prefix in ("", "original_"):
            labels = out[prefix + "labels"].ravel()
            scores = out[prefix + "scores"].ravel()
            boxes = out[prefix + "boxes"].reshape(-1, 4)
            for i in np.flatnonzero(np.isin(labels, (0, 1, 3)) & (scores >= 0.06)):
                b = boxes[i].clip([0, 0, 0, 0], [640, 384, 640, 384])
                if (
                    b[2] - b[0] < 2
                    or b[3] - b[1] < 2
                    or min(b[0], b[1]) < 2
                    or b[2] > 638
                    or b[3] > 382
                ):
                    continue
                result.append(
                    dict(
                        class_id=int(labels[i]),
                        score=float(scores[i]),
                        box=(b * scale + offset).tolist(),
                    )
                )
    return result


def suggestions(verified, parent, observations, local):
    bikes = [p for p in parent if p["class_id"] == 1]
    people = [
        p["box"] for p in [*parent, *local] if p["class_id"] == 0 and p["score"] >= 0.35
    ]
    glob = [p for p in observations if p[2] == 1]
    zoom = [d for d in local if d["class_id"] == 1]
    seeds = sorted([*verified, *zoom], key=lambda p: -p["score"])
    result = []
    for p in seeds:
        b = p["box"]
        if any(iou(b, d["box"]) >= 0.4 for d in bikes) or any(
            iou(b, d["box"]) > 0.87 for d in result
        ):
            continue
        score = max(
            (d["score"] for d in verified if iou(b, d["box"]) >= 0.55), default=0
        )
        zoom_score = max(
            (d["score"] for d in zoom if iou(b, d["box"]) >= 0.5), default=0
        )
        votes = [d for d in glob if iou(b, d[4:]) >= 0.45]
        global_score = max((d[3] for d in votes), default=0)
        views = len({d[0] for d in votes if d[3] >= 0.2})
        rider = any(alignment(b, r) for r in people)
        # Distinct signals must corroborate the type; a rider alone is shared with motorcycles.
        confirm = max(
            zoom_score,
            min(global_score, score),
            min(global_score, 0.8) if views >= 3 else 0,
        )
        if not rider and zoom_score < 0.45:
            continue
        strength = max((score * confirm) ** 0.5, (zoom_score * global_score) ** 0.5)
        if strength:
            result.append(dict(class_id=1, box=b, score=round(strength, 6)))
    return result


def expand(bundle, image, base, new, obs):
    parent = fused_metrics(base, new)
    verified = new.get("1", [])
    zoom = local_proposals(
        image, regions(verified, parent), bundle.session, bundle.spec
    )
    return parent, suggestions(verified, parent, obs, zoom)


def rows_from_run(run):
    for f, g in zip(
        read(run / "images.json")["frames"],
        read(run / "evaluation-only-gt.json")["frames"],
        strict=True,
    ):
        if f["scene"] != g["scene"]:
            raise ValueError("native scene association")
        rgb = rgb_bytes(unpack(run / "dataset", f["rgb_raw"], 2560, 1536))
        if hashlib.sha256(rgb).hexdigest() != f["rgb_sha256"]:
            raise ValueError("native RGB")
        yield Image.frombytes("RGB", (2560, 1536), rgb), g, f["rgb_sha256"]


def predict_raw(model, im):
    from multiview_observations import observe
    from multiview_detector import predict_proposals

    base, obs = observe(im, model.session, model.spec)
    return base, predict_proposals(model.bundle, im, dict(obs=obs, base=base)), obs


def make_cache(name):
    model = Detector(PARENT, FIX)
    path = WORK / (name + ".jsonl.gz")
    if path.exists():
        raise FileExistsError(path)
    temp = path.with_suffix(".partial")
    run = DEV.get(name)
    if name == "dev07":
        source = (
            (im, g, key, *predict_raw(model, im)) for im, g, key in rows_from_run(run)
        )
    else:

        def cached():
            for obs, vr, (im, g, key, _) in zip(
                records(PARENT / (name + ".jsonl.gz")),
                records(PARENT / (name + "-verified.jsonl.gz")),
                data(name, run),
                strict=True,
            ):
                if (
                    obs["rgb"] != key
                    or vr["rgb"] != key
                    or hashlib.sha256(im.tobytes()).hexdigest() != key
                ):
                    raise ValueError("cached image association")
                yield im, g, key, obs["base"], vr["new"], obs["obs"]

        source = cached()
    with gzip.open(temp, "wt") as out:
        for im, g, key, base, new, obs in source:
            fixed, extra = expand(model, im, base, new, obs)
            out.write(
                json.dumps(
                    dict(rgb=key, gt=g["objects"], base=fixed, new={"1": extra}),
                    separators=(",", ":"),
                )
                + "\n"
            )
    temp.rename(path)


def policy(t):
    return dict(OFF, **{"1": t})


def archive(ds, t):
    s = Counter()
    for r in ds:
        det = combine(r["base"], r["new"], policy(t))
        for c in (0, 1, 2, 3, 5, 7):
            pred = [p for p in det if p["class_id"] == c]
            gt = [p["box"] for p in r["gt"] if p["class_id"] == c]
            n = len(matched(pred, gt))
            s.update(tp=n, fp=len(pred) - n, fn=len(gt) - n)
            if c == 1:
                s.update(bike_tp=n, bike_fp=len(pred) - n, bike_fn=len(gt) - n)
    return dict(
        s, precision=s["tp"] / (s["tp"] + s["fp"]), recall=s["tp"] / (s["tp"] + s["fn"])
    )


def select():
    native = {k: list(records(WORK / (k + ".jsonl.gz"))) for k in DEV}
    ds = list(records(WORK / "validation.jsonl.gz"))
    if len(ds) != 699 or any(len(r) != 81 for r in native.values()):
        raise ValueError("development denominator")
    archive_sites = {
        r["source"]: r["site"] for r in read(PARK / "cache/manifest.json")["validation"]
    }
    groups = {
        k: [r for r in ds if archive_sites[r["rgb"]] == k]
        for k in set(archive_sites.values())
    }
    seen = {r["rgb"] for r in records(PARENT / "train.jsonl.gz")}
    for group in (*native.values(), ds):
        for r in group:
            if r["rgb"] in seen:
                raise ValueError("split overlap")
            seen.add(r["rgb"])
    for group in (*native.values(), ds):
        for r in group:
            r["base"] = resolve_vehicle_conflicts(r["base"])
    best = None
    options = []
    for t in [1.01, *np.linspace(0.9, 0.15, 16).round(2)]:
        t = float(t)
        ar = {n: archive(rows, t) for n, rows in groups.items()}
        cards = {n: score_run(DEV[n], rows, policy(t))[0] for n, rows in native.items()}
        if t == 1.01:
            base_ar = ar
        passed = all(c["passed"] for c in cards.values()) and all(
            v["precision"] >= 0.85
            and v["recall"] >= 0.8
            and v["bike_tp"] >= base_ar[n]["bike_tp"]
            and v["bike_fp"] - base_ar[n]["bike_fp"]
            <= max(2, 3 * (v["bike_tp"] - base_ar[n]["bike_tp"]))
            for n, v in ar.items()
        )
        bikes = [c["card"]["per_class"]["1"] for c in cards.values()]
        rank = (
            min(c["recall"] for c in bikes),
            sum(c["tp"] for c in bikes),
            sum(v["bike_tp"] for v in ar.values()),
            -sum(v["bike_fp"] for v in ar.values()) - sum(c["fp"] for c in bikes),
            t,
        )
        options.append(dict(threshold=t, eligible=passed, rank=rank))
        if passed and (best is None or rank > best[0]):
            best = (
                rank,
                dict(
                    passed=True,
                    threshold=t,
                    thresholds=policy(t),
                    archive=ar,
                    native=cards,
                    model_sha256=FIX["model_sha256"],
                ),
            )
    if best is None:
        raise ValueError("no qualifying cycle policy")
    dump(WORK / "selection.json", dict(best[1], development_options=options))


def evaluate(run, name, selected):
    if selected["model_sha256"] != FIX["model_sha256"]:
        raise ValueError("model changed")
    model = Detector(PARENT, FIX)
    rows = []
    for f in read(run / "images.json")["frames"]:
        rgb = rgb_bytes(unpack(run / "dataset", f["rgb_raw"], 2560, 1536))
        if hashlib.sha256(rgb).hexdigest() != f["rgb_sha256"]:
            raise ValueError("evaluation RGB")
        image = Image.frombytes("RGB", (2560, 1536), rgb)
        start = time.perf_counter()
        fixed, sug = expand(model, image, *predict_raw(model, image))
        resolved = resolve_vehicle_conflicts(fixed)
        det = combine(resolved, {"1": sug}, policy(selected["threshold"]))
        rows.append(
            dict(
                rgb=f["rgb_sha256"],
                base=resolved,
                original_parent=fixed,
                new={"1": sug},
                detections=det,
                elapsed_s=time.perf_counter() - start,
            )
        )
    with gzip.open(WORK / (name + "-verified.jsonl.gz"), "wt") as out:
        for r in rows:
            out.write(json.dumps(r, separators=(",", ":")) + "\n")
    card, trace = score_run(run, rows, policy(selected["threshold"]))
    if any(
        r["detections"] != p["detections"] for r, p in zip(rows, trace, strict=True)
    ):
        raise ValueError("cycle replay")
    dump(WORK / (name + "-score.json"), card)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("cache", "select", "replay"))
    p.add_argument("name", nargs="?")
    p.add_argument("--run", type=Path)
    a = p.parse_args()
    if a.action == "cache":
        make_cache(a.name)
    elif a.action == "select":
        select()
    else:
        if not (EVIDENCE / "nomination.json").is_file():
            raise ValueError("freeze before replay")
        evaluate(a.run, a.name, read(EVIDENCE / "selection.json"))

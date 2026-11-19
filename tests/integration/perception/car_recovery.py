"""Recover unmatched passenger-car proposals with the fixed YOLOX and crop type verifier."""

import argparse
import hashlib
import time

from PIL import Image

import vehicle_class as typed
from vehicle_class import (
    prior,
    cycle,
    records,
    score_run,
    data,
    write_stream,
    dump,
    iou,
)
from car_recovery_plan import ROOT, WORK, read
from physical_ai.perception.contract import CameraFrame, FrameIdentity
from physical_ai.perception.yolox import postprocess, preprocess
from physical_ai.perception.camera_resolution_v1 import unpack
from fresh_quality_2k_review import rgb_bytes

FIX = read(ROOT / "docs/test-plan/evidence/m10_vehicle_class_v1/selection.json")


def add(parent, candidates, threshold):
    predictions = list(parent)
    for d in sorted(candidates, key=lambda c: -c["score"]):
        if d["support"] < threshold or any(
            o["class_id"] == 2 and iou(d["box"], o["box"]) >= 0.5 for o in predictions
        ):
            continue
        predictions.append({k: d[k] for k in ("class_id", "score", "box")})
    return predictions


def proposals(im, parent, model, yolo, classes):
    resized = im.resize((640, 384), Image.Resampling.BILINEAR)
    tensor, ratio = preprocess(
        CameraFrame(FrameIdentity(1, 1, 1, 1), resized.tobytes())
    )
    raw = yolo.session.run(["output"], {"images": tensor})[0]
    ds = postprocess(raw, ratio)
    out = []
    for obj in ds:
        if obj.class_id != 2 or any(
            d["class_id"] == 2 and iou(obj.box, d["box"]) >= 0.5 for d in parent
        ):
            continue
        vec = typed.recognition(im, obj.box, model, yolo)
        class_prob = typed.probability(vec, classes)
        # A full-frame box and an object-centered crop are independent views of the same RGB.
        # Use both decoder heads and the second detector without counting two car boxes twice.
        independent = max(vec[1], vec[13], vec[25])
        support = max((class_prob * obj.score) ** 0.5, (independent * obj.score) ** 0.5)
        out.append(
            dict(
                class_id=2,
                box=list(obj.box),
                score=obj.score,
                support=support,
                crop_type=class_prob,
                crop_car=independent,
            )
        )
    return out


def cache(name):
    model, _, yolo = typed.sessions()
    classes = typed.classifier()

    def rows():
        for r, (im, g, key, _) in zip(
            records(typed.WORK / (name + ".jsonl.gz")),
            data(name, prior.DEV.get(name)),
            strict=True,
        ):
            if (
                r["rgb"] != key
                or r["gt"] != g["objects"]
                or hashlib.sha256(im.tobytes()).hexdigest() != key
            ):
                raise ValueError("calibration RGB")
            parent = prior.filter_detections(r["parent"], r["checks"], FIX["threshold"])
            yield dict(
                rgb=key,
                gt=g["objects"],
                parent=parent,
                candidates=proposals(im, parent, model, yolo, classes),
            )

    write_stream(WORK / (name + ".jsonl.gz"), rows())


def selected_rows(ds, t):
    return [
        dict(
            rgb=r["rgb"], gt=r["gt"], base=add(r["parent"], r["candidates"], t), new={}
        )
        for r in ds
    ]


def select():
    groups = {n: list(records(WORK / (n + ".jsonl.gz"))) for n in prior.DEV}
    archive = list(records(WORK / "validation.jsonl.gz"))
    ids = {
        r["source"]: r["site"]
        for r in read(cycle.PARK / "cache/manifest.json")["validation"]
    }
    seen = {r["rgb"] for r in records(cycle.PARENT / "train.jsonl.gz")}
    for ds in [archive, *groups.values()]:
        for r in ds:
            if r["rgb"] in seen:
                raise ValueError("split overlap")
            seen.add(r["rgb"])
    if len(archive) != 699 or any(len(x) != 81 for x in groups.values()):
        raise ValueError("calibration count")
    options = []
    best = None
    for t in (
        1.01,
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
        0.15,
        0.1,
        0.0,
    ):
        rows = selected_rows(archive, t)
        ar = {
            n: cycle.archive([r for r in rows if ids[r["rgb"]] == n], 1.01)
            for n in sorted(set(ids.values()))
        }
        cards = {
            n: score_run(prior.DEV[n], selected_rows(ds, t), cycle.OFF)[0]
            for n, ds in groups.items()
        }
        if t == 1.01:
            parent_ar = ar
            parent_native = cards
        eligible = all(v["passed"] for v in cards.values()) and all(
            v["precision"] >= 0.85 and v["recall"] >= 0.80 for v in ar.values()
        )
        tp = sum(v["tp"] - parent_ar[n]["tp"] for n, v in ar.items()) + sum(
            v["card"]["micro"]["tp"] - parent_native[n]["card"]["micro"]["tp"]
            for n, v in cards.items()
        )
        fp = sum(v["fp"] - parent_ar[n]["fp"] for n, v in ar.items()) + sum(
            v["card"]["micro"]["fp"] - parent_native[n]["card"]["micro"]["fp"]
            for n, v in cards.items()
        )
        # Among qualifying policies recover the most missed cars, then minimize false recoveries.
        rank = (tp, -fp, t)
        options.append(
            dict(threshold=t, eligible=eligible, additional_tp=tp, additional_fp=fp)
        )
        if eligible and (best is None or rank > best[0]):
            best = (
                rank,
                dict(
                    passed=True,
                    threshold=t,
                    thresholds=cycle.OFF,
                    archive=ar,
                    classes=cards,
                ),
            )
    if best is None:
        raise ValueError("car recovery qualification")
    dump(WORK / "selection.json", dict(best[1], options=options))


def evaluate(run, name, selection, retained=None):
    model, app, yolo = typed.sessions()
    classes = typed.classifier()
    old = iter(records(retained)) if retained else None
    rows = []
    for f in read(run / "images.json")["frames"]:
        raw = rgb_bytes(unpack(run / "dataset", f["rgb_raw"], 2560, 1536))
        if hashlib.sha256(raw).hexdigest() != f["rgb_sha256"]:
            raise ValueError("evaluation RGB")
        im = Image.frombytes("RGB", (2560, 1536), raw)
        start = time.perf_counter()
        if old is None:
            ds = prior.parent_predictions(model, im)
            ds = prior.filter_detections(
                ds, prior.evidence(im, ds, model, app), typed.FIX["threshold"]
            )
            parent = prior.filter_detections(
                ds, typed.competition(im, ds, model, yolo, classes), FIX["threshold"]
            )
        else:
            r = next(old)
            if r["rgb"] != f["rgb_sha256"]:
                raise ValueError("parent binding")
            parent = r["detections"]
        suggestions = proposals(im, parent, model, yolo, classes)
        det = add(parent, suggestions, selection["threshold"])
        rows.append(
            dict(
                rgb=f["rgb_sha256"],
                base=det,
                new={},
                original_parent=parent,
                candidates=suggestions,
                detections=det,
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
    p.add_argument("action", choices=("cache", "select"))
    p.add_argument("name", nargs="?")
    a = p.parse_args()
    if a.action == "cache":
        cache(a.name)
    else:
        select()

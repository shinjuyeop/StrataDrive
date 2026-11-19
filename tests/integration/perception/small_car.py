"""Recover small passenger cars supported by overlapping, independently resized RGB crops."""

import argparse
import hashlib
import time

import numpy as np
from PIL import Image

import car_support as support
from car_support import (
    cycle,
    prior,
    typed,
    recovery,
    records,
    score_run,
    data,
    write_stream,
    dump,
    iou,
    read,
)
from small_car_plan import ROOT, WORK
from fresh_quality_2k_review import rgb_bytes
from physical_ai.perception.camera_resolution_v1 import unpack

PARENT = read(ROOT / "docs/test-plan/evidence/m10_car_support_v1/selection.json")
VIEWS = tuple(
    (float(x), y, w, h)
    for w, h, y, count in ((0.46, 0.56, 0.21, 4), (0.26, 0.37, 0.28, 6))
    for x in np.linspace(0, 1 - w, count)
)


def proposals(im, model):
    observations = []
    for index, (x, y, w, h) in enumerate(VIEWS):
        rect = tuple(
            round(v)
            for v in (
                x * im.width,
                y * im.height,
                (x + w) * im.width,
                (y + h) * im.height,
            )
        )
        raw = prior.forward(im.crop(rect), model.session, model.spec)
        for head in ("original_", ""):
            labels = raw[head + "labels"].ravel()
            scores = raw[head + "scores"].ravel()
            boxes = raw[head + "boxes"].reshape(-1, 4)
            for j in np.flatnonzero((labels == 2) & (scores >= 0.25)):
                b = boxes[j]
                if min(b[0], b[1], 640 - b[2], 384 - b[3]) < 2:
                    continue
                scale = np.array(
                    [(rect[2] - rect[0]) / im.width, (rect[3] - rect[1]) / im.height]
                    * 2
                )
                box = b * scale + np.array(
                    [rect[0] * 640 / im.width, rect[1] * 384 / im.height] * 2
                )
                width, height = box[2:] - box[:2]
                if (
                    min(width, height) < 4
                    or max(width, height) > 40
                    or width * height < 42
                ):
                    continue
                observations.append((index, head, float(scores[j]), box.tolist()))
    candidates = []
    for index, head, score, box in observations:
        other = max(
            (s for k, _, s, b in observations if k != index and iou(box, b) >= 0.55),
            default=0.0,
        )
        if other:
            candidates.append(dict(class_id=2, box=box, score=min(score, other)))
    return sorted(candidates, key=lambda v: -v["score"])


def duplicate(box, previous):
    if previous["class_id"] not in (2, 5, 7, 3):
        return False
    # Suppress a fragment well inside a vehicle while retaining a partly hidden car.
    return (
        iou(box, previous["box"]) >= 0.32
        or prior.containment(box, previous["box"]) >= 0.85
    )


def short_side(box):
    return min(box[2] - box[0], box[3] - box[1])


def add(parent, candidates, cutoff):
    out = list(parent)
    boxes = [item["box"] for item in candidates]
    for candidate in candidates:
        if candidate["score"] < cutoff:
            break
        box = candidate["box"]
        # Tall or nearly square small vehicles are ambiguous with a truck cab.
        # Keep the parent detector's classification for these shapes.
        if box[2] - box[0] < 1.25 * (box[3] - box[1]):
            continue
        if short_side(box) < 5 or any(duplicate(box, obj) for obj in out):
            continue
        # Require a one-pixel margin above the four-pixel annotation minimum
        # in both the selected box and the typical overlapping crop observation.
        sizes = [short_side(other) for other in boxes if iou(box, other) >= 0.5]
        if np.median(sizes) >= 5:
            out.append(candidate)
    return out


def cache(name):
    model, _ = prior.model_pair()

    def rows():
        for r, (im, g, key, _) in zip(
            records(support.WORK / (name + ".jsonl.gz")),
            data(name, prior.DEV.get(name)),
            strict=True,
        ):
            if (
                r["gt"] != g["objects"]
                or r["rgb"] != key
                or hashlib.sha256(im.tobytes()).hexdigest() != key
            ):
                raise ValueError("development association")
            yield dict(
                rgb=key,
                gt=r["gt"],
                parent=support.add(r["parent"], r["candidates"], PARENT["policy"]),
                candidates=proposals(im, model),
            )

    write_stream(WORK / (name + ".jsonl.gz"), rows())


def selected(rows, cutoff):
    return [
        dict(
            rgb=r["rgb"],
            gt=r["gt"],
            base=add(r["parent"], r["candidates"], cutoff),
            new={},
        )
        for r in rows
    ]


def select():
    groups = {n: list(records(WORK / (n + ".jsonl.gz"))) for n in prior.DEV}
    archive = list(records(WORK / "validation.jsonl.gz"))
    sites = {
        r["source"]: r["site"]
        for r in read(cycle.PARK / "cache/manifest.json")["validation"]
    }
    for name in sorted(set(sites.values())):
        groups[name] = [r for r in archive if sites[r["rgb"]] == name]
    seen = {r["rgb"] for r in records(cycle.PARENT / "train.jsonl.gz")}
    if len(archive) != 699 or any(len(groups[n]) != 81 for n in prior.DEV):
        raise ValueError("development denominator")
    controls = {}
    for n, rows in groups.items():
        cases = []
        for r in rows:
            if r["rgb"] in seen:
                raise ValueError("split overlap")
            seen.add(r["rgb"])
            for g in r["gt"]:
                b = g["box"]
                if g["class_id"] != 2 or max(b[2] - b[0], b[3] - b[1]) > 40:
                    continue
                parent = r["parent"]
                ov, j = max(
                    (
                        (iou(b, p["box"]), j)
                        for j, p in enumerate(parent)
                        if p["class_id"] == 2
                    ),
                    default=(0, -1),
                )
                if ov >= 0.5:
                    sub = parent[:j] + parent[j + 1 :]
                    recovered = add(sub, r["candidates"], 0.25)[len(sub) :]
                    cases.append(
                        max(
                            (p["score"] for p in recovered if iou(b, p["box"]) >= 0.5),
                            default=0,
                        )
                    )
        controls[n] = cases
    best = None
    history = []
    for t in (
        1.01,
        0.95,
        0.90,
        0.85,
        0.80,
        0.75,
        0.70,
        0.65,
        0.60,
        0.55,
        0.50,
        0.45,
        0.40,
    ):
        cards = {
            n: score_run(prior.DEV[n], selected(groups[n], t), cycle.OFF)[0]
            for n in prior.DEV
        }
        ar = {
            n: cycle.archive(selected(rows, t), 1.01)
            for n, rows in groups.items()
            if n not in prior.DEV
        }
        tp = sum(c["card"]["micro"]["tp"] for c in cards.values()) + sum(
            c["tp"] for c in ar.values()
        )
        fp = sum(c["card"]["micro"]["fp"] for c in cards.values()) + sum(
            c["fp"] for c in ar.values()
        )
        if t > 1:
            oldtp, oldfp = tp, fp
        cp = {
            n: dict(recovered=sum(x >= t for x in xs), cases=len(xs))
            for n, xs in controls.items()
        }
        valid = all(c["passed"] for c in cards.values()) and all(
            c["precision"] >= 0.85 and c["recall"] >= 0.8 for c in ar.values()
        )
        # Require at least three additional intact development detections or substantial
        # small-car omission recovery, with at most one extra FP per recovered TP plus 3.
        recovered = sum(x["recovered"] for x in cp.values())
        eligible = (
            valid
            and (tp - oldtp >= 3 or recovered >= 20)
            and fp - oldfp <= max(0, tp - oldtp) + 3
        )
        history.append(
            dict(cutoff=t, tp=tp, fp=fp, recovered=recovered, eligible=eligible)
        )
        rank = (tp - oldtp - (fp - oldfp) * 0.5, recovered, t)
        if eligible and (best is None or rank > best[0]):
            best = (
                rank,
                dict(
                    passed=True,
                    cutoff=t,
                    thresholds=cycle.OFF,
                    classes=cards,
                    archive=ar,
                    controls=cp,
                ),
            )
    dump(WORK / "options.json", history)
    if not best:
        raise ValueError("no qualified small-car detector")
    dump(WORK / "selection.json", dict(best[1], options=history))


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
            ds = prior.filter_detections(
                ds,
                typed.competition(im, ds, model, yolo, classes),
                recovery.FIX["threshold"],
            )
            props = recovery.proposals(im, ds, model, yolo, classes)
            parent = support.add(
                recovery.add(ds, props, support.EARLIER["threshold"]),
                props,
                PARENT["policy"],
            )
        else:
            row = next(old)
            if row["rgb"] != f["rgb_sha256"]:
                raise ValueError("parent RGB")
            parent = row["detections"]
        candidates = proposals(im, model)
        det = add(parent, candidates, selection["cutoff"])
        rows.append(
            dict(
                rgb=f["rgb_sha256"],
                original_parent=parent,
                base=det,
                new={},
                candidates=candidates,
                detections=det,
                elapsed_s=time.perf_counter() - start,
            )
        )
    if old is not None and next(old, None) is not None:
        raise ValueError("parent denominator")
    write_stream(WORK / (name + "-verified.jsonl.gz"), rows)
    dump(WORK / (name + "-score.json"), score_run(run, rows, cycle.OFF)[0])


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("cache", "select"))
    p.add_argument("name", nargs="?")
    a = p.parse_args()
    if a.action == "cache":
        cache(a.name)
    else:
        select()

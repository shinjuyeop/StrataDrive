"""Verify full-frame car proposals after accounting for already explained objects."""

import argparse
import hashlib
import time
from PIL import Image

import car_recovery as recovery
from car_recovery import (
    typed,
    prior,
    cycle,
    records,
    data,
    write_stream,
    score_run,
    dump,
    iou,
    read,
)
from car_support_plan import WORK, ROOT
from physical_ai.perception.camera_resolution_v1 import unpack
from fresh_quality_2k_review import rgb_bytes

EARLIER = read(ROOT / "docs/test-plan/evidence/m10_car_recovery_v1/selection.json")


def explained(candidate, parents):
    box = candidate["box"]
    for p in parents:
        ov = iou(box, p["box"])
        if p["class_id"] == 2:
            cover = prior.containment(box, p["box"])
            if ov >= 0.4 or cover >= 0.7:
                return True
        if (
            p["class_id"] in (1, 3, 5, 7)
            and ov >= 0.55
            and p["score"] >= 0.65
            and p["score"] > candidate["score"]
            and candidate["crop_car"] < 0.85
        ):
            return True
    return False


def accept(c, parents, policy):
    return (
        c["score"] >= policy["full"]
        and c["crop_car"] >= policy["crop"]
        and not explained(c, parents)
    )


def add(parent, proposals, policy):
    result = list(parent)
    for c in sorted(proposals, key=lambda v: -v["score"]):
        if accept(c, result, policy):
            result.append({k: c[k] for k in ("class_id", "score", "box")})
    return result


def cache(name):
    model, _, yolo = typed.sessions()
    classes = typed.classifier()

    def rows():
        for r, (im, g, key, _) in zip(
            records(recovery.WORK / (name + ".jsonl.gz")),
            data(name, prior.DEV.get(name)),
            strict=True,
        ):
            if (
                r["rgb"] != key
                or r["gt"] != g["objects"]
                or hashlib.sha256(im.tobytes()).hexdigest() != key
            ):
                raise ValueError("development RGB")
            parent = recovery.add(r["parent"], r["candidates"], EARLIER["threshold"])
            all_cars = recovery.proposals(im, [], model, yolo, classes)
            yield dict(rgb=key, gt=r["gt"], parent=parent, candidates=all_cars)

    write_stream(WORK / (name + ".jsonl.gz"), rows())


def controls(rows):
    # One object at a time: can a real full-frame YOLOX proposal recover the
    # correctly matched D-FINE car if its box disappears? Never used in the reported native score.
    pairs = []
    for r in rows:
        for g in r["gt"]:
            if g["class_id"] != 2:
                continue
            hits = [
                (iou(p["box"], g["box"]), i)
                for i, p in enumerate(r["parent"])
                if p["class_id"] == 2
            ]
            choices = [c for c in r["candidates"] if iou(c["box"], g["box"]) >= 0.5]
            best, index = max(hits, default=(0, -1))
            if best >= 0.5 and choices:
                parent = r["parent"][:index] + r["parent"][index + 1 :]
                pairs.append([c for c in choices if not explained(c, parent)])
    return pairs


def selected(rows, policy):
    return [
        dict(
            rgb=r["rgb"],
            gt=r["gt"],
            base=add(r["parent"], r["candidates"], policy),
            new={},
        )
        for r in rows
    ]


def select():
    ds = {
        n: list(records(WORK / (n + ".jsonl.gz"))) for n in [*prior.DEV, "validation"]
    }
    archive = ds.pop("validation")
    sites = {
        r["source"]: r["site"]
        for r in read(cycle.PARK / "cache/manifest.json")["validation"]
    }
    for n in sorted(set(sites.values())):
        ds[n] = [r for r in archive if sites[r["rgb"]] == n]
    if len(archive) != 699 or any(len(ds[n]) != 81 for n in prior.DEV):
        raise ValueError("development denominator")
    seen = {r["rgb"] for r in records(cycle.PARENT / "train.jsonl.gz")}
    for group in ds.values():
        for r in group:
            if r["rgb"] in seen:
                raise ValueError("split overlap")
            seen.add(r["rgb"])
    ctrl = {n: controls(rows) for n, rows in ds.items()}
    if any(len(x) == 0 for x in ctrl.values()):
        raise ValueError("missing omission control")
    best = None
    options = []
    for full in (0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7):
        for crop in (0, 0.10, 0.20, 0.35, 0.50, 0.65, 0.80, 0.90):
            policy = dict(full=full, crop=crop)
            cards = {
                n: score_run(prior.DEV[n], selected(ds[n], policy), cycle.OFF)[0]
                for n in prior.DEV
            }
            ar = {
                n: cycle.archive(selected(rows, policy), 1.01)
                for n, rows in ds.items()
                if n not in prior.DEV
            }
            eligible = all(s["passed"] for s in cards.values()) and all(
                s["precision"] >= 0.85 and s["recall"] >= 0.80 for s in ar.values()
            )
            cp = {
                n: dict(
                    recovered=sum(
                        any(c["score"] >= full and c["crop_car"] >= crop for c in v)
                        for v in cases
                    ),
                    cases=len(cases),
                )
                for n, cases in ctrl.items()
            }
            rates = [v["recovered"] / v["cases"] for v in cp.values()]
            tp = sum(s["card"]["micro"]["tp"] for s in cards.values()) + sum(
                s["tp"] for s in ar.values()
            )
            fp = sum(s["card"]["micro"]["fp"] for s in cards.values()) + sum(
                s["fp"] for s in ar.values()
            )
            rank = (min(rates), sum(rates), tp, -fp, full, crop)
            options.append(
                dict(
                    policy=policy,
                    eligible=eligible,
                    min_control_recall=min(rates),
                    tp=tp,
                    fp=fp,
                )
            )
            if eligible and min(rates) >= 0.65 and (best is None or rank > best[0]):
                best = (
                    rank,
                    dict(
                        passed=True,
                        policy=policy,
                        thresholds=cycle.OFF,
                        classes=cards,
                        archive=ar,
                        controls=cp,
                    ),
                )
    dump(WORK / "options.json", options)
    if best is None:
        raise ValueError("no qualified recovery policy")
    dump(WORK / "selection.json", best[1])


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
            candidates = recovery.proposals(im, ds, model, yolo, classes)
            parent = recovery.add(ds, candidates, EARLIER["threshold"])
        else:
            r = next(old)
            if r["rgb"] != f["rgb_sha256"]:
                raise ValueError("parent RGB")
            parent = r["detections"]
            candidates = recovery.proposals(im, parent, model, yolo, classes)
        det = add(parent, candidates, selection["policy"])
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
    card, _ = score_run(run, rows, cycle.OFF)
    dump(WORK / (name + "-score.json"), card)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("cache", "select"))
    p.add_argument("name", nargs="?")
    a = p.parse_args()
    if a.action == "cache":
        cache(a.name)
    else:
        select()

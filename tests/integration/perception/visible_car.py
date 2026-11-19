"""Qualify supplemental small-car boxes using measured visible-mask support on development roads."""

import argparse
import gzip
import hashlib
import json
import time

import numpy as np

import small_car as tiles
from small_car_plan import ROOT
from small_car import read, dump, records, prior, score_run, cycle, iou, write_stream
from multiview_audit import audit, annotate, unpack, rgb_bytes

WORK = ROOT / "build/m10-visible-car-v1"
EVIDENCE = ROOT / "docs/test-plan/evidence/m10_visible_car_v1"
PARENT = ROOT / "docs/test-plan/evidence/m10_small_car_v1"
FIX = read(PARENT / "selection.json")


def calibrate():
    road = {}
    for name, run in prior.DEV.items():
        ratios = []
        for row, frame in zip(
            records(tiles.WORK / (name + ".jsonl.gz")),
            read(run / "evaluation-only-gt.json")["frames"],
            strict=True,
        ):
            cars = [
                o for o in frame["objects"] + frame["excluded"] if o["class_id"] == 2
            ]
            for d in tiles.add([], row["candidates"], 0.5):
                box = d["box"]
                match, obj = max(
                    ((iou(box, c["box"]), c) for c in cars),
                    key=lambda x: x[0],
                    default=(0, None),
                )
                if match >= 0.25:
                    ratios.append(
                        (
                            obj["native_visible_pixels"] / 16 / prior.area(box),
                            tiles.short_side(obj["box"]) / tiles.short_side(box),
                        )
                    )
        if not ratios:
            raise ValueError("no visible car calibration matches")
        area, side = np.quantile(ratios, 0.1, axis=0)
        road[name] = dict(
            samples=len(ratios), area_fraction=float(area), side_fraction=float(side)
        )
    return dict(
        area_fraction=min(x["area_fraction"] for x in road.values()),
        side_fraction=min(x["side_fraction"] for x in road.values()),
        development_roads=road,
    )


def select_boxes(parent, tiled, calibration):
    if tiled[: len(parent)] != parent:
        raise ValueError("parent boxes changed")
    return parent + [
        d
        for d in tiled[len(parent) :]
        if prior.area(d["box"]) * calibration["area_fraction"] >= 25
        and tiles.short_side(d["box"]) * calibration["side_fraction"] >= 4
    ]


def select():
    cal = calibrate()
    cards = {}

    def rows(name):
        for r in records(tiles.WORK / (name + ".jsonl.gz")):
            proposed = tiles.add(r["parent"], r["candidates"], FIX["cutoff"])
            yield dict(
                rgb=r["rgb"],
                gt=r["gt"],
                base=select_boxes(r["parent"], proposed, cal),
                new={},
            )

    for name, run in prior.DEV.items():
        cards[name] = score_run(run, list(rows(name)), cycle.OFF)[0]
    sites = {
        r["source"]: r["site"]
        for r in read(cycle.PARK / "cache/manifest.json")["validation"]
    }
    archive = list(rows("validation"))
    groups = {
        n: cycle.archive([r for r in archive if sites[r["rgb"]] == n], 1.01)
        for n in set(sites.values())
    }
    total = sum(c["card"]["micro"]["tp"] for c in cards.values()) + sum(
        c["tp"] for c in groups.values()
    )
    old = next(o["tp"] for o in FIX["options"] if o["cutoff"] > 1)
    passed = (
        all(c["passed"] for c in cards.values())
        and all(c["precision"] >= 0.85 and c["recall"] >= 0.8 for c in groups.values())
        and total > old
        and len(archive) == 699
    )
    sel = dict(
        passed=passed,
        calibration=cal,
        classes=cards,
        archive=groups,
        intact_development_tp_gain=total - old,
        thresholds=cycle.OFF,
    )
    dump(EVIDENCE / "selection.json", sel)
    if not passed:
        raise ValueError("visible box policy failed development")


def audit_legacy(run, rows, card, name):
    # Site 101 predates the per-run boot-restoration record used by the later auditor.
    baseline = read(run / "baseline/predictions.json")["rows"]
    captures = read(run / "dataset/capture.json")["frames"]
    truth = read(run / "evaluation-only-gt.json")["frames"]
    if len({r["rgb"] for r in rows}) != 81:
        raise ValueError("historical denominator")
    for r, f, g, b in zip(rows, captures, truth, baseline, strict=True):
        rgb = rgb_bytes(unpack(run / "dataset", f["rgb"], 2560, 1536))
        mask = unpack(run / "dataset", f["instance"], 2560, 1536)
        if (
            not b["valid"]
            or hashlib.sha256(rgb).hexdigest() != r["rgb"]
            or b["rgb_sha256"] != r["rgb"]
            or annotate(mask, 2560, 1536) != (g["objects"], g["excluded"])
        ):
            raise ValueError("historical native identity")
    base, _ = score_run(
        run,
        [dict(rgb=r["rgb_sha256"], base=r["detections"], new={}) for r in baseline],
        cycle.OFF,
    )
    if base["card"]["per_class"] != read(run / "baseline/score.json")["per_class"]:
        raise ValueError("historical YOLOX reproduction")
    result = dict(
        passed=card["passed"],
        candidate=card,
        baseline=base["card"],
        mask_frames_replayed=len(rows),
        capture_sha256=hashlib.sha256(
            (run / "dataset/capture.json").read_bytes()
        ).hexdigest(),
    )
    dump(EVIDENCE / (name + ".json"), result)
    (EVIDENCE / (name + "-detections.json.gz")).write_bytes(
        gzip.compress(
            json.dumps(
                [dict(rgb=r["rgb"], detections=r["detections"]) for r in rows],
                separators=(",", ":"),
            ).encode(),
            mtime=0,
        )
    )
    return result


def evaluate(run, name, source, full=False):
    if not (EVIDENCE / "nomination.json").is_file():
        raise ValueError("missing nomination")
    if full:
        tiles.evaluate(run, source, FIX)
    calibration = read(EVIDENCE / "selection.json")["calibration"]
    rows = []
    for r in records(tiles.WORK / (source + "-verified.jsonl.gz")):
        start = time.perf_counter()
        parent = r["original_parent"]
        if tiles.add(parent, r["candidates"], FIX["cutoff"]) != r["detections"]:
            raise ValueError("tile replay")
        boxes = select_boxes(parent, r["detections"], calibration)
        rows.append(
            dict(
                rgb=r["rgb"],
                original_parent=parent,
                base=boxes,
                new={},
                detections=boxes,
                elapsed_s=r["elapsed_s"] + time.perf_counter() - start,
            )
        )
    card, _ = score_run(run, rows, cycle.OFF)
    write_stream(WORK / (name + "-verified.jsonl.gz"), rows)
    dump(WORK / (name + "-score.json"), card)
    result = (
        audit_legacy(run, rows, card, name)
        if name == "previous101"
        else audit(run, WORK, EVIDENCE, name)
    )
    if not full:
        original = read(PARENT / (source + ".json"))
        if (
            original["capture_sha256"] != result["capture_sha256"]
            or original["baseline"]["micro"] != result["baseline"]["micro"]
        ):
            raise ValueError("historical baseline reproduction")
    dump(
        EVIDENCE / (name + "-additions.json"),
        [
            dict(rgb=r["rgb"], added=r["detections"][len(r["original_parent"]) :])
            for r in rows
        ],
    )
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("select",))
    p.parse_args()
    select()

"""Conservative two-view selection and strict person scoring; no labels in view selection."""

import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import hashlib

import numpy as np
from PIL import Image

from person_zoom_validation import (
    CACHE,
    EVIDENCE,
    MODEL,
    BUNDLE,
    crop_bounds,
    merge,
    detect,
    load_session,
    frames,
    read,
    dump,
    score,
)
from person_pair_candidate import overlaps
from person_proposal_diagnosis import digest

TRAIN = CACHE.parent / "m10-person-zoom-v1/parity/pairs-train.jsonl.gz"
PREVIOUS = EVIDENCE / "m10_person_zoom_v1"


def choose(full, zoom, minimum):
    """Use the native crop only when its newly proposed people have sufficient image support."""
    flags = []
    for det in zoom:
        left, top, right, bottom = det["box"]
        width, height = right - left, bottom - top
        supported = min(width, height) >= minimum and width * height >= 25
        confirmed = bool(
            overlaps(np.array([det["box"]]), [d["box"] for d in full]).max(initial=0)
            >= 0.5
        )
        flags.append(
            dict(width=width, height=height, small=not supported, confirmed=confirmed)
        )
    use = all(not f["small"] or f["confirmed"] for f in flags)
    return (zoom if use else full), use, flags


def rows(path, source):
    with gzip.open(path, "rt") as trace:
        for line, (_, gt, sha, meta) in zip(trace, source, strict=True):
            r = json.loads(line)
            if r["rgb"] != sha:
                raise ValueError("unpaired RGB")
            yield r, gt, meta


def compare(data, minimum):
    counts = {k: Counter() for k in ("full", "raw_zoom", "selected")}
    small = Counter()
    rollbacks = 0
    for r, gt, meta in data:
        selected, use, _ = choose(r["full"], r["zoom"], minimum)
        rollbacks += int(not use)
        for k, pred in (
            ("full", r["full"]),
            ("raw_zoom", r["zoom"]),
            ("selected", selected),
        ):
            c, n, _ = score(pred, gt, meta.get("role", "archive"))
            counts[k].update(c)
            small[k] += n
    base, cand = counts["full"], counts["selected"]
    paired = base["both_eligible"] > 0
    gates = dict(
        pedestrian=cand["pedestrian_tp"] >= base["pedestrian_tp"] + int(paired),
        rider=cand["rider_tp"] >= base["rider_tp"],
        strict_fp=cand["fp"] <= base["fp"] + base["frames"] // 100,
        precision=cand["tp"] >= 0.85 * (cand["tp"] + cand["fp"]),
    )
    if paired:
        gates["both"] = cand["both_matched"] > base["both_matched"]
    return dict(
        counts=counts,
        small_matches=small,
        full_view_fallbacks=rollbacks,
        gates=gates,
        passed=all(gates.values()),
    )


def fit(out):
    train = list(rows(TRAIN, frames(CACHE, "train", True)))
    candidates = []
    for minimum in (4, 4.25, 4.5, 4.75, 5, 5.5, 6, 7, 8):
        record = compare(train, minimum)
        if record["passed"]:
            c = record["counts"]["selected"]
            candidates.append(
                (
                    (c["both_matched"], c["pedestrian_tp"], -c["fp"], -minimum),
                    minimum,
                    record,
                )
            )
    if not candidates:
        raise ValueError("no candidate met training screen")
    _, minimum, record = max(candidates)
    dump(
        out / "selection.json",
        dict(parent=MODEL, minimum=minimum, train_sha256=digest(TRAIN), train=record),
    )


def cached(out, minimum):
    result = {}
    for name, paired in (("archive-validation", False), ("pairs-validation", True)):
        result[name] = compare(
            rows(PREVIOUS / (name + ".jsonl.gz"), frames(CACHE, "validation", paired)),
            minimum,
        )
    dump(out / "validation.json", result)
    print(json.dumps(result), flush=True)


def infer(im, sess, spec, minimum):
    all_dets, _ = detect(im, sess, spec)
    people = [d for d in all_dets if d["class_id"] == 0]
    anchor = max(
        (d for d in all_dets if d["class_id"] in (1, 3)),
        key=lambda d: d["score"],
        default=None,
    )
    zoom = people
    bounds = None
    if anchor is not None:
        bounds = crop_bounds(im.size, anchor["box"])
        local, _ = detect(im.crop(bounds), sess, spec)
        zoom = merge(people, local, bounds, im.size)
    selected, use, flags = choose(people, zoom, minimum)
    primary = [d for d in all_dets if d["class_id"] != 0] + selected
    return primary, dict(
        full=people,
        zoom=zoom,
        bounds=bounds,
        use_zoom=bool(bounds and use),
        flags=flags,
    )


def six_class(out, run, minimum):
    from fresh_quality_2k_review import rgb_bytes
    from fresh_quality_2k_score import PROTOCOL
    from physical_ai.perception.camera_resolution_v1 import unpack
    from quality_benchmark import relative
    from run_resolution_v2 import quality

    sess, spec = load_session(BUNDLE)
    if spec["model_sha256"] != MODEL:
        raise ValueError("parent model")
    images = read(run / "images.json")["frames"]
    if len(images) != 81:
        raise ValueError("six-class denominator")
    scores = []
    records = []
    for f, scene, gt in zip(
        images,
        read(run / "benchmark.json")["scenes"],
        read(run / "evaluation-only-gt.json")["frames"],
        strict=True,
    ):
        rgb = rgb_bytes(unpack(run / "dataset", f["rgb_raw"], 2560, 1536))
        if (
            hashlib.sha256(rgb).hexdigest() != f["rgb_sha256"]
            or not f["scene"] == scene["scene"] == gt["scene"]
        ):
            raise ValueError("image association")
        pred, views = infer(
            Image.frombytes("RGB", (2560, 1536), rgb), sess, spec, minimum
        )
        scores.append((scene, gt, pred, True, False, None))
        records.append(dict(rgb=f["rgb_sha256"], detections=pred, **views))
    card = {k: v for k, v in quality(scores).items() if k != "records"}
    rel = relative(read(run / "baseline/score.json"), card, read(PROTOCOL))
    dump(out / (run.name + "-detections.json"), records)
    dump(
        out / (run.name + "-score.json"),
        dict(
            card=card,
            relative=rel,
            passed=card["absolute_quality"] == "PASS" and rel["status"] == "PASS",
        ),
    )
    print(card["absolute_quality"], rel["status"], card["micro"], flush=True)


def new_development(out, minimum):
    from person_pair_review import audit

    town = "Town05_Opt"
    dump(out / "visibility.json", audit(out, "validation", town))
    ds = out / town / "dataset"
    session, spec = load_session(BUNDLE)
    if spec["model_sha256"] != MODEL:
        raise ValueError("model identity")
    history = {
        r["rgb"]
        for part in (
            "pairs-train",
            "pairs-validation",
            "archive-train",
            "archive-validation",
        )
        for r in read(CACHE / part / "index.json")
    }
    data = []
    with gzip.open(out / "fresh.jsonl.gz", "wt") as log:
        for scene, gt in zip(
            read(ds / "plan.json")["scenes"], read(ds / "labels.json"), strict=True
        ):
            with Image.open(ds / (gt["id"] + ".png")) as img:
                im = img.convert("RGB")
            sha = hashlib.sha256(im.tobytes()).hexdigest()
            if sha != gt["rgb_sha256"] or sha in history or scene["id"] != gt["id"]:
                raise ValueError("fresh capture association")
            history.add(sha)
            pred, views = infer(im, session, spec, minimum)
            r = dict(rgb=sha, scene=gt["id"], **views)
            log.write(json.dumps(r) + "\n")
            data.append((r, gt, scene))
    dump(out / "fresh.json", compare(data, minimum))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=("fit", "cached", "six", "fresh"))
    p.add_argument("output", type=Path)
    p.add_argument("--run", type=Path)
    a = p.parse_args()
    if a.action == "fit":
        fit(a.output)
    else:
        sel = read(a.output / "selection.json")
        if sel["parent"] != MODEL:
            raise ValueError("parent model")
        if a.action == "six":
            six_class(a.output, a.run, sel["minimum"])
        else:
            {"cached": cached, "fresh": new_development}[a.action](
                a.output, sel["minimum"]
            )

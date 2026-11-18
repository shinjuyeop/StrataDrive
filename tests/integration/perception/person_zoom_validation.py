"""Validate the frozen two-wheeler crop, measuring warm RGB-to-detection latency."""

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
from time import perf_counter_ns

import numpy as np
from PIL import Image

from parking_onnx_replay import load_session
from person_assignment_candidate import CACHE
from person_pair_candidate import BUNDLE, MODEL, dump, frames, read
from person_pair_errors import false_positives
from physical_ai.perception.parking_candidate import detections
from quality_benchmark_v3 import measure

EVIDENCE = Path(__file__).resolve().parents[3] / "docs/test-plan/evidence"


def crop_bounds(size, box):
    w, h = size
    if w * 384 != h * 640 or w % 8 or h % 8:
        raise ValueError("unexpected native RGB geometry")
    extent = np.array([w, h]) * 3 // 8
    scale = np.array([w / 640, h / 384])
    center = (np.array(box[:2]) + box[2:]) * scale / 2
    origin = np.rint(center - extent / 2).clip(0, np.array(size) - extent).astype(int)
    return tuple(map(int, (*origin, *(origin + extent))))


def merge(people, local, bounds, size):
    scale = np.array(size) / [640, 384]
    origin = np.array(bounds[:2]) / scale
    end = np.array(bounds[2:]) / scale
    merged = []
    for d in people:
        b = d["box"]
        center = (np.asarray(b[:2]) + b[2:]) / 2
        if not ((origin <= center) & (center < end)).all():
            merged.append(d)
    for d in local:
        if d["class_id"] == 0:
            box = np.asarray(d["box"]) * np.tile(
                (end - origin) / [640, 384], 2
            ) + np.tile(origin, 2)
            merged.append(dict(d, box=box.tolist()))
    return merged


def detect(image, session, spec):
    x = np.ascontiguousarray(
        np.asarray(
            image.resize((960, 960), Image.Resampling.BILINEAR), np.float32
        ).transpose(2, 0, 1)[None]
        / 255
    )
    t = perf_counter_ns()
    vals = session.run(spec["outputs"], {"images": x})
    gpu_call = perf_counter_ns() - t
    return detections(dict(zip(spec["outputs"], vals, strict=True)), spec), gpu_call


def replay(image, session, spec):
    start = perf_counter_ns()
    dets, first_ort = detect(image, session, spec)
    base = [d for d in dets if d["class_id"] == 0]
    first = perf_counter_ns()
    anchor = max(
        (d for d in dets if d["class_id"] in (1, 3)),
        key=lambda d: d["score"],
        default=None,
    )
    zoom = base
    second_ort = 0
    bounds = None
    if anchor is not None:
        bounds = crop_bounds(image.size, anchor["box"])
        local, second_ort = detect(image.crop(bounds), session, spec)
        zoom = merge(base, local, bounds, image.size)
    end = perf_counter_ns()
    return (
        base,
        zoom,
        bounds,
        dict(
            full=first - start,
            increment=end - first,
            total=end - start,
            first_ort=first_ort,
            second_ort=second_ort,
        ),
    )


def score(pred, truth, role):
    gt = [o for o in truth["objects"] if o["class_id"] == 0]
    counts, used, _, ignored, _ = measure(pred, gt, truth["excluded"])
    c = Counter(counts["0"], frames=1)
    for i, o in enumerate(gt):
        subtype = {(12,): "pedestrian", (13,): "rider"}[tuple(o["semantic_tags"])]
        c[subtype + ("_tp" if i in used else "_fn")] += 1
    if role == "cycle" and {tuple(o["semantic_tags"]) for o in gt} == {(12,), (13,)}:
        c["both_eligible"] += 1
        c["both_matched"] += int(len(used) == len(gt))
    return c, len(ignored), Counter(kind for _, kind in false_positives(pred, truth))


def latency(samples):
    if not samples:
        return {"frames": 0}
    summary = {"frames": len(samples)}
    for name in samples[0]:
        ms = np.array([s[name] for s in samples]) * 1e-6
        summary[name] = dict(
            mean=float(ms.mean()),
            p50=float(np.median(ms)),
            p95=float(np.percentile(ms, 95)),
            p99=float(np.percentile(ms, 99)),
            max=float(ms.max()),
        )
    return summary


def run(out, training):
    session, spec = load_session(BUNDLE)
    if spec["model_sha256"] != MODEL:
        raise ValueError("frozen model changed")
    warm = next(frames(CACHE, "train", True))[0]
    with Image.open(warm) as im:
        image = im.convert("RGB")
        for _ in range(12):
            detect(image, session, spec)
    refs = read(EVIDENCE / "m10_person_assignment_v1/result.json")["splits"]
    out.mkdir(parents=True, exist_ok=True)
    splits = (
        ("pairs-train",) if training else ("archive-validation", "pairs-validation")
    )
    seen = (
        set()
        if training
        else {
            r["rgb"]
            for k in ("archive-train", "pairs-train")
            for r in read(CACHE / k / "index.json")
        }
    )
    result = {}
    for name in splits:
        groups = defaultdict(lambda: defaultdict(Counter))
        errors = defaultdict(Counter)
        small = Counter()
        triggered = Counter()
        sizes = Counter()
        times = defaultdict(list)
        with gzip.open(out / (name + ".jsonl.gz"), "wt") as log:
            for path, truth, sha, meta in frames(
                CACHE, "train" if training else "validation", name.startswith("pairs")
            ):
                with Image.open(path) as src:
                    im = src.convert("RGB")
                if sha in seen or hashlib.sha256(im.tobytes()).hexdigest() != sha:
                    raise ValueError("duplicate or changed RGB")
                seen.add(sha)
                base, zoom, bounds, timing = replay(im, session, spec)
                role = meta.get("role", "archive")
                sizes[str(im.size)] += 1
                if bounds:
                    triggered[role] += 1
                times["all"].append(timing)
                times["triggered" if bounds else "untriggered"].append(timing)
                for mode, pred in (("full", base), ("zoom", zoom)):
                    c, n, err = score(pred, truth, role)
                    for group in ("all", role):
                        groups[group][mode].update(c)
                    errors[mode].update(err)
                    small[mode] += n
                log.write(
                    json.dumps(
                        dict(
                            rgb=sha,
                            role=role,
                            bounds=bounds,
                            timing_ns=timing,
                            full=base,
                            zoom=zoom,
                        )
                    )
                    + "\n"
                )
        full, zoom = (groups["all"][k] for k in ("full", "zoom"))
        if training:
            ref = read(EVIDENCE / "m10_person_assignment_v1/train-zoom.json")
            if (
                groups != ref["groups"]
                or triggered != ref["triggered"]
                or errors != ref["false_positives"]
            ):
                raise ValueError("2K training probe parity")
            gates = {}
        else:
            ref = refs[name]["groups"]["all"]["baseline"]
            if any(
                full[k] != ref.get(k, 0)
                for k in (
                    "frames",
                    "tp",
                    "fp",
                    "fn",
                    "pedestrian_tp",
                    "rider_tp",
                    "both_eligible",
                    "both_matched",
                )
            ):
                raise ValueError("validation denominator or baseline drift")
            paired = name == "pairs-validation"
            gates = dict(
                pedestrian=zoom["pedestrian_tp"] >= full["pedestrian_tp"] + int(paired),
                rider=zoom["rider_tp"] >= full["rider_tp"],
                strict_fp=zoom["fp"] <= full["fp"] + full["frames"] // 100,
                precision=zoom["tp"] >= 0.85 * (zoom["tp"] + zoom["fp"]),
            )
            if paired:
                gates["simultaneous_pair_gain"] = (
                    zoom["both_matched"] > full["both_matched"]
                )
        result[name] = dict(
            groups=groups,
            strict_fp_types=errors,
            one_to_one_small_matches=small,
            triggered=triggered,
            sizes=sizes,
            latency_ms={
                k: latency(times[k]) for k in ("all", "triggered", "untriggered")
            },
            gates=gates,
        )
        print(name, dict(full), dict(zoom), gates, flush=True)
    dump(
        out / "result.json",
        dict(
            parent=MODEL,
            splits=result,
            passed=None
            if training
            else all(all(v["gates"].values()) for v in result.values()),
        ),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("output", type=Path)
    p.add_argument("--training-parity", action="store_true")
    args = p.parse_args()
    run(args.output, args.training_parity)

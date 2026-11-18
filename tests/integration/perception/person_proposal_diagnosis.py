"""Trace the frozen person decoder on the exact archived training and validation splits."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
PARK = ROOT / "build/m10-parking-verifier-v1"
BUNDLE = PARK / "export-bus-truck"
DOMAIN = ROOT / "build/m10-domain-data-v1"
PREV = ROOT / "build/m10-occlusion-transfer-v1"
MODEL = "cebce257cc2cd456a229467f47d19101ee0cad336833e6627d29ecf640c52683"
BOXES = "/post/Mul_4_output_0"
PROBS = "/post/Sigmoid_output_0"
RANK = "/post/TopK_output_1"
THRESHOLDS = (0.35, 0.4, 0.5, 0.6)


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def instrument(out):
    import onnx
    from onnx import TensorProto, helper

    source = BUNDLE / "parking-dfine-960.onnx"
    if digest(source) != MODEL:
        raise ValueError("unexpected model")
    if (out / source.name).resolve() == source.resolve():
        raise ValueError("choose a separate diagnostic directory")
    graph = onnx.load(source)
    nodes = {o: n for n in graph.graph.node for o in n.output}
    if not (
        nodes["boxes"].input[0] == BOXES
        and nodes[nodes["scores"].input[0]].input[0] == PROBS
        and nodes["scores"].output[1] == RANK
    ):
        raise ValueError("unexpected decoder topology")
    for key, dtype, shape in (
        (BOXES, TensorProto.FLOAT, [1, 300, 4]),
        (PROBS, TensorProto.FLOAT, [1, 300, 80]),
        (RANK, TensorProto.INT64, [1, 300]),
    ):
        graph.graph.output.append(helper.make_tensor_value_info(key, dtype, shape))
    onnx.checker.check_model(graph)
    path = out / source.name
    onnx.save(graph, path)
    spec = read(BUNDLE / "manifest.json")
    spec.update(model_sha256=digest(path), source_sha256=MODEL)
    (out / "manifest.json").write_text(json.dumps(spec, indent=2) + "\n")


def source_frames(split):
    files = {}

    def add(key, *values):
        if key in files:
            raise ValueError("duplicate RGB in split")
        files[key] = values

    for ds in (
        PREV / "run-02/dataset",
        PREV / "parked-03/dataset",
        PARK
        / ("Town10HD_Opt-stock-02" if split == "train" else "Town02_Opt-stock-02")
        / "dataset",
    ):
        plan = {s["id"]: s for s in read(ds / "plan.json")["scenes"]}
        for r in read(ds / "labels.json"):
            if r["split"] != split:
                continue
            scene = plan[r["id"]]
            poses = {
                k % 65536: a["pose"]
                for k, a in zip(r["actor_ids"], scene["actors"], strict=True)
            }
            add(
                r["rgb_sha256"],
                ds / (r["id"] + ".png"),
                r,
                scene["camera"],
                poses,
                None,
            )

    export = DOMAIN / "export"
    info = read(export / "dataset.json")["splits"][split]
    path = export / info["annotation_path"]
    if digest(path) != info["annotation_sha256"]:
        raise ValueError("COCO labels changed")
    coco = read(path)
    captures = {}
    capture_hashes = {i["capture_sha256"] for i in coco["images"]}
    for site in ("14", "31", "74") if split == "train" else ("104",):
        for path in DOMAIN.glob(f"*{split}-{site}-*/dataset/capture.json"):
            fingerprint = digest(path)
            if fingerprint in capture_hashes:
                captures[fingerprint] = {s["id"]: s for s in read(path)["scenes"]}
    by_id = defaultdict(lambda: dict(objects=[], excluded=[]))
    for a in coco["annotations"]:
        x, y, w, h = a["bbox"]
        by_id[a["image_id"]][
            "objects" if a["m10_quality_eligible"] else "excluded"
        ].append(
            dict(
                class_id=a["category_id"] - 1,
                box=[x, y, x + w, y + h],
                semantic_tags=a["m10_semantic_tags"],
                instance_id=a["m10_instance_id"],
            )
        )
    for r in coco["images"]:
        scene = captures[r["capture_sha256"]][r["scene"]]
        poses = {a["actor_id"] % 65536: a["pose"] for a in scene["actors"]}
        add(
            r["rgb_sha256"],
            PREV / "archived-training-images" / r["file_name"],
            by_id[r["id"]],
            scene["camera_pose"],
            poses,
            scene["stratum"],
        )
    return files


def run(out):
    from parking_onnx_replay import load_session
    from physical_ai.perception.class_calibration_v1 import decode
    from physical_ai.perception.resolution_car_v1 import VECTOR
    from quality_benchmark_v3 import measure

    session, spec = load_session(out)
    if spec["source_sha256"] != MODEL or VECTOR[0] != THRESHOLDS[-1]:
        raise ValueError("diagnosis model or confidence mismatch")
    manifest = read(PARK / "cache/manifest.json")
    seen = set()
    with (out / "frames.jsonl").open("w") as log:
        for split in ("train", "validation"):
            files = source_frames(split)
            entries = manifest[split]
            if (
                len(files) != len(entries)
                or set(files) != {e["source"] for e in entries}
                or seen.intersection(files)
            ):
                raise ValueError("split identity mismatch")
            seen.update(files)
            for i, e in enumerate(entries):
                path, gt, camera, poses, stratum = files[e["source"]]
                with Image.open(path) as src:
                    rgb = src.convert("RGB")
                if hashlib.sha256(rgb.tobytes()).hexdigest() != e["source"]:
                    raise ValueError("source RGB changed")
                tensor = (
                    np.asarray(
                        rgb.resize((960, 960), Image.Resampling.BILINEAR), np.float32
                    ).transpose(2, 0, 1)[None]
                    / 255
                )
                keys = ["labels", "boxes", "scores"]
                raw_outputs = session.run(
                    keys + [BOXES, PROBS, RANK] + ["original_" + k for k in keys],
                    {"images": np.ascontiguousarray(tensor)},
                )
                labels, boxes, scores, query_boxes, probs, rank = raw_outputs[:6]
                if not (
                    np.array_equal(labels, rank % 80)
                    and np.array_equal(boxes[0], query_boxes[0, rank[0] // 80])
                    and np.array_equal(scores[0], probs.reshape(-1)[rank[0]])
                    and np.isfinite(probs).all()
                ):
                    raise ValueError("query to top-300 parity")
                raw = dict(zip(keys, (labels, boxes, scores), strict=True))
                floor = decode(raw, (THRESHOLDS[0], *VECTOR[1:]))
                people = [
                    dict(class_id=0, score=d.score, box=d.box)
                    for d in floor
                    if d.class_id == 0
                ]
                original = decode(dict(zip(keys, raw_outputs[6:], strict=True)), VECTOR)
                original_counts, original_matched, *_ = measure(
                    [
                        dict(class_id=0, score=d.score, box=d.box)
                        for d in original
                        if d.class_id == 0
                    ],
                    gt["objects"],
                    gt["excluded"],
                )
                counts = {}
                matches = {}
                for t in THRESHOLDS:
                    by_class, matched, *_ = measure(
                        [d for d in people if d["score"] >= t],
                        gt["objects"],
                        gt["excluded"],
                    )
                    counts[t] = by_class["0"]
                    matches[t] = matched
                clipped = np.clip(query_boxes[0].astype(float), [0] * 4, [640, 384] * 2)
                objects = []
                for n, obj in enumerate(gt["objects"]):
                    if obj["class_id"] != 0:
                        continue
                    others = [o["box"] for o in gt["objects"] if o is not obj]
                    row = diagnose(
                        obj["box"],
                        n in matches[VECTOR[0]],
                        clipped,
                        probs[0, :, 0],
                        people,
                    )
                    pose = poses.get(obj["instance_id"])
                    distance = (
                        math.dist(
                            [camera["location"][k] for k in "xyz"],
                            [pose["location"][k] for k in "xyz"],
                        )
                        if pose
                        else None
                    )
                    row.update(
                        original_match=n in original_matched,
                        thresholds_matched=[t for t, m in matches.items() if n in m],
                        instance=obj["instance_id"],
                        tags=obj["semantic_tags"],
                        height=obj["box"][3] - obj["box"][1],
                        distance_m=distance,
                        other_box_cover=max(
                            (cover(obj["box"], b) for b in others), default=0
                        ),
                    )
                    objects.append(row)
                record = dict(
                    split=split,
                    group=e["site"],
                    scene=path.stem,
                    rgb=e["source"],
                    scene_stratum=stratum,
                    counts=counts,
                    original_counts=original_counts["0"],
                    people=objects,
                )
                log.write(json.dumps(record, allow_nan=False) + "\n")
                if (i + 1) % 200 == 0:
                    print(split, i + 1, flush=True)


def cover(a, b):
    return (
        max(0, min(a[2], b[2]) - max(a[0], b[0]))
        * max(0, min(a[3], b[3]) - max(a[1], b[1]))
        / ((a[2] - a[0]) * (a[3] - a[1]))
    )


def diagnose(truth, matched, boxes, scores, selected):
    from evaluate import overlap

    iou = np.array([overlap(truth, b) for b in boxes])
    close = iou >= 0.5
    best = float(scores[close].max()) if close.any() else None
    if matched:
        reason = "detected"
    elif best is None:
        reason = "no_box_iou50"
    elif best < THRESHOLDS[-1]:
        reason = "below_score"
    elif any(
        d["score"] >= THRESHOLDS[-1] and overlap(truth, d["box"]) >= 0.5
        for d in selected
    ):
        reason = "one_to_one"
    else:
        reason = "top300"
    return dict(reason=reason, best_iou=float(iou.max()), best_person_score=best)


def summarize(out):
    records = [
        json.loads(line) for line in (out / "frames.jsonl").read_text().splitlines()
    ]
    reference = read(
        ROOT
        / "docs/test-plan/evidence/m10_parking_verifier_v1/selected/validation.json"
    )
    manifest = read(PARK / "cache/manifest.json")
    if reference["model"] != MODEL:
        raise ValueError("validation reference model")
    result = dict(
        model_sha256=MODEL,
        manifest_sha256=digest(PARK / "cache/manifest.json"),
        frame_records_sha256=digest(out / "frames.jsonl"),
        splits={},
    )
    for split in ("train", "validation"):
        frames = [f for f in records if f["split"] == split]
        if [(f["rgb"], f["group"]) for f in frames] != [
            (e["source"], e["site"]) for e in manifest[split]
        ]:
            raise ValueError("incomplete replay")
        metrics = {str(t): Counter() for t in THRESHOLDS}
        by_group = defaultdict(Counter)
        original_counts = Counter()
        paired = defaultdict(Counter)
        subtype_threshold_tp = defaultdict(Counter)
        strata = defaultdict(lambda: defaultdict(Counter))
        missed = defaultdict(Counter)
        for f in frames:
            for t, counts in metrics.items():
                counts.update(f["counts"][t])
            original_counts.update(f["original_counts"])
            by_group[f["group"]].update(f["counts"]["0.6"])
            outcomes = Counter(o["reason"] for o in f["people"])
            if (
                outcomes["detected"] != f["counts"]["0.6"]["tp"]
                or len(f["people"]) - outcomes["detected"] != f["counts"]["0.6"]["fn"]
            ):
                raise ValueError("miss attribution denominator")
            for o in f["people"]:
                kind = {(12,): "pedestrian", (13,): "rider"}[tuple(o["tags"])]
                adapted = o["reason"] == "detected"
                paired[kind][
                    ("both" if adapted else "original_only")
                    if o["original_match"]
                    else ("adapted_only" if adapted else "neither")
                ] += 1
                subtype_threshold_tp[kind].update(map(str, o["thresholds_matched"]))
                d = o["distance_m"]
                band = (
                    "unknown"
                    if d is None
                    else ("under15m" if d < 15 else "15to30m" if d < 30 else "30m_plus")
                )
                coverage = (
                    "overlap25pct_plus"
                    if o["other_box_cover"] >= 0.25
                    else "overlap_under25pct"
                )
                for key in (
                    "all",
                    band,
                    coverage,
                    "scene_" + (f["scene_stratum"] or "unlabelled"),
                ):
                    strata[kind][key][o["reason"]] += 1
                if o["reason"] == "below_score":
                    bucket = (
                        "under_decode_floor"
                        if o["best_person_score"] < THRESHOLDS[0]
                        else "between_floor_and_threshold"
                    )
                    missed[kind][bucket] += 1
        if split == "validation" and dict(by_group) != {
            k: g["classes"]["0"] for k, g in reference["groups"].items()
        }:
            raise ValueError("frozen validation totals differ")
        result["splits"][split] = dict(
            frames=len(frames),
            thresholds=metrics,
            subtype_threshold_tp=subtype_threshold_tp,
            original_at_06=original_counts,
            original_vs_adapted_at_06=paired,
            by_group=by_group,
            by_subtype=strata,
            score_misses=missed,
        )
    (out / "summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["instrument", "run", "summarize"])
    p.add_argument("output", type=Path)
    args = p.parse_args()
    {"instrument": instrument, "run": run, "summarize": summarize}[args.action](
        args.output
    )

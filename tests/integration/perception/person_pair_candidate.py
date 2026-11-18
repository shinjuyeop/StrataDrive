"""Fit and compare one additive person verifier using frozen D-FINE query features."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from person_proposal_diagnosis import (
    BUNDLE,
    BOXES,
    MODEL,
    PARK,
    PROBS,
    digest,
    read,
    source_frames,
)

FEATURE = "/decoder/decoder/layers.3/norm3/Add_1_output_0"
CONFIDENCE = 0.60
MIN_PROPOSAL = 0.01
TOWNS = {"train": "Town01_Opt", "validation": "Town07_Opt"}


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def instrument(root):
    import onnx
    from onnx import helper, TensorProto

    bundle = root / "features"
    bundle.mkdir(exist_ok=True)
    source = BUNDLE / "parking-dfine-960.onnx"
    if digest(source) != MODEL:
        raise ValueError("unexpected frozen model")
    g = onnx.load(source)
    for k, shape in [
        (FEATURE, [1, 300, 256]),
        (BOXES, [1, 300, 4]),
        (PROBS, [1, 300, 80]),
    ]:
        g.graph.output.append(
            helper.make_tensor_value_info(k, TensorProto.FLOAT, shape)
        )
    onnx.checker.check_model(g)
    path = bundle / source.name
    onnx.save(g, path)
    dump(
        bundle / "manifest.json",
        dict(
            read(BUNDLE / "manifest.json"),
            model_sha256=digest(path),
            parent_sha256=MODEL,
        ),
    )


def frames(root, split, paired):
    if not paired:
        manifest = read(PARK / "cache/manifest.json")[split]
        files = source_frames(split)
        if set(files) != {v["source"] for v in manifest} or len(files) != len(manifest):
            raise ValueError("archive manifest mismatch")
        for e in manifest:
            path, gt, *_ = files[e["source"]]
            yield path, gt, e["source"], {}
        return
    ds = root / TOWNS[split] / "dataset"
    plan = read(ds / "plan.json")
    if plan["map"].rsplit("/", 1)[-1] != TOWNS[split] or plan["size"] != [2560, 1536]:
        raise ValueError("paired map or camera")
    for scene, gt in zip(plan["scenes"], read(ds / "labels.json"), strict=True):
        if (
            gt["id"] != scene["id"]
            or gt["split"] != scene["split"]
            or gt["split"] != split
        ):
            raise ValueError("pair association")
        yield (
            ds / (gt["id"] + ".png"),
            gt,
            gt["rgb_sha256"],
            {k: scene[k] for k in ("role", "group", "distance_m", "site")},
        )


def cache(root, split, paired):
    from parking_onnx_replay import load_session
    from physical_ai.perception.class_calibration_v1 import decode
    from physical_ai.perception.resolution_car_v1 import VECTOR

    folder = root / (("pairs-" if paired else "archive-") + split)
    folder.mkdir(exist_ok=True)
    sess, spec = load_session(root / "features")
    if spec["parent_sha256"] != MODEL:
        raise ValueError("unexpected feature model")
    records = []
    for i, (path, gt, rgb, meta) in enumerate(frames(root, split, paired)):
        with Image.open(path) as im:
            im = im.convert("RGB")
        if hashlib.sha256(im.tobytes()).hexdigest() != rgb:
            raise ValueError("RGB identity")
        x = np.ascontiguousarray(
            np.asarray(
                im.resize((960, 960), Image.Resampling.BILINEAR), np.float32
            ).transpose(2, 0, 1)[None]
            / 255
        )
        labels, boxes, scores, feat, coords, prob = sess.run(
            ["labels", "boxes", "scores", FEATURE, BOXES, PROBS], {"images": x}
        )
        original = [
            dict(class_id=0, score=d.score, box=d.box)
            for d in decode(dict(labels=labels, boxes=boxes, scores=scores), VECTOR)
            if d.class_id == 0
        ]
        b = coords[0].clip(0, [640, 384, 640, 384])
        prob = prob[0, :, 0]
        idx = (prob >= MIN_PROPOSAL) & (b[:, 2:] > b[:, :2]).all(axis=1)
        name = f"{i:04}.npz"
        np.savez(folder / name, x=feat[0, idx], boxes=b[idx], p=prob[idx])
        records.append(
            dict(
                file=name,
                rgb=rgb,
                objects=[o for o in gt["objects"] if o["class_id"] == 0],
                excluded=[o for o in gt["excluded"] if o["class_id"] == 0],
                original=original,
                **meta,
            )
        )
    if len(records) != len({r["rgb"] for r in records}):
        raise ValueError("duplicate images")
    dump(folder / "index.json", records)


def overlaps(boxes, truth):
    b = np.asarray(truth, dtype=float).reshape(-1, 4)
    inter = (
        (
            np.minimum(boxes[:, None, 2:], b[:, 2:])
            - np.maximum(boxes[:, None, :2], b[:, :2])
        )
        .clip(0)
        .prod(axis=2)
    )
    union = (
        (boxes[:, 2:] - boxes[:, :2]).prod(axis=1)[:, None]
        + (b[:, 2:] - b[:, :2]).prod(axis=1)
        - inter
    )
    return inter / union.clip(1e-9)


def logit(p):
    return np.log(p.clip(1e-6, 1 - 1e-6) / (1 - p.clip(1e-6, 1 - 1e-6)))


def samples(root):
    features, priors, labels, weights = [], [], [], []
    for prefix in ("archive", "pairs"):
        folder = root / (prefix + "-train")
        for r in read(folder / "index.json"):
            with np.load(folder / r["file"]) as data:
                b, x, p = (data[k] for k in ("boxes", "x", "p"))
            iou = overlaps(b, [o["box"] for o in r["objects"]])
            pos = iou.max(axis=1, initial=0) >= 0.5
            ign = (
                overlaps(b, [o["box"] for o in r["excluded"]]).max(axis=1, initial=0)
                >= 0.35
            )
            neg = np.flatnonzero(~ign & (iou.max(axis=1, initial=0) < 0.3))
            hard = neg[np.argsort(-p[neg], kind="stable")[:16]]
            idx = np.r_[np.flatnonzero(pos), hard]
            features.append(x[idx])
            priors.append(logit(p[idx]))
            labels.append(pos[idx])
            weights.append(np.full(len(idx), 4.0 if prefix == "pairs" else 1.0))
    return [
        np.concatenate(v).astype(float) for v in (features, priors, labels, weights)
    ]


def fit(root):
    from scipy.optimize import minimize
    from scipy.special import expit

    x, prior, y, w = samples(root)
    w /= w.sum()

    def objective(beta):
        z = prior + x @ beta[:-1] + beta[-1]
        resid = w * (expit(z) - y)
        return (
            np.dot(w, np.logaddexp(0, z) - y * z)
            + 0.015 * np.dot(beta[:-1], beta[:-1]),
            np.r_[x.T @ resid + 0.03 * beta[:-1], resid.sum()],
        )

    fit = minimize(
        objective,
        np.zeros(x.shape[1] + 1),
        jac=True,
        method="L-BFGS-B",
        options=dict(maxiter=200, ftol=1e-12),
    )
    if not fit.success:
        raise RuntimeError(fit.message)
    dump(
        root / "person-head.json",
        dict(
            parent=MODEL,
            threshold=CONFIDENCE,
            weight=fit.x[:-1].tolist(),
            bias=float(fit.x[-1]),
            positive_queries=int(y.sum()),
            negative_queries=int(len(y) - y.sum()),
            training_indices={
                k: digest(root / k / "index.json")
                for k in ("pairs-train", "archive-train")
            },
        ),
    )


def predictions(row, data, head):
    from scipy.special import expit

    base = list(row["original"])
    b, p, x = (data[k] for k in ("boxes", "p", "x"))
    s = expit(logit(p) + x @ head["weight"] + head["bias"])
    for i in np.argsort(-s, kind="stable"):
        if s[i] < CONFIDENCE:
            break
        if overlaps(b[i : i + 1], [d["box"] for d in base]).max(initial=0) >= 0.45:
            continue
        base.append(dict(class_id=0, score=float(s[i]), box=b[i].tolist()))
    return base


def evaluate(root):
    from quality_benchmark_v3 import measure

    head = read(root / "person-head.json")
    report = {}
    seen = set()
    for key in (
        "archive-train",
        "pairs-train",
        "archive-validation",
        "pairs-validation",
    ):
        folder = root / key
        rows = read(folder / "index.json")
        if seen.intersection(r["rgb"] for r in rows):
            raise ValueError("overlapping experiment splits")
        seen.update(r["rgb"] for r in rows)
        totals = defaultdict(lambda: defaultdict(Counter))
        for row in rows:
            with np.load(folder / row["file"]) as data:
                candidate = predictions(row, data, head)
            for name, pred in (("baseline", row["original"]), ("candidate", candidate)):
                counts, used, *_ = measure(pred, row["objects"], row["excluded"])
                for tag in ["all"] + (
                    [row["role"], "30m_plus"]
                    if row.get("distance_m", 0) >= 30
                    else ([row["role"]] if "role" in row else [])
                ):
                    c = totals[tag][name]
                    c.update(counts["0"])
                    c["frames"] += 1
                    for n, o in enumerate(row["objects"]):
                        k = {(12,): "pedestrian", (13,): "rider"}[
                            tuple(o["semantic_tags"])
                        ]
                        c[k + ("_tp" if n in used else "_fn")] += 1
        report[key] = totals
    reference = read(PARK / "selected-validation.json")
    orig = report["archive-validation"]["all"]["baseline"]
    if any(
        orig[k] != sum(s["classes"]["0"][k] for s in reference["groups"].values())
        for k in ("tp", "fp", "fn")
    ):
        raise ValueError("archive baseline parity")
    gates = {}
    for key in ("archive-validation", "pairs-validation"):
        base, cand = (report[key]["all"][k] for k in ("baseline", "candidate"))
        gates[key] = dict(
            pedestrian=cand["pedestrian_tp"]
            >= base["pedestrian_tp"] + (key == "pairs-validation"),
            rider=cand["rider_tp"] >= base["rider_tp"],
            fp=cand["fp"] <= base["fp"] + int(0.01 * base["frames"]),
            precision=cand["tp"] >= 0.85 * (cand["tp"] + cand["fp"]),
        )
    dump(
        root / "comparison.json",
        dict(
            parent=MODEL,
            head_sha256=digest(root / "person-head.json"),
            counts=report,
            gates=gates,
            passed=all(all(v.values()) for v in gates.values()),
        ),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("instrument", "cache", "fit", "evaluate"))
    p.add_argument("root", type=Path)
    p.add_argument("--split", choices=("train", "validation"), default="train")
    p.add_argument("--paired", action="store_true")
    a = p.parse_args()
    if a.action == "cache":
        cache(a.root, a.split, a.paired)
    else:
        {"instrument": instrument, "fit": fit, "evaluate": evaluate}[a.action](a.root)

"""Select bus corroboration using both independent validation groups before development replay."""

import argparse
from collections import defaultdict
from pathlib import Path
import hashlib
import numpy as np
from PIL import Image
from physical_ai.perception.parking_candidate import (
    bus_evidence,
    detections,
    select_buses,
)
from parking_validation_replay import inputs
from parking_onnx_replay import load_session
from fresh_quality_2k_review import digest, write
from quality_benchmark_v3 import measure


def run(root, bundle, out, truck_veto=False):
    out.mkdir(exist_ok=False)
    session, spec = load_session(bundle)
    if not spec.get("original_bus") or "bus_policy" in spec:
        raise ValueError("original dual-decoder bundle required")
    policies = [dict(source="adapted")] + [
        dict(source="original", confidence=c, support=s)
        for c in (0.5, 0.6, 0.7)
        for s in (0.0, 0.03, 0.05, 0.10, 0.20, 0.35, 0.5)
    ]
    if truck_veto:
        policies.extend(
            dict(source="original", confidence=c, support=s, truck_veto=t)
            for c in (0.5, 0.6, 0.7)
            for s in (0.0, 0.1, 0.2, 0.35)
            for t in (0.2, 0.35, 0.5, 0.6)
        )
    write(
        out / "protocol.json",
        dict(
            policies=policies,
            matching_iou=0.4,
            truck_conflict_iou=0.7,
            onnx_sha256=spec["model_sha256"],
            validation_manifest=digest(root / "cache/manifest.json"),
            selection="Both groups require micro P >= .85 and R >= .80. Maximize worst-group bus recall, then bus precision, then overall recall. First tie.",
        ),
    )
    counts = [defaultdict(lambda: np.zeros((2, 3), dtype=np.int64)) for _ in policies]
    for entry, path, label in inputs(root):
        im = Image.open(path).convert("RGB")
        if hashlib.sha256(im.tobytes()).hexdigest() != entry["source"]:
            raise ValueError("validation source changed")
        arr = (
            np.asarray(
                im.resize((960, 960), Image.Resampling.BILINEAR), np.float32
            ).transpose(2, 0, 1)[None]
            / 255
        )
        raw = dict(
            zip(
                spec["outputs"],
                session.run(spec["outputs"], {"images": np.ascontiguousarray(arr)}),
                strict=True,
            )
        )
        adapted = detections(raw, dict(spec, original_bus=False))
        fixed = [d for d in adapted if d["class_id"] != 5]
        evidence = bus_evidence(raw)
        for policy, count in zip(policies, counts, strict=True):
            pred = (
                adapted
                if policy["source"] == "adapted"
                else fixed + select_buses(evidence, policy)
            )
            values = measure(pred, label["objects"], label["excluded"])[0]
            count[entry["site"]] += np.array(
                [
                    [sum(v[k] for v in values.values()) for k in ("tp", "fp", "fn")],
                    [values["5"][k] for k in ("tp", "fp", "fn")],
                ]
            )
    history = []
    for policy, count in zip(policies, counts, strict=True):
        groups = {}
        for site, arr in count.items():
            m = {}
            for key, (tp, fp, fn) in zip(("micro", "bus"), arr.tolist(), strict=True):
                m[key] = dict(
                    tp=tp, fp=fp, fn=fn, p=tp / max(1, tp + fp), r=tp / max(1, tp + fn)
                )
            groups[site] = m
        history.append(dict(policy=policy, groups=groups))
    valid = [
        v
        for v in history
        if all(
            g["micro"]["p"] >= 0.85 and g["micro"]["r"] >= 0.80
            for g in v["groups"].values()
        )
    ]
    if not valid:
        raise RuntimeError("no validation-qualified configuration")
    selected = max(
        valid,
        key=lambda v: tuple(
            min(g[k][m] for g in v["groups"].values())
            for k, m in (("bus", "r"), ("bus", "p"), ("micro", "r"))
        ),
    )
    write(
        out / "selection.json",
        dict(selected=selected, history=history, admissible=len(valid)),
    )
    # Graph bytes stay fixed across the postprocessing-only comparison.
    graph = bundle / "parking-dfine-960.onnx"
    (out / graph.name).hardlink_to(graph)
    write(
        out / "manifest.json",
        dict(
            spec,
            bus_policy=selected["policy"],
            selection_sha256=digest(out / "selection.json"),
        ),
    )
    print(selected, flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    p.add_argument("bundle", type=Path)
    p.add_argument("out", type=Path)
    p.add_argument("--truck-veto", action="store_true")
    a = p.parse_args()
    run(a.root, a.bundle, a.out, a.truck_veto)

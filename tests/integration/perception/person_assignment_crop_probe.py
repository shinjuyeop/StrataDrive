"""Training-only paired-view probe of native RGB detail around a detected two-wheeler."""

import argparse
from collections import Counter, defaultdict
import hashlib
from pathlib import Path

import numpy as np
from PIL import Image

from parking_onnx_replay import load_session
from person_pair_errors import false_positives
from person_pair_candidate import BUNDLE, MODEL, dump, frames
from person_assignment_candidate import CACHE
from physical_ai.perception.parking_candidate import detections
from quality_benchmark_v3 import measure


def run(output):
    session, spec = load_session(BUNDLE)
    if spec["model_sha256"] != MODEL:
        raise ValueError("model identity")

    def detect(image):
        tensor = np.ascontiguousarray(
            np.asarray(
                image.resize((960, 960), Image.Resampling.BILINEAR), np.float32
            ).transpose(2, 0, 1)[None]
            / 255
        )
        raw = dict(
            zip(
                spec["outputs"],
                session.run(spec["outputs"], {"images": tensor}),
                strict=True,
            )
        )
        return detections(raw, spec)

    groups = defaultdict(lambda: defaultdict(Counter))
    anchors = Counter()
    errors = defaultdict(Counter)
    for path, truth, sha, meta in frames(CACHE, "train", True):
        with Image.open(path) as im:
            im = im.convert("RGB")
        if im.size != (2560, 1536) or hashlib.sha256(im.tobytes()).hexdigest() != sha:
            raise ValueError("training RGB")
        all_dets = detect(im)
        base = [d for d in all_dets if d["class_id"] == 0]
        pred = base
        anchor = max(
            (d for d in all_dets if d["class_id"] in (1, 3)),
            key=lambda d: d["score"],
            default=None,
        )
        if anchor:
            anchors[meta["role"]] += 1
            box = np.asarray(anchor["box"]) * 4
            x, y = (
                np.rint((box[:2] + box[2:]) / 2 - [480, 288])
                .clip([0, 0], [1600, 960])
                .astype(int)
            )
            crop = im.crop((x, y, x + 960, y + 576))
            pred = [
                d
                for d in base
                if not (
                    x <= (d["box"][0] + d["box"][2]) * 2 < x + 960
                    and y <= (d["box"][1] + d["box"][3]) * 2 < y + 576
                )
            ]
            for det in detect(crop):
                if det["class_id"] == 0:
                    mapped = (np.asarray(det["box"]) * 1.5 + [x, y, x, y]) / 4
                    pred.append(dict(det, box=mapped.tolist()))
        gt = [o for o in truth["objects"] if o["class_id"] == 0]
        for name, rows in (("full", base), ("zoom", pred)):
            counts, used, *_ = measure(rows, gt, truth["excluded"])
            for _, reason in false_positives(rows, truth):
                errors[name][reason] += 1
            for key in ("all", meta["role"]):
                c = groups[key][name]
                c.update(counts["0"])
                c["frames"] += 1
                for i, o in enumerate(gt):
                    kind = {(12,): "pedestrian", (13,): "rider"}[
                        tuple(o["semantic_tags"])
                    ]
                    c[kind + ("_tp" if i in used else "_fn")] += 1
                if meta["role"] == "cycle" and {
                    tuple(o["semantic_tags"]) for o in gt
                } == {(12,), (13,)}:
                    c["both_eligible"] += 1
                    c["both_matched"] += int(len(used) == len(gt))
    dump(
        output,
        dict(
            split="pairs-train",
            parent=MODEL,
            triggered=anchors,
            false_positives=errors,
            groups=groups,
        ),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("output", type=Path)
    run(p.parse_args().output)

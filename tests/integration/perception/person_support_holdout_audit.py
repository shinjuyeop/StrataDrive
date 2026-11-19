"""Verify retained detections and independently replay every class and stratum gate."""

import argparse
from collections import Counter
from pathlib import Path

from fresh_quality_2k_review import read, digest
from fresh_quality_2k_score import PROTOCOL
from person_support_replay import choose
from quality_benchmark import relative
from quality_benchmark_v3 import measure
from run_resolution_v2 import quality


def audit(out, run):
    got = read(out / (run.name + "-score.json"))
    minimum = read(out / "selection.json")["minimum"]
    counts = Counter()
    rows = []
    preds = out / (run.name + "-detections.json")
    for source, pred, gt, scene in zip(
        read(run / "images.json")["frames"],
        read(preds),
        read(run / "evaluation-only-gt.json")["frames"],
        read(run / "benchmark.json")["scenes"],
        strict=True,
    ):
        if (
            source["rgb_sha256"] != pred["rgb"]
            or not source["scene"] == gt["scene"] == scene["scene"]
        ):
            raise ValueError("scene association")
        people, zoom, flags = choose(pred["full"], pred["zoom"], minimum)
        if (
            people != [d for d in pred["detections"] if d["class_id"] == 0]
            or flags != pred["flags"]
            or bool(pred["bounds"] and zoom) != pred["use_zoom"]
        ):
            raise ValueError("stored decisions do not reproduce")
        objects = [o for o in gt["objects"] if o["class_id"] == 0]
        _, matched, *_ = measure(people, objects, gt["excluded"])
        for i, obj in enumerate(objects):
            tag = {(12,): "walker", (13,): "rider"}[tuple(obj["semantic_tags"])]
            counts[tag + "_total"] += 1
            counts[tag + "_matched"] += int(i in matched)
        rows.append((scene, gt, pred["detections"], True, False, None))
    card = {k: v for k, v in quality(rows).items() if k != "records"}
    rel = relative(read(run / "baseline/score.json"), card, read(PROTOCOL))
    if (
        card != got["card"]
        or rel != got["relative"]
        or got["passed"]
        != (card["absolute_quality"] == "PASS" and rel["status"] == "PASS")
        or len(rows) != 81
    ):
        raise ValueError("stored six-class result does not reproduce")
    return dict(
        frames=len(rows),
        masks=counts,
        quality=got["passed"],
        files={
            p.name: digest(p)
            for p in (
                preds,
                run / "visibility.json",
                run / "images.json",
                run / "evaluation-only-gt.json",
                run / "server.json",
            )
        },
    )


if __name__ == "__main__":
    import json

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("work", type=Path)
    p.add_argument("run", type=Path)
    a = p.parse_args()
    print(json.dumps(audit(a.work, a.run), indent=2))

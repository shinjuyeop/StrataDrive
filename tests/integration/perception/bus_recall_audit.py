"""Replay the frozen predecessor on reported misses, or independently audit a new result."""

import argparse
from pathlib import Path
import hashlib
from PIL import Image
from bus_recall import forward, proposals
from bus_recall_fit import recover, iou
from fresh_quality_2k_review import ROOT, read, rgb_bytes, write
from physical_ai.perception.camera_resolution_v1 import unpack
from physical_ai.perception.parking_candidate import detections
from parking_onnx_replay import load_session
from person_proposal_diagnosis import BUNDLE
from quality_benchmark import relative
from fresh_quality_2k_score import PROTOCOL
from run_resolution_v2 import quality
from person_additive import combine


def predecessor():
    run = ROOT / "build/m10-person-support-v1/holdout/runs/evaluation-holdout-01"
    misses = read(
        ROOT / "docs/test-plan/evidence/m10_person_additive_v2/bus-misses.json"
    )["missed"]
    frames = {f["scene"]: f for f in read(run / "images.json")["frames"]}
    sess, spec = load_session(BUNDLE)
    results = []
    for row in misses:
        f = frames[row["scene"]]
        rgb = rgb_bytes(unpack(run / "dataset", f["rgb_raw"], 2560, 1536))
        if hashlib.sha256(rgb).hexdigest() != f["rgb_sha256"]:
            raise ValueError("RGB mismatch")
        raw = forward(Image.frombytes("RGB", (2560, 1536), rgb), sess, spec)
        if any(d["class_id"] == 5 for d in detections(raw, spec)):
            raise ValueError("predecessor miss changed")
        matches = [p for p in proposals(raw) if iou(p["box"], row["box"]) >= 0.5]
        best = {
            k: max(
                (p for p in matches if p["source"] == k),
                key=lambda p: p["score"],
                default=None,
            )
            for k in ("original_", "adapted")
        }
        results.append(
            dict(scene=f["scene"], stratum=row["stratum"], best_matched=best)
        )
    return results


def review(work):
    run = work / "holdout/runs/evaluation-holdout-01"
    config = read(work / "selection.json")["policy"]
    pc = read(
        ROOT / "docs/test-plan/evidence/m10_person_additive_v2/additive-selection.json"
    )["config"]
    scored = read(work / (run.name + "-score.json"))
    parent_rows = []
    rows = []
    for f, p, g, s in zip(
        read(run / "images.json")["frames"],
        read(work / (run.name + "-detections.json")),
        read(run / "evaluation-only-gt.json")["frames"],
        read(run / "benchmark.json")["scenes"],
        strict=True,
    ):
        if (
            not f["rgb_sha256"] == p["rgb"]
            or not f["scene"] == s["scene"] == g["scene"]
        ):
            raise ValueError("frame identity")
        buses = recover(p["bus_full"], p["bus_observations"], config)
        people = combine(p["full"], p["zoom"], pc)
        if buses != [d for d in p["detections"] if d["class_id"] == 5] or people != [
            d for d in p["detections"] if d["class_id"] == 0
        ]:
            raise ValueError("decision mismatch")
        rows.append((s, g, p["detections"], True, False, None))
        parent_rows.append(
            (
                s,
                g,
                [d for d in p["detections"] if d["class_id"] != 5] + p["bus_full"],
                True,
                False,
                None,
            )
        )
    card = {k: v for k, v in quality(rows).items() if k != "records"}
    before = quality(parent_rows)
    rel = relative(read(run / "baseline/score.json"), card, read(PROTOCOL))
    if (
        len(rows) != 81
        or card != scored["card"]
        or rel != scored["relative"]
        or scored["passed"]
        != (card["absolute_quality"] == "PASS" and rel["status"] == "PASS")
    ):
        raise ValueError("quality replay mismatch")
    return dict(
        frames=len(rows),
        passed=scored["passed"],
        parent_bus=before["per_class"]["5"],
        candidate_bus=card["per_class"]["5"],
        micro=card["micro"],
        absolute=card["gates"],
        relative=rel,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("work", type=Path)
    p.add_argument("action", choices=("predecessor", "review"))
    a = p.parse_args()
    write(
        a.work / (a.action + ".json"),
        predecessor() if a.action == "predecessor" else review(a.work),
    )

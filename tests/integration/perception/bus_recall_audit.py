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


def paired(work):
    """Run the previous detector on exactly the same evaluation pixels."""
    from person_support_replay import six_class
    from person_additive_transfer import infer_additive
    from bus_recall_fit import PERSON
    from quality_benchmark_v3 import measure

    run = work / "holdout/runs/evaluation-holdout-01"
    parent = work / "parent-replay"
    parent.mkdir(exist_ok=True)
    six_class(parent, run, read(PERSON)["config"], detector=infer_additive)
    name = run.name + "-detections.json"
    original = read(parent / name)
    fixed = read(work / name)
    changes = dict(frames=0, new_bus_tp=0, new_bus_fp=0)
    for old, new, truth in zip(
        original, fixed, read(run / "evaluation-only-gt.json")["frames"], strict=True
    ):
        if old["rgb"] != new["rgb"]:
            raise ValueError("parent replay RGB")
        old_bus = [d for d in old["detections"] if d["class_id"] == 5]
        other_old = [d for d in old["detections"] if d["class_id"] != 5]
        other_new = [d for d in new["detections"] if d["class_id"] != 5]
        for actual, retained in ((old_bus, new["bus_full"]), (other_old, other_new)):
            for a, b in zip(actual, retained, strict=True):
                if (
                    a["class_id"] != b["class_id"]
                    or abs(a["score"] - b["score"]) >= 0.0001
                    or max(abs(x - y) for x, y in zip(a["box"], b["box"], strict=True))
                    >= 0.02
                ):
                    raise ValueError("original detector output changed")
            if (
                measure(actual, truth["objects"], truth["excluded"])[:2]
                != measure(retained, truth["objects"], truth["excluded"])[:2]
            ):
                raise ValueError("original matches changed")
        before = measure(old["detections"], truth["objects"], truth["excluded"])[0]["5"]
        after = measure(new["detections"], truth["objects"], truth["excluded"])[0]["5"]
        changes["new_bus_tp"] += after["tp"] - before["tp"]
        changes["new_bus_fp"] += after["fp"] - before["fp"]
        changes["frames"] += 1
    if changes["frames"] != 81:
        raise ValueError("parent denominator")
    return dict(
        counts=changes,
        frame_level_nonbus_matches_identical=True,
        original_bus=read(parent / (run.name + "-score.json"))["card"]["per_class"][
            "5"
        ],
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("work", type=Path)
    p.add_argument("action", choices=("predecessor", "review", "paired"))
    a = p.parse_args()
    write(
        a.work / (a.action + ".json"),
        predecessor()
        if a.action == "predecessor"
        else {"review": review, "paired": paired}[a.action](a.work),
    )

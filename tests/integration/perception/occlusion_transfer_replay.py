"""Recheck selected outputs and bound one-to-one recall on the existing development frames."""

import argparse
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.sparse.csgraph import maximum_bipartite_matching
from scipy.sparse import csr_matrix

from fresh_quality_2k_plan import digest, read
from fresh_quality_2k_review import BASE, write
from physical_ai.perception.class_calibration_v1 import decode as decode_grid
from physical_ai.perception.resolution_car_v1 import decode
from quality_benchmark_v3 import measure
from run_resolution_v2 import quality


def bound(coordinates, confidence, objects, floor):
    if not objects:
        return 0
    gt = np.array([o["box"] for o in objects])
    inter = np.maximum(
        0,
        np.minimum(coordinates[:, None, 2:], gt[:, 2:])
        - np.maximum(coordinates[:, None, :2], gt[:, :2]),
    ).prod(axis=2)
    union = (
        (coordinates[:, 2:] - coordinates[:, :2]).prod(axis=1)[:, None]
        + (gt[:, 2:] - gt[:, :2]).prod(axis=1)
        - inter
    )
    allowed = (inter >= 0.5 * union) & (
        confidence[:, [o["class_id"] for o in objects]] >= floor
    )
    return int(
        (maximum_bipartite_matching(csr_matrix(allowed), perm_type="column") >= 0).sum()
    )


def replay(out):
    predictions = read(out / "development-predictions.json")
    run = BASE / "runs/evaluation-development-01"
    scenes = read(run / "benchmark.json")["scenes"]
    truth = read(run / "evaluation-only-gt.json")["frames"]
    if not len(scenes) == len(truth) == len(predictions) == 81:
        raise ValueError("development denominator")
    observations = []
    counts = Counter()
    for i, (scene, gt, row) in enumerate(zip(scenes, truth, predictions)):
        path = out / "queries" / f"{i:03d}.npz"
        if (
            digest(path) != row["queries_sha256"]
            or not scene["scene"] == gt["scene"] == row["scene"]
        ):
            raise ValueError("query provenance")
        with np.load(path, allow_pickle=False) as data:
            raw = {k: data[k] for k in ("labels", "boxes", "scores")}
            boxes, confidence = data["coordinates"], data["confidence"]
        for key, decoded in (
            ("current", decode(raw)),
            ("lowest_allowed", decode_grid(raw, (0.35,) * 6)),
        ):
            pred = [
                dict(class_id=d.class_id, score=d.score, box=list(d.box))
                for d in decoded
            ]
            if key == "current":
                if pred != row["detections"]:
                    raise ValueError("numerical replay mismatch")
                observations.append((scene, gt, pred, True, False, None))
            card = measure(pred, gt["objects"], gt["excluded"])[0]
            counts[key] += sum(v["tp"] for v in card.values())
        counts["objects"] += len(gt["objects"])
        counts["distinct_query_matches_at_floor"] += bound(
            boxes, confidence, gt["objects"], 0.35
        )
        counts["distinct_query_matches_ignoring_confidence"] += bound(
            boxes, confidence, gt["objects"], 0
        )
    card = quality(observations)
    expected = read(out / "development-score.json")
    if any(card[k] != v for k, v in expected.items()):
        raise ValueError("development quality replay mismatch")
    write(
        out / "query-replay.json",
        dict(
            status="PASS_REPLAY",
            frames=len(predictions),
            counts=dict(counts),
            scope="The two one-to-one upper bounds use all decoder queries and the true labels for diagnosis, including queries omitted from published detections.",
        ),
    )
    print(counts)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("output", type=Path)
    replay(p.parse_args().output)

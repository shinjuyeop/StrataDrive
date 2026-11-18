"""Audit original holdout packets, dataset separation and person recall by semantic tag."""

from collections import Counter
import hashlib
import json

from camera_resolution_v1_common import annotate
from fresh_quality_2k_review import BASE, ROOT, digest, read, rgb_bytes
from physical_ai.perception.camera_resolution_v1 import unpack
from quality_benchmark_v3 import measure


def audit():
    run = BASE / "runs/evaluation-holdout-01"
    result_dir = ROOT / "docs/test-plan/evidence/m10_parking_holdout_v1"
    manifest = ROOT / "build/m10-parking-verifier-v1/cache/manifest.json"
    cache = read(manifest)
    previous = {r["source"] for entries in cache.values() for r in entries}
    capture = read(run / "dataset/capture.json")
    frames = read(run / "images.json")["frames"]
    labels = read(run / "evaluation-only-gt.json")["frames"]
    preds = read(run / "parking-candidate/predictions.json")["rows"]
    scenes = read(run / "benchmark.json")["scenes"]
    seen = set()
    counts = Counter()
    for packet, frame, gt, pred, scene in zip(
        capture["frames"], frames, labels, preds, scenes, strict=True
    ):
        if len({row["scene"] for row in (packet, frame, gt, pred, scene)}) != 1:
            raise ValueError("frame association")
        pixel = hashlib.sha256(
            rgb_bytes(unpack(run / "dataset", packet["rgb"], 2560, 1536))
        ).hexdigest()
        if (
            pixel in previous
            or pixel in seen
            or pixel != frame["rgb_sha256"]
            or pixel != pred["rgb_sha256"]
        ):
            raise ValueError("RGB independence or identity")
        seen.add(pixel)
        raw = unpack(run / "dataset", packet["instance"], 2560, 1536)
        if annotate(raw, 2560, 1536) != (gt["objects"], gt["excluded"]):
            raise ValueError("mask annotation replay")
        _, matched, *_ = measure(pred["detections"], gt["objects"], gt["excluded"])
        for i, obj in enumerate(gt["objects"]):
            if obj["class_id"] == 0:
                counts[tuple(obj["semantic_tags"]), scene["stratum"], i in matched] += 1
    assert len(seen) == 81
    persons = []
    for tag, kind in ((12, "pedestrian"), (13, "rider")):
        for stratum in sorted({s for tags, s, ok in counts if tags == (tag,)}):
            tp = counts[(tag,), stratum, True]
            fn = counts[(tag,), stratum, False]
            persons.append(dict(semantic=kind, stratum=stratum, detected=tp, missed=fn))
    c = read(run / "parking-candidate/score.json")["per_class"]["0"]
    if (sum(r["detected"] for r in persons), sum(r["missed"] for r in persons)) != (
        c["tp"],
        c["fn"],
    ):
        raise ValueError("person denominator")
    return dict(
        frames=len(seen),
        nonduplicate_rgb=len(seen),
        mask_labels_reproduced=len(seen),
        training_validation_excluded=len(previous),
        training_manifest_sha256=digest(manifest),
        within_holdout_or_training_matches=0,
        person_by_stratum=persons,
        recorded_result_sha256=digest(result_dir / "result.json"),
    )


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))

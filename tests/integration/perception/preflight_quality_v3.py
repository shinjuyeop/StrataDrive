#!/usr/bin/env python3
"""Model-free raw asset/pose/visibility acceptance on a separate preparation set."""

import argparse
from datetime import datetime, timezone
from pathlib import Path
from quality_v3_common import PREPARATION_PLAN, validate_plan, write_new, require
from physical_ai.perception.dataset import read_json
from physical_ai.perception.contract import sha256_file
from prepare_quality_v3 import prepare


def assess(capture, output):
    plan = read_json(PREPARATION_PLAN)
    validate_plan(plan)
    prepare(capture, output)
    gt = read_json(output / "evaluation-only-gt.json")["frames"]
    meta = read_json(output / "benchmark.json")["scenes"]
    manifest = read_json(output / "rgb.json")
    missing, targets, rows = 0, [], []
    for case, m, truth in zip(plan["partitions"]["preparation"]["cases"], meta, gt):
        require(case["id"] == m["scene"] == truth["scene"], "preparation lineage")
        for planned, actor in zip(case["actors"], m["actors"]):
            key = (actor["class_id"], actor["actor_id"] % 65536)
            matched = [
                g for g in truth["objects"] if (g["class_id"], g["instance_id"]) == key
            ]
            missing += int(len(matched) != 1)
            rows.append(
                dict(
                    scene=case["id"],
                    blueprint=actor["blueprint"],
                    role=actor["role"],
                    included=len(matched) == 1,
                    support=matched[0] if matched else None,
                )
            )
            if actor["role"] == "target":
                targets.append(
                    dict(
                        weather=case["weather"], stratum=case["stratum"], actor=planned
                    )
                )
    supports = {
        (r["scene"], r["blueprint"]): r["support"]["visible_pixels"]
        for r in rows
        if r["included"] and r["role"] == "target"
    }
    occlusions = []
    for reference in plan["partitions"]["preparation"]["cases"]:
        if "reference_for" not in reference:
            continue
        for actor in reference["actors"]:
            a = supports.get((reference["reference_for"], actor["blueprint"]), 0)
            b = supports.get((reference["id"], actor["blueprint"]), 0)
            ratio = a / b if b else None
            occlusions.append(
                dict(
                    scene=reference["reference_for"],
                    reference=reference["id"],
                    visible_pixels=a,
                    unoccluded_pixels=b,
                    visible_ratio=ratio,
                    passed=ratio is not None and 0 < ratio < 0.95,
                )
            )
    failed = sum(not r["passed"] for r in occlusions)
    return dict(
        schema="m10-quality-preparation-v3",
        status="PASS" if missing == 0 and failed == 0 else "FAIL",
        completed_utc=datetime.now(timezone.utc).isoformat(),
        plan_sha256=sha256_file(PREPARATION_PLAN),
        capture_sha256=sha256_file(capture),
        rgb_manifest_sha256=sha256_file(output / "rgb.json"),
        frames=len(gt),
        missing_actors=missing,
        occlusion_failures=failed,
        occlusion_checks=occlusions,
        inference_performed=False,
        planned_targets=targets,
        actors=rows,
        rgb_sha256=[r["rgb_sha256"] for r in manifest["frames"]],
        scope="Separate camera spawn4; static asset spawn/settled pose/visible support only",
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("capture", type=Path)
    p.add_argument("prepared", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    result = assess(a.capture, a.prepared)
    write_new(a.output, result)
    print({k: result[k] for k in ("status", "frames", "missing_actors")})
    raise SystemExit(0 if result["status"] == "PASS" else 1)

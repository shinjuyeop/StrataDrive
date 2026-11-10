#!/usr/bin/env python3
"""Raw support diagnostic on the retained failed V9 held preparation, never a seal."""

import argparse
import hashlib
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import read_json, local_path
from quality_annotation import visible_boxes_v2
from quality_geometry_v4 import check_pose
from quality_staging_v5 import staging_pose
from quality_road_v9 import validate_plan
from prepare_road_v9 import assess_frames
from quality_benchmark import require, write_new


def diagnose(run, plan_path):
    server, cap, plan = (
        read_json(run / "server.json"),
        read_json(run / "dataset/capture.json"),
        read_json(plan_path),
    )
    validate_plan(plan)
    require(
        server["schema"] == "m10-road-server-v9"
        and server["status"] == "FAIL"
        and server["server_exit"] == -9
        and server.get("forced_stop")
        and server["capture_exit"] == 0
        and cap["schema"] == "m10-road-capture-v9"
        and cap["phase"] == "preparation"
        and cap["partition"] == "holdout"
        and cap["plan_sha256"] == sha256_file(plan_path),
        "only retained failed V9 held preparation diagnostic",
    )
    settings = plan["partitions"]["holdout"]
    require(
        len(cap["frames"]) == len(cap["scenes"]) == len(settings["cases"]) == 99,
        "failed attempt full denominator",
    )
    check_pose(cap["camera_pose"], settings["camera_pose"])
    truth, hashes = [], []
    for case, scene, pair in zip(settings["cases"], cap["scenes"], cap["frames"]):
        require(case["id"] == scene["id"] == pair["scene"], "failed raw scene lineage")
        for kind in ("rgb", "instance"):
            require(
                sha256_file(local_path(run / "dataset", pair[kind]["path"]))
                == pair[kind]["sha256"],
                "failed raw sensor SHA",
            )
        raw = local_path(run / "dataset", pair["rgb"]["path"]).read_bytes()
        rgb = (
            np.frombuffer(raw, np.uint8)
            .reshape(384, 640, 4)[:, :, 2::-1]
            .copy()
            .tobytes()
        )
        hashes.append(hashlib.sha256(rgb).hexdigest())
        objects, excluded = visible_boxes_v2(
            local_path(run / "dataset", pair["instance"]["path"]).read_bytes()
        )
        truth.append(
            dict(
                scene=pair["scene"],
                frame=pair["frame"],
                objects=objects,
                excluded=excluded,
            )
        )
        for n, (planned, actual) in enumerate(zip(case["actors"], scene["actors"])):
            check_pose(actual["pose"], planned["pose"])
            check_pose(
                actual["staging_requested_pose"], staging_pose(planned["pose"], n)
            )
    return dict(
        schema="m10-v9-failed-preparation-diagnostic-v1",
        status="PASS",
        accepted=False,
        server_status="FAIL",
        server_sha256=sha256_file(run / "server.json"),
        capture_sha256=sha256_file(run / "dataset/capture.json"),
        plan_sha256=sha256_file(plan_path),
        helper_sha256=sha256_file(Path(__file__)),
        frames=99,
        rgb_sha256=hashes,
        support=assess_frames(
            settings["cases"],
            [dict(row, scene=row["id"]) for row in cap["scenes"]],
            truth,
        ),
        inference_performed=False,
        scope="Raw support diagnostic only; original failed shutdown is never accepted",
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run", type=Path)
    p.add_argument("plan", type=Path)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    result = diagnose(args.run, args.plan)
    write_new(args.output, result)
    print(
        result["status"],
        "original server FAIL; accepted=False",
        result["support"]["status"],
    )

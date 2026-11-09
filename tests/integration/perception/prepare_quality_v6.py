#!/usr/bin/env python3
"""Rebuild frozen evaluation RGB/GT and actual road geometry; never runs models."""

import argparse
import math
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import read_json, local_path, RgbDataset
from quality_annotation import visible_boxes_v2
from quality_geometry_v4 import check_pose
from quality_staging_v5 import staging_pose
from quality_road_v6 import validate_plan
from quality_benchmark_v3 import validate_truth
from quality_v6_common import (
    PLAN,
    EXCLUSION,
    check_freeze,
    check_selection,
    require,
    write_new,
)


def assess_visibility(cases, scenes, truth):
    require(
        len(cases) == len(scenes) == len(truth) == 81,
        "evaluation visibility denominator",
    )
    missing, riders = [], []
    for case, scene, gt in zip(cases, scenes, truth):
        require(case["id"] == scene["scene"] == gt["scene"], "visibility scene order")
        require(
            len(case["actors"]) == len(scene["actors"]), "visibility actor denominator"
        )
        validate_truth(gt)
        included = {(o["class_id"], o["instance_id"]): o for o in gt["objects"]}
        for actual in scene["actors"]:
            key = (actual["class_id"], actual["actor_id"] % 65536)
            require(actual["included"] == (key in included), "actor inclusion binding")
            if key not in included:
                missing.append(dict(scene=case["id"], actor_id=actual["actor_id"]))
            if actual["class_id"] in (1, 3):
                rider = included.get((0, key[1]))
                if rider is None or 13 not in rider["semantic_tags"]:
                    riders.append(dict(scene=case["id"], actor_id=actual["actor_id"]))
    gates = dict(
        all_planned_actors_visible=not missing,
        all_two_wheeler_riders_visible=not riders,
    )
    return dict(
        status="PASS" if all(gates.values()) else "FAIL",
        gates=gates,
        missing_actors=missing,
        missing_riders=riders,
    )


def prepare(capture_path, output, frozen_path):
    frozen = check_freeze(frozen_path)
    plan_path, exclusion_path = PLAN, EXCLUSION
    cap, plan, server = (
        read_json(capture_path),
        read_json(plan_path),
        read_json(capture_path.parent.parent / "server.json"),
    )
    validate_plan(plan)
    part = cap["partition"]
    settings = plan["partitions"][part]
    cases = settings["cases"]
    require(
        cap["schema"] == "m10-road-evaluation-capture-v6"
        and cap["phase"] == "evaluation"
        and cap["status"] == server["status"] == "PASS"
        and server["schema"] == "m10-quality-server-v6"
        and server["stage"] == "evaluation"
        and server["server_exit"] == 130
        and server["capture_exit"] == 0
        and not server.get("forced_stop")
        and not cap["overflow"]
        and not cap["cleanup_errors"]
        and cap["plan_sha256"] == server["plan_sha256"] == sha256_file(plan_path)
        and cap["survey_sha256"] == plan["survey_sha256"]
        and cap["xodr_sha256"] == plan["xodr_sha256"]
        and len(cap["frames"]) == len(cap["scenes"]) == len(cases) == 81,
        "complete preparation capture/identity",
    )
    require(
        server["freeze_sha256"] == sha256_file(frozen_path)
        and server["protocol_sha256"] == frozen["protocol_sha256"],
        "capture freeze binding",
    )
    selection_sha = server["selection_sha256"]
    if part == "holdout":
        selection_path = capture_path.parent.parent / "candidate-selection.json"
        check_selection(selection_path, frozen_path)
        require(
            selection_sha == sha256_file(selection_path), "pre-acquisition nomination"
        )
    else:
        require(selection_sha is None, "no development nomination")
    check_pose(cap["camera_pose"], settings["camera_pose"])
    output.mkdir(parents=True, exist_ok=False)
    (output / "rgb").mkdir()
    manifest = dict(
        schema="m10-rgb-dataset-v1",
        split="evaluation",
        capture_sha256=sha256_file(capture_path),
        epoch=cap["epoch"],
        clock_instance=cap["clock_instance"],
        camera=dict(
            width=640, height=384, camera_id=1, calibration_revision=1, format="RGB8"
        ),
        frames=[],
    )
    truth = dict(
        schema="m10-rider-visible-gt-v2",
        partition=part,
        capture_sha256=manifest["capture_sha256"],
        frames=[],
    )
    metadata = dict(
        schema="m10-quality-dataset-v6",
        phase="evaluation",
        partition=part,
        site=settings["spawn_point_index"],
        plan_sha256=sha256_file(plan_path),
        capture_sha256=sha256_file(capture_path),
        exclusion_sha256=sha256_file(exclusion_path),
        protocol_sha256=frozen["protocol_sha256"],
        selection_sha256=selection_sha,
        scenes=[],
    )
    prior = set(read_json(exclusion_path)["rgb_sha256"])
    for case, scene, source in zip(cases, cap["scenes"], cap["frames"]):
        require(
            case["id"] == scene["id"] == source["scene"]
            and scene["frame"] == source["frame"]
            and all(case[k] == scene[k] for k in ("weather", "stratum", "target_class"))
            and len(case["actors"]) == len(scene["actors"]),
            "raw scene identity",
        )
        raw = {}
        for stream in ("rgb", "instance"):
            p = local_path(capture_path.parent, source[stream]["path"])
            require(
                p.stat().st_size == 640 * 384 * 4
                and sha256_file(p) == source[stream]["sha256"],
                "paired raw hash/layout",
            )
            raw[stream] = p.read_bytes()
        image = np.frombuffer(raw["rgb"], np.uint8).reshape(384, 640, 4)
        path = f"rgb/{source['frame']:08d}.rgb"
        (output / path).write_bytes(image[:, :, [2, 1, 0]].copy().tobytes())
        digest = sha256_file(output / path)
        require(digest not in prior, "prior preparation/evaluation RGB reused")
        manifest["frames"].append(
            dict(
                scene=case["id"],
                frame=source["frame"],
                source_ns=source["source_ns"],
                rgb_path=path,
                rgb_sha256=digest,
            )
        )
        objects, excluded = visible_boxes_v2(raw["instance"])
        truth["frames"].append(
            dict(
                scene=case["id"],
                frame=source["frame"],
                objects=objects,
                excluded=excluded,
            )
        )
        require(
            len({a["actor_id"] % 65536 for a in scene["actors"]})
            == len(scene["actors"]),
            "aliased actor instances",
        )
        actors = []
        for index, (wanted, actual) in enumerate(zip(case["actors"], scene["actors"])):
            require(
                all(wanted[k] == actual[k] for k in ("class_id", "blueprint", "role")),
                "actor lineage",
            )
            require(
                actual["staging_requested_pose"] == staging_pose(wanted["pose"], index),
                "transient spawn request lineage",
            )
            check_pose(actual["pose"], wanted["pose"])
            readback = actual["road_readback"]
            lane = readback["nearest_lane_pose"]["location"]
            loc = wanted["pose"]["location"]
            projection = math.hypot(loc["x"] - lane["x"], loc["y"] - lane["y"])
            clearance = loc["z"] - lane["z"] - wanted["clearance_m"]
            require(
                abs(projection - readback["projection_m"]) < 1e-6
                and abs(clearance - readback["clearance_error_m"]) < 1e-6
                and projection <= 2
                and abs(clearance) <= 0.15
                and readback["road_id"] == wanted["road_node"]["road_id"]
                and readback["lane_id"] == wanted["road_node"]["lane_id"],
                "actual-site road readback",
            )
            key = (actual["class_id"], actual["actor_id"] % 65536)
            actual = dict(
                actual,
                included=any((o["class_id"], o["instance_id"]) == key for o in objects),
                excluded_small=any(
                    (o["class_id"], o["instance_id"]) == key for o in excluded
                ),
            )
            actors.append(actual)
        metadata["scenes"].append(
            dict(
                scene=case["id"],
                weather=case["weather"],
                stratum=case["stratum"],
                target_class=case["target_class"],
                actors=actors,
            )
        )
    write_new(output / "rgb.json", manifest)
    list(RgbDataset(output / "rgb.json").frames())
    truth["rgb_manifest_sha256"] = sha256_file(output / "rgb.json")
    write_new(output / "evaluation-only-gt.json", truth)
    metadata.update(
        rgb_manifest_sha256=sha256_file(output / "rgb.json"),
        truth_sha256=sha256_file(output / "evaluation-only-gt.json"),
    )
    write_new(output / "benchmark.json", metadata)
    result = assess_visibility(cases, metadata["scenes"], truth["frames"])
    result.update(
        schema="m10-quality-visibility-v6",
        partition=part,
        frames=81,
        site=settings["spawn_point_index"],
    )
    write_new(output / "visibility.json", result)
    seal = {
        k: metadata[k]
        for k in (
            "partition",
            "plan_sha256",
            "protocol_sha256",
            "capture_sha256",
            "selection_sha256",
            "rgb_manifest_sha256",
            "truth_sha256",
            "exclusion_sha256",
        )
    }
    seal.update(
        schema="m10-quality-data-seal-v6",
        metadata_sha256=sha256_file(output / "benchmark.json"),
        visibility_sha256=sha256_file(output / "visibility.json"),
    )
    write_new(output / "benchmark-seal.json", seal)
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("capture", "output", "freeze"):
        p.add_argument(name, type=Path)
    a = p.parse_args()
    print(prepare(a.capture, a.output, a.freeze))

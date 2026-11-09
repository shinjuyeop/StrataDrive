#!/usr/bin/env python3
"""Rebuild road-preparation RGB/visible labels and assess every actual camera site."""

import argparse
from datetime import datetime, timezone
import math
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import read_json, local_path, RgbDataset
from quality_annotation import visible_boxes_v2
from quality_benchmark import require, write_new
from quality_geometry_v4 import check_pose
from quality_plan_v4 import validate_plan
from quality_benchmark_v2 import validate_truth


def assess_frames(cases, scenes, truth):
    """Gate only predeclared visibility/geometry; model predictions are never read."""
    require(len(cases) == len(scenes) == len(truth) == 99, "preparation denominator")
    missing = []
    riders = []
    coverage = {
        str(c): {s: 0 for s in ("near", "medium", "far", "occluded")}
        for c in (0, 1, 2, 3, 5, 7)
    }
    primary = {}
    support_rows = []
    for case, scene, gt in zip(cases, scenes, truth):
        require(case["id"] == scene["scene"] == gt["scene"], "preparation scene order")
        require(
            len(case["actors"]) == len(scene["actors"]), "preparation actor denominator"
        )
        validate_truth(gt)
        included = {(o["class_id"], o["instance_id"]): o for o in gt["objects"]}
        for index, (planned, actual) in enumerate(zip(case["actors"], scene["actors"])):
            key = (actual["class_id"], actual["actor_id"] % 65536)
            obj = included.get(key)
            if obj is None:
                missing.append(
                    dict(
                        scene=case["id"],
                        actor_index=index,
                        blueprint=actual["blueprint"],
                        role=actual["role"],
                    )
                )
            if actual["class_id"] in (1, 3):
                rider = included.get((0, key[1]))
                if rider is None or 13 not in rider["semantic_tags"]:
                    riders.append(
                        dict(
                            scene=case["id"],
                            actor_index=index,
                            blueprint=actual["blueprint"],
                        )
                    )
            if (
                planned["role"] == "target"
                and planned["class_id"] == case["target_class"]
            ):
                if case["stratum"] in coverage[str(planned["class_id"])]:
                    coverage[str(planned["class_id"])][case["stratum"]] += int(
                        obj is not None
                    )
                require(case["id"] not in primary, "ambiguous primary target")
                primary[case["id"]] = obj
            support_rows.append(
                dict(
                    scene=case["id"],
                    actor_index=index,
                    blueprint=actual["blueprint"],
                    role=actual["role"],
                    support=obj,
                )
            )
    occlusions = []
    for case in cases:
        if "reference_for" not in case:
            continue
        a, b = primary.get(case["reference_for"]), primary.get(case["id"])
        ratio = a["visible_pixels"] / b["visible_pixels"] if a and b else None
        occlusions.append(
            dict(
                scene=case["reference_for"],
                reference=case["id"],
                visible_ratio=ratio,
                passed=ratio is not None and 0 < ratio < 0.95,
            )
        )
    gates = dict(
        all_planned_actors_visible=not missing,
        all_two_wheeler_riders_visible=not riders,
        every_class_stratum=all(
            n == 3 for cls in coverage.values() for n in cls.values()
        ),
        occlusion_references=len(occlusions) == 18
        and all(x["passed"] for x in occlusions),
    )
    return dict(
        status="PASS" if all(gates.values()) else "FAIL",
        gates=gates,
        primary_coverage=coverage,
        missing_actors=missing,
        missing_riders=riders,
        occlusion_checks=occlusions,
        support_rows=support_rows,
    )


def prepare(capture_path, plan_path, exclusion_path, output):
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
        cap["schema"] == "m10-road-capture-v4"
        and cap["phase"] == "preparation"
        and cap["status"] == server["status"] == "PASS"
        and server["schema"] == "m10-road-server-v4"
        and server["stage"] == "preparation"
        and server["server_exit"] == 130
        and server["capture_exit"] == 0
        and not server.get("forced_stop")
        and not cap["overflow"]
        and not cap["cleanup_errors"]
        and cap["plan_sha256"] == server["plan_sha256"] == sha256_file(plan_path)
        and cap["survey_sha256"] == plan["survey_sha256"]
        and cap["xodr_sha256"] == plan["xodr_sha256"]
        and len(cap["frames"]) == len(cap["scenes"]) == len(cases) == 99,
        "complete preparation capture/identity",
    )
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
    truth = dict(schema="m10-rider-visible-gt-v2", partition=part, frames=[])
    metadata = dict(
        schema="m10-road-prepared-data-v4",
        phase="preparation",
        partition=part,
        site=settings["spawn_point_index"],
        plan_sha256=sha256_file(plan_path),
        capture_sha256=sha256_file(capture_path),
        exclusion_sha256=sha256_file(exclusion_path),
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
        require(digest not in prior, "prior RGB reused at new preparation site")
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
        for wanted, actual in zip(case["actors"], scene["actors"]):
            require(
                all(wanted[k] == actual[k] for k in ("class_id", "blueprint", "role")),
                "actor lineage",
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
    write_new(output / "preparation-data.json", metadata)
    result = assess_frames(cases, metadata["scenes"], truth["frames"])
    result.update(
        schema="m10-road-preparation-acceptance-v4",
        completed_utc=datetime.now(timezone.utc).isoformat(),
        phase="preparation",
        partition=part,
        site=settings["spawn_point_index"],
        frames=99,
        inference_performed=False,
        plan_sha256=sha256_file(plan_path),
        capture_sha256=sha256_file(capture_path),
        metadata_sha256=sha256_file(output / "preparation-data.json"),
        rgb_manifest_sha256=sha256_file(output / "rgb.json"),
        truth_sha256=sha256_file(output / "evaluation-only-gt.json"),
        rgb_sha256=[r["rgb_sha256"] for r in manifest["frames"]],
        objects=sum(len(r["objects"]) for r in truth["frames"]),
        excluded=sum(len(r["excluded"]) for r in truth["frames"]),
    )
    write_new(output / "acceptance.json", result)
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("capture", "plan", "exclusion", "output"):
        p.add_argument(name, type=Path)
    a = p.parse_args()
    r = prepare(a.capture, a.plan, a.exclusion, a.output)
    print({k: r[k] for k in ("status", "partition", "site", "frames", "gates")})
    raise SystemExit(0 if r["status"] == "PASS" else 1)

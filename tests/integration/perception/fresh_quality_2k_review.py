"""Verify and label selected original camera pairs without loading a detector."""

import hashlib
import json

import numpy as np
from camera_resolution_v1_common import annotate
from fresh_quality_2k_plan import ROOT, digest, read, validate_retained
from physical_ai.perception.camera_resolution_v1 import NativeFrame, health, unpack
from physical_ai.perception.contract import FrameIdentity
from prepare_road_v9 import assess_frames
from prepare_quality_v9 import assess_visibility
from quality_geometry_v4 import check_pose
from quality_staging_v5 import staging_pose

BASE = ROOT / "docs/test-plan/evidence/m10_fresh_quality_2k_v1"
EXCLUSIONS = (
    ROOT / "docs/test-plan/evidence/m10_quality_v9/future-evaluation-exclusion.json",
    ROOT
    / "docs/test-plan/evidence/m10_cuda_resize_v1/normal-300s-01/future-exclusion.json",
)


def write(path, data):
    with path.open("x") as out:
        json.dump(data, out, indent=2, allow_nan=False)
        out.write("\n")


def previous_images(current):
    hashes = set()
    for path in EXCLUSIONS:
        hashes.update(read(path)["rgb_sha256"])
    for dataset in (BASE / "runs").glob("*/dataset"):
        if dataset.parent == current:
            continue
        reviewed = dataset.parent / "images.json"
        if reviewed.exists():
            hashes.update(row["rgb_sha256"] for row in read(reviewed)["frames"])
        else:
            # Include acquisitions from interrupted/failed captures as well.
            import zlib

            for path in (dataset / "rgb").glob("*.bgra.z"):
                raw = zlib.decompress(path.read_bytes())
                hashes.add(hashlib.sha256(rgb_bytes(raw)).hexdigest())
    return hashes


def rgb_bytes(raw):
    return (
        np.frombuffer(raw, np.uint8)
        .reshape(1536, 2560, 4)[:, :, 2::-1]
        .copy()
        .tobytes()
    )


def review(run):
    validate_retained(BASE / "plan")
    server = read(run / "server.json")
    dataset = run / "dataset"
    capture = read(dataset / "capture.json")
    plan_path = BASE / "plan" / (capture["phase"] + ".json")
    plan = read(plan_path)
    partition = plan["partitions"][capture["partition"]]
    cases = partition["cases"]
    if (
        server["status"] != "PASS_CAPTURE"
        or capture["status"] != "PASS"
        or server["client_exit"] != 0
        or server["shutdown"]["server_exit"] != 130
        or server["shutdown"].get("forced_stop")
        or capture["errors"]
        or capture["cleanup_errors"]
        or capture["overflow"]
        or capture["xodr_sha256"] != plan["xodr_sha256"]
        or capture["plan_sha256"] != digest(plan_path)
        or len(cases) != len(capture["frames"])
        or len(cases) != len(capture["scenes"])
    ):
        raise ValueError(
            "complete clean shutdown, camera capture and planned denominator required"
        )
    prior = previous_images(run)
    frames, truth, scenes, duplicates = [], [], [], []
    for case, row, actual in zip(cases, capture["frames"], capture["scenes"]):
        if not (
            case["id"] == row["scene"] == actual["id"]
            and actual["frame"] == row["frame"]
            and all(
                case[k] == actual[k] for k in ("weather", "stratum", "target_class")
            )
            and len(case["actors"]) == len(actual["actors"])
            and len({a["actor_id"] % 65536 for a in actual["actors"]})
            == len(actual["actors"])
        ):
            raise ValueError("planned exposure and actor identity")
        original = unpack(dataset, row["rgb"], 2560, 1536)
        rgb = rgb_bytes(original)
        image_hash = hashlib.sha256(rgb).hexdigest()
        if image_hash in prior:
            duplicates.append(case["id"])
        frame = NativeFrame(
            FrameIdentity(
                capture["epoch"], capture["world"], row["frame"], row["source_ns"]
            ),
            2560,
            1536,
            rgb,
        )
        health(frame)
        raw_mask = unpack(dataset, row["instance"], 2560, 1536)
        objects, excluded = annotate(raw_mask, 2560, 1536)
        included = {(o["class_id"], o["instance_id"]) for o in objects}
        for n, (wanted, actor) in enumerate(zip(case["actors"], actual["actors"])):
            if any(actor[k] != wanted[k] for k in ("role", "blueprint", "class_id")):
                raise ValueError("actual actor or role changed")
            check_pose(actor["pose"], wanted["pose"])
            check_pose(actor["staging_requested_pose"], staging_pose(wanted["pose"], n))
            road = actor["road_readback"]
            if (
                road["road_id"] != wanted["road_node"]["road_id"]
                or road["lane_id"] != wanted["road_node"]["lane_id"]
                or road["projection_m"] > 2
                or abs(road["clearance_error_m"]) > 0.15
            ):
                raise ValueError("actual surveyed lane")
            actor["included"] = (
                actor["class_id"],
                actor["actor_id"] % 65536,
            ) in included
        frames.append(
            dict(
                scene=case["id"],
                frame=row["frame"],
                source_ns=row["source_ns"],
                rgb_sha256=image_hash,
                rgb_raw=row["rgb"],
            )
        )
        truth.append(
            dict(
                scene=case["id"], frame=row["frame"], objects=objects, excluded=excluded
            )
        )
        scenes.append(
            dict(
                scene=case["id"],
                **{
                    k: actual[k]
                    for k in ("stratum", "target_class", "weather", "actors")
                },
            )
        )
    if any(
        b["frame"] <= a["frame"] or b["source_ns"] <= a["source_ns"]
        for a, b in zip(frames, frames[1:])
    ):
        raise ValueError("sensor frame/time regression")
    write(
        run / "images.json",
        dict(
            phase=plan["phase"],
            partition=capture["partition"],
            world=capture["world"],
            epoch=capture["epoch"],
            capture_sha256=digest(dataset / "capture.json"),
            frames=frames,
        ),
    )
    write(run / "evaluation-only-gt.json", dict(frames=truth))
    write(run / "benchmark.json", dict(scenes=scenes))
    result = (assess_frames if plan["phase"] == "preparation" else assess_visibility)(
        cases, scenes, truth
    )
    result.update(
        prior_rgb_count=len(prior),
        prior_matches=duplicates,
        capture_sha256=digest(dataset / "capture.json"),
        plan_sha256=digest(plan_path),
        server_sha256=digest(run / "server.json"),
    )
    if duplicates:
        result["status"] = "FAIL"
    write(run / "visibility.json", result)
    return result

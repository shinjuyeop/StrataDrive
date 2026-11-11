"""Frozen2K/4K development comparison; no holdout or prospective model selection."""
from pathlib import Path
import numpy as np
import hashlib
from physical_ai.perception.contract import FrameIdentity, sha256_file
from physical_ai.perception.dataset import read_json
from physical_ai.perception.camera_resolution_v1 import NativeFrame, unpack, health
from camera_resolution_v1_common import cases, annotate
from quality_geometry_v4 import check_pose
from quality_staging_v5 import staging_pose
from run_model_screen_v1 import require, write_new
from probe_async_native_v1 import check_sources
ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / "profiles/perception-camera-resolution-plan-v1.json"

def verify_sources(path):
    digest = check_sources(path)
    f = read_json(path)
    require(all(sha256_file(ROOT / name) == value for name,value in f["inputs"].items()), "frozen model/manifest/prior exclusions")
    return digest


def check_freeze(path):
    verify_sources(path)
    f = read_json(path)
    require(f["schema"] == "m10-source-compare-freeze-v1" and f["quality_scales"] == [6,4] and not f["holdout_access"] and not f["runtime_promotion"], "declared comparison")
    return dict(f, sources=f["files"])

def derive(capture, freeze_path):
    f = check_freeze(freeze_path)
    cap = read_json(capture)
    server = read_json(capture.parent.parent / "server.json")
    plan = read_json(PLAN)
    require(
        cap["schema"] == "m10-camera-resolution-capture-v1"
        and cap["partition"] == "development"
        and cap["status"] == server["status"] == "PASS"
        and server["schema"] == "m10-camera-resolution-server-v1"
        and server["server_exit"] == 130
        and server["capture_exit"] == 0
        and not server.get("forced_stop")
        and server["freeze_sha256"] == sha256_file(freeze_path)
        and cap["plan_sha256"] == server["plan_sha256"] == f["plan_sha256"]
        and not cap["overflow"]
        and not cap["cleanup_errors"],
        "normal lifecycle/source identity",
    )
    require(
        server["probe_sha256"]
        == f["sources"]["tests/integration/perception/carla_camera_resolution_v1.py"]
        and server["helper_sha256"]
        == f["sources"]["tests/integration/perception/quality_geometry_v4.py"]
        and server["staging_sha256"]
        == f["sources"]["tests/integration/perception/quality_staging_v5.py"],
        "capture helpers identity",
    )
    for attrs in cap["sensor_attributes"].values():
        require(
            int(attrs["image_size_x"]) == 640 * cap["scale"]
            and int(attrs["image_size_y"]) == 384 * cap["scale"]
            and float(attrs["fov"]) == 90
            and float(attrs["sensor_tick"]) == 0,
            "actual sensor attributes",
        )
    expected = cases(plan, cap["phase"])
    scale = cap["scale"]
    w, h = 640 * scale, 384 * scale
    require(
        cap["camera"] == dict(width=w, height=h, fov_degrees=90, calibration_revision=1)
        and server["scale"] == scale
        and cap["phase"] == server["phase"]
        and len(cap["frames"]) == len(cap["scenes"]) == len(expected),
        "capture layout/denominator",
    )
    part = plan["partitions"]["development"]
    check_pose(cap["camera_pose"], part["camera_pose"])
    require(
        cap["xodr_sha256"] == plan["xodr_sha256"]
        and cap["survey_sha256"] == plan["survey_sha256"],
        "map identity",
    )
    rgb = dict(
        schema="m10-highres-rgb-only-v1",
        partition="development",
        phase=cap["phase"],
        scale=scale,
        camera=cap["camera"],
        epoch=cap["epoch"],
        clock_instance=cap["clock_instance"],
        capture_sha256=sha256_file(capture),
        frames=[],
    )
    gt = dict(
        schema="m10-camera-native-derived-gt-v1",
        partition="development",
        scale=scale,
        frames=[],
    )
    meta = dict(
        schema="m10-camera-development-metadata-v1",
        phase=cap["phase"],
        scale=scale,
        scenes=[],
    )
    missing = []
    missing_riders = []
    health_rows = []
    for case, scene, row in zip(expected, cap["scenes"], cap["frames"]):
        require(
            case["id"] == scene["id"] == row["scene"]
            and scene["frame"] == row["frame"]
            and len(scene["actors"]) == len(case["actors"]),
            "scene/actor lineage",
        )
        raw = unpack(capture.parent, row["rgb"], w, h)
        instance = unpack(capture.parent, row["instance"], w, h)
        data = (
            np.frombuffer(raw, np.uint8).reshape(h, w, 4)[:, :, 2::-1].copy().tobytes()
        )
        frame = NativeFrame(
            FrameIdentity(
                cap["epoch"], cap["clock_instance"], row["frame"], row["source_ns"]
            ),
            w,
            h,
            data,
        )
        health_rows.append(health(frame))
        objects, excluded = annotate(instance, w, h)
        keys = {(o["class_id"], o["instance_id"]) for o in objects}
        for n, (wanted, actual) in enumerate(zip(case["actors"], scene["actors"])):
            require(
                all(wanted[k] == actual[k] for k in ("class_id", "blueprint", "role")),
                "actor semantics",
            )
            check_pose(actual["pose"], wanted["pose"])
            check_pose(
                actual["staging_requested_pose"], staging_pose(wanted["pose"], n)
            )
            road = actual["road_readback"]
            require(
                road["road_id"] == wanted["road_node"]["road_id"]
                and road["lane_id"] == wanted["road_node"]["lane_id"]
                and road["projection_m"] <= 2
                and abs(road["clearance_error_m"]) <= 0.15,
                "actual road readback",
            )
            key = (actual["class_id"], actual["actor_id"] % 65536)
            if key not in keys:
                missing.append(dict(scene=row["scene"], actor=n))
            if actual["class_id"] in (1, 3) and (0, key[1]) not in keys:
                missing_riders.append(dict(scene=row["scene"], actor=n))
        rgb["frames"].append(
            dict(
                scene=row["scene"],
                frame=row["frame"],
                source_ns=row["source_ns"],
                rgb_sha256=hashlib.sha256(data).hexdigest(),
                rgb_raw=row["rgb"],
            )
        )
        gt["frames"].append(
            dict(
                scene=row["scene"],
                frame=row["frame"],
                objects=objects,
                excluded=excluded,
            )
        )
        meta["scenes"].append(
            dict(
                scene=row["scene"],
                weather=case["weather"],
                stratum=case["stratum"],
                target_class=case["target_class"],
                actors=scene["actors"],
            )
        )
    acceptance = dict(
        schema="m10-camera-source-acceptance-v1",
        status="PASS" if not missing and not missing_riders else "FAIL",
        phase=cap["phase"],
        scale=scale,
        frames=len(expected),
        missing_actors=missing,
        missing_riders=missing_riders,
        min_luma_std=min(r["luma_std"] for r in health_rows),
        capture_sha256=sha256_file(capture),
        server_sha256=sha256_file(capture.parent.parent / "server.json"),
    )
    return dict(rgb=rgb, truth=gt, metadata=meta, acceptance=acceptance)

def save_derived(capture, freeze_path):
    result = derive(capture, freeze_path)
    for key, name in [
        ("rgb", "rgb.json"),
        ("truth", "evaluation-only-gt.json"),
        ("metadata", "benchmark.json"),
        ("acceptance", "acceptance.json"),
    ]:
        write_new(capture.parent / name, result[key])
    return result["acceptance"]

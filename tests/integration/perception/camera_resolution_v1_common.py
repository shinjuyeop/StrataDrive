"""Prospective camera-source freeze, native mask reconstruction and technical choice."""

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import FrameIdentity, sha256_file
from physical_ai.perception.dataset import read_json
from physical_ai.perception.camera_resolution_v1 import (
    SCALES,
    NativeFrame,
    unpack,
    health,
    scale_of,
)
from quality_annotation import SEMANTICS_BY_CLASS
from quality_geometry_v4 import check_pose
from quality_staging_v5 import staging_pose
from run_model_screen_v1 import require, write_new

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / "profiles/perception-camera-resolution-plan-v1.json"
CANDIDATE = ROOT / "profiles/perception-resolution-candidates-v1.json"
EXCLUSION = (
    ROOT / "docs/test-plan/evidence/m10_quality_v9/future-evaluation-exclusion.json"
)


def freeze(base):
    parent = read_json(ROOT / "build/m10-resolution-car-v1/freeze.json")
    sources = dict(parent["sources"])
    for n, h in sources.items():
        require(sha256_file(ROOT / n) == h, "parent source drift: " + n)
    paths = list(
        (ROOT / "physical_ai/perception").glob("*camera_resolution_v1.py")
    ) + list((ROOT / "tests/integration/perception").glob("*camera_resolution_v1*.py"))
    paths += [
        PLAN,
        CANDIDATE,
        ROOT / "docs/test-plan/perception-camera-resolution-v1-protocol.md",
        ROOT / "docs/test-plan/perception-camera-resolution-v1-recovery.md",
    ]
    paths.append(ROOT / "docs/test-plan/perception-camera-resolution-v1-recovery.md")
    sources.update({str(p.relative_to(ROOT)): sha256_file(p) for p in paths})
    model = read_json(CANDIDATE)["models"]["dfine-m-960-car-v1"]
    require(
        model["confidence_vector"] == [0.6, 0.4, 0.6, 0.5, 0.5, 0.6]
        and model["size"] == 960,
        "fixed detector/vector",
    )
    inputs = [
        ROOT / "build/m10-resolution-v2/models/dfine-960.onnx",
        ROOT / "build/m10-resolution-v2/models.json",
        ROOT / "build/m10-model-screen-v2/upstream/dfine-m.pth",
        EXCLUSION,
    ]
    require(
        sha256_file(inputs[0]) == model["onnx_sha256"]
        and len(read_json(EXCLUSION)["rgb_sha256"]) == 5449,
        "model/prior exclusion identity",
    )
    f = dict(
        schema="m10-camera-source-freeze-v1",
        created_utc=datetime.now(timezone.utc).isoformat(),
        sources=sources,
        inputs={str(p.relative_to(ROOT)): sha256_file(p) for p in inputs},
        scales=list(SCALES),
        plan_sha256=sha256_file(PLAN),
        protocol_sha256=sha256_file(
            ROOT / "docs/test-plan/perception-camera-resolution-v1-protocol.md"
        ),
        model_sha256=model["onnx_sha256"],
        vector=model["confidence_vector"],
        holdout_access=False,
        new_rgb=True,
        runtime_promotion=False,
    )
    write_new(base / "freeze.json", f)
    return f


def check_freeze(path):
    f = read_json(path)
    require(
        f["schema"] == "m10-camera-source-freeze-v1"
        and f["scales"] == list(SCALES)
        and f["plan_sha256"] == sha256_file(PLAN)
        and f["holdout_access"] is False
        and f["runtime_promotion"] is False,
        "camera freeze/scope",
    )
    for n, h in {**f["sources"], **f["inputs"]}.items():
        require(sha256_file(ROOT / n) == h, "camera frozen source/input: " + n)
    return f


def cases(plan, phase):
    all_cases = plan["partitions"]["development"]["cases"]
    return (
        [all_cases[n] for n in plan["pilot_case_indices"]]
        if phase == "pilot"
        else all_cases
    )


def annotate(raw, width, height):
    scale = scale_of(width, height)
    pixels = np.frombuffer(raw, np.uint8).reshape(height, width, 4)
    tags = pixels[:, :, 2]
    ids = pixels[:, :, 1].astype(np.uint16) + (pixels[:, :, 0].astype(np.uint16) << 8)
    included, excluded = [], []
    for cls, allowed in SEMANTICS_BY_CLASS.items():
        selected = np.isin(tags, allowed)
        for ident in np.unique(ids[selected]):
            mask = selected & (ids == ident)
            y, x = np.where(mask)
            box = [int(x.min()), int(y.min()), int(x.max()) + 1, int(y.max()) + 1]
            count = int(mask.sum())
            small = (
                count < 25 * scale * scale
                or min(box[2] - box[0], box[3] - box[1]) < 4 * scale
            )
            obj = dict(
                class_id=cls,
                instance_id=int(ident),
                box=[v / scale for v in box],
                visible_pixels=max(1, count // (scale * scale)),
                semantic_tags=sorted(map(int, np.unique(tags[mask]))),
                native_box=box,
                native_visible_pixels=count,
            )
            if small:
                obj["reason"] = "small_visible_support"
            (excluded if small else included).append(obj)
    return included, excluded


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


def check_selection(base):
    check_freeze(base / "freeze.json")
    s = read_json(base / "selection.json")
    eligible = []
    for scale, row in s["pilots"].items():
        run = base / row["run"]
        a = read_json(run / "dataset/acceptance.json")
        n = read_json(base / f"numeric-{scale}.json")
        require(
            sha256_file(run / "server.json") == row["server_sha256"]
            and sha256_file(run / "dataset/acceptance.json") == row["acceptance_sha256"]
            and sha256_file(base / f"numeric-{scale}.json") == row["numeric_sha256"],
            "pilot selection binding",
        )
        passed = (
            a["status"] == "PASS"
            and n["status"] == "PASS"
            and len(n["rows"]) == 3
            and all(r["passed"] for r in n["rows"])
        )
        if passed:
            eligible.append(int(scale))
    require(
        s["selected_scale"] == max(eligible)
        and s["criterion"] == "largest technical passing source; quality unseen"
        and s["runtime_promotion"] is False,
        "largest technical source choice",
    )
    return s

"""Versioned extractor for append-only occlusion plan; original extractor retained."""

from pathlib import Path
from datetime import datetime
import hashlib
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.dataset import read_json, local_path
from physical_ai.perception.contract import sha256_file, CameraFrame, FrameIdentity
from physical_ai.perception.yolox import image_health
from physical_ai.perception.domain_data_v1 import visible_objects, write_json_new
from quality_geometry_v4 import check_pose
from quality_staging_v5 import staging_pose
from domain_extension_v1 import validate_plan


def prepare(capture, plan_path, freeze_path, exclusion_path, output):
    capture, plan_path, freeze_path, output = map(
        Path, (capture, plan_path, freeze_path, output)
    )
    cap = read_json(capture)
    plan = read_json(plan_path)
    frozen = read_json(freeze_path)
    server = read_json(capture.parent.parent / "server.json")
    validate_plan(plan)
    if frozen["schema"] != "m10-domain-capture-freeze-v1" or frozen["sources"].get(
        "profiles/" + plan_path.name
    ) != sha256_file(plan_path):
        raise ValueError("plan not bound to prelaunch freeze")
    part = plan["partitions"][cap["partition"]]
    for name, digest in frozen["sources"].items():
        if (
            sha256_file(
                freeze_path.parent
                / frozen.get("snapshot_directory", "preflight-source")
                / name
            )
            != digest
        ):
            raise ValueError("frozen source bytes")
    if (
        cap["schema"] != "m10-domain-capture-v1"
        or cap["status"] != server["status"]
        or cap["status"] != "PASS"
        or server["server_exit"] != 130
        or server["capture_exit"] != 0
        or server["schema"] != "m10-domain-server-v1"
        or server.get("forced_stop")
        or any(
            server[k] != n
            for k, n in (
                ("startup_budget_seconds", 180),
                ("capture_budget_seconds", 900),
                ("shutdown_budget_seconds", 30),
            )
        )
        or cap["cleanup_errors"]
        or cap["overflow"]
    ):
        raise ValueError("complete successful capture required")
    if (
        cap["plan_sha256"] != sha256_file(plan_path)
        or server["plan_sha256"] != cap["plan_sha256"]
        or cap["survey_sha256"] != plan["survey_sha256"]
        or cap["xodr_sha256"] != plan["xodr_sha256"]
    ):
        raise ValueError("capture plan/map lineage")
    if not datetime.fromisoformat(frozen["created_utc"]) < datetime.fromisoformat(
        server["started_utc"]
    ):
        raise ValueError("freeze must precede capture")
    for field, name in [
        ("probe_sha256", "carla_domain_capture_v1.py"),
        ("helper_sha256", "quality_geometry_v4.py"),
        ("staging_sha256", "quality_staging_v5.py"),
    ]:
        executed = capture.parent.parent / (
            "capture-probe.py" if field == "probe_sha256" else name
        )
        if (
            sha256_file(executed) != server[field]
            or server[field]
            != frozen["sources"]["tests/integration/perception/" + name]
        ):
            raise ValueError("executed source lineage")
    if len(cap["frames"]) != len(cap["scenes"]) or len(cap["frames"]) != len(
        part["cases"]
    ):
        raise ValueError("raw denominator")
    if (
        cap["phase"] != plan["phase"]
        or cap["client_version"] != cap["server_version"]
        or cap["server_version"] != "294096e-dirty"
    ):
        raise ValueError("phase/SDK")
    prior = set(read_json(exclusion_path)["rgb_sha256"])
    seen = set()
    last = None
    frames = []
    support = []
    health = []
    output.mkdir(parents=True, exist_ok=False)
    (output / "rgb").mkdir()
    for wanted, row, scene in zip(part["cases"], cap["frames"], cap["scenes"]):
        if (
            wanted["id"] != row["scene"]
            or row["scene"] != scene["id"]
            or row["frame"] != scene["frame"]
        ):
            raise ValueError("scene/frame lineage")
        if last and (row["frame"] <= last[0] or row["source_ns"] <= last[1]):
            raise ValueError("source ordering")
        last = (row["frame"], row["source_ns"])
        raw = {}
        for stream in ("rgb", "instance"):
            path = local_path(capture.parent, row[stream]["path"])
            raw[stream] = path.read_bytes()
            if (
                sha256_file(path) != row[stream]["sha256"]
                or len(raw[stream]) != 640 * 384 * 4
            ):
                raise ValueError("raw pair hash/layout")
        pixels = (
            np.frombuffer(raw["rgb"], np.uint8)
            .reshape(384, 640, 4)[:, :, [2, 1, 0]]
            .copy()
            .tobytes()
        )
        digest = hashlib.sha256(pixels).hexdigest()
        if digest in prior or digest in seen:
            raise ValueError("consumed or duplicate RGB")
        seen.add(digest)
        camera = CameraFrame(
            FrameIdentity(
                cap["epoch"], cap["clock_instance"], row["frame"], row["source_ns"]
            ),
            pixels,
        )
        health.append(image_health(camera))
        check_pose(scene["camera_pose"], wanted["camera_pose"])
        objects = visible_objects(raw["instance"])
        by_id = {(o["class_id"], o["instance_id"]): o for o in objects}
        if len(wanted["actors"]) != len(scene["actors"]):
            raise ValueError("actor denominator")
        planned = []
        for n, (expected, actual) in enumerate(zip(wanted["actors"], scene["actors"])):
            if (expected["class_id"], expected["blueprint"], expected["role"]) != (
                actual["class_id"],
                actual["blueprint"],
                actual["role"],
            ):
                raise ValueError("actor identity")
            check_pose(actual["pose"], expected["pose"])
            check_pose(
                actual["staging_requested_pose"], staging_pose(expected["pose"], n)
            )
            road = actual["road_readback"]
            if (
                road["projection_m"] > 2
                or abs(road["clearance_error_m"]) > 0.15
                or road["road_id"] != expected["road_node"]["road_id"]
                or road["lane_id"] != expected["road_node"]["lane_id"]
            ):
                raise ValueError("actual road geometry")
            for key, value in actual["requested_attributes"].items():
                if actual["actor_attributes"][key].replace(" ", "") != value.replace(
                    " ", ""
                ):
                    raise ValueError("actor attribute readback")
            ident = actual["actor_id"] % 65536
            obj = by_id.get((expected["class_id"], ident))
            rider = by_id.get((0, ident)) if expected["class_id"] in (1, 3) else None
            planned.append(
                dict(
                    blueprint=expected["blueprint"],
                    class_id=expected["class_id"],
                    role=expected["role"],
                    instance_id=ident,
                    object=obj,
                    rider=rider,
                    qualified=bool(obj and obj["quality_eligible"]),
                    rider_qualified=bool(
                        rider
                        and rider["quality_eligible"]
                        and 13 in rider["semantic_tags"]
                    ),
                )
            )
        name = f"rgb/{wanted['id']}.rgb"
        (output / name).write_bytes(pixels)
        metadata = {
            k: wanted[k]
            for k in (
                "id",
                "weather",
                "stratum",
                "target_class",
                "orientation_degrees",
                "variant_group",
            )
        }
        if "reference_for" in wanted:
            metadata["reference_for"] = wanted["reference_for"]
        support.append(dict(**metadata, actors=planned))
        frames.append(
            dict(
                scene=wanted["id"],
                rgb_path=name,
                rgb_sha256=digest,
                variant_group=wanted["variant_group"],
                objects=objects,
            )
        )
    data = dict(
        schema="m10-domain-prepared-v1",
        split=part["split"],
        partition=cap["partition"],
        site=part["spawn_point_index"],
        road_id=part["road_id"],
        capture_sha256=sha256_file(capture),
        plan_sha256=sha256_file(plan_path),
        source_freeze_sha256=sha256_file(freeze_path),
        frames=frames,
    )
    write_json_new(output / "data.json", data)
    write_json_new(output / "support.json", dict(frames=support))
    report = dict(
        status="PASS",
        phase=plan["phase"],
        frames=len(frames),
        source_freeze_sha256=sha256_file(freeze_path),
        capture_sha256=sha256_file(capture),
        quality_supported_objects=sum(
            o["quality_eligible"] for row in frames for o in row["objects"]
        ),
        small_fragments=sum(
            not o["quality_eligible"] for row in frames for o in row["objects"]
        ),
        minimum_luma_std=min(h["luma_std"] for h in health),
        rgb_sha256=sorted(seen),
        scope="Raw/pose/labels reconstructed; coverage/export acceptance is separate; no model inference",
    )
    write_json_new(output / "reconstruction.json", report)
    return report


def preflight_gate(data):
    rows = read_json(Path(data) / "support.json")["frames"]
    assets = {}
    for row in rows:
        a = row["actors"][0]
        entry = assets.setdefault(
            a["blueprint"], dict(class_id=a["class_id"], near=[], far=[])
        )
        good = a["qualified"] and (
            a["rider_qualified"] if a["class_id"] in (1, 3) else True
        )
        entry["near" if row["stratum"] == "preflight-near" else "far"].append(
            dict(
                orientation=row["orientation_degrees"],
                qualified=good,
                pixels=a["object"]["visible_pixels"] if a["object"] else 0,
                rider_pixels=a["rider"]["visible_pixels"] if a["rider"] else 0,
            )
        )
    return dict(
        status="PASS"
        if len(assets) == 22
        and all(
            len(a["near"]) == 4 and all(r["qualified"] for r in a["near"])
            for a in assets.values()
        )
        else "FAIL",
        assets=assets,
        frames=len(rows),
        scope="All near8m views required; far24m support reported separately, no detector/model scores",
    )

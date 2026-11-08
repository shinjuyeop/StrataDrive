#!/usr/bin/env python3
"""Prepare prospectively frozen Rider-aware v3 labels and RGB-only inputs."""

import argparse
import math
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import read_json, local_path
from quality_annotation import visible_boxes_v2
from quality_v3_common import (
    PLAN,
    PREPARATION_PLAN,
    PROTOCOL,
    EXCLUSION,
    require,
    write_new,
)


def check_pose(base, actual, planned):
    yaw = math.radians(base["rotation"]["yaw"])
    forward, right = planned["forward_m"], planned["right_m"]
    expected = [
        base["location"]["x"] + forward * math.cos(yaw) - right * math.sin(yaw),
        base["location"]["y"] + forward * math.sin(yaw) + right * math.cos(yaw),
        base["location"]["z"] + planned["z_offset_m"],
    ]
    require(
        math.dist(expected, [actual["location"][k] for k in ("x", "y", "z")]) <= 0.02,
        "settled actor position",
    )
    delta = (
        actual["rotation"]["yaw"]
        - base["rotation"]["yaw"]
        - planned["yaw_offset_degrees"]
        + 180
    ) % 360 - 180
    require(abs(delta) <= 0.1, "settled actor orientation")


def prepare(capture_path, output):
    capture = read_json(capture_path)
    plan_path = PREPARATION_PLAN if capture["partition"] == "preparation" else PLAN
    plan = read_json(plan_path)
    server = read_json(capture_path.parent.parent / "server.json")
    part = capture["partition"]
    cases = plan["partitions"][part]["cases"]
    require(
        capture["schema"] == "m10-quality-capture-v3"
        and capture["status"] == "PASS"
        and not capture["cleanup_errors"]
        and not capture["overflow"]
        and server["mode"] == "quality-v3"
        and server["status"] == "PASS"
        and server["capture_exit"] == 0
        and server["server_exit"] == 130
        and not server.get("forced_stop")
        and capture["plan_sha256"] == server["plan_sha256"] == sha256_file(plan_path)
        and len(cases)
        == len(capture["frames"])
        == len(capture["scenes"])
        == len(cases),
        "v3 capture completion/identity",
    )
    selection_sha = server.get("selection_sha256")
    if part == "holdout":
        selected = capture_path.parent.parent / "candidate-selection.json"
        require(
            selection_sha == sha256_file(selected)
            and read_json(selected)["schema"] == "m10-quality-selection-v3",
            "v3 holdout selection binding",
        )
    else:
        require(selection_sha is None, "development cannot use nomination")
    output.mkdir(parents=True, exist_ok=False)
    (output / "rgb").mkdir()
    manifest = dict(
        schema="m10-rgb-dataset-v1",
        split="evaluation",
        capture_sha256=sha256_file(capture_path),
        epoch=capture["epoch"],
        clock_instance=capture["clock_instance"],
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
        schema="m10-quality-dataset-v3",
        partition=part,
        plan_sha256=sha256_file(plan_path),
        protocol_sha256=sha256_file(PROTOCOL),
        capture_sha256=manifest["capture_sha256"],
        selection_sha256=selection_sha,
        scenes=[],
    )
    prior = set(read_json(EXCLUSION)["rgb_sha256"])
    for case, scene, source in zip(cases, capture["scenes"], capture["frames"]):
        require(
            case["id"] == scene["id"] == source["scene"]
            and scene["frame"] == source["frame"]
            and all(scene[k] == case[k] for k in ("weather", "stratum", "target_class"))
            and len(scene["actors"]) == len(case["actors"]),
            "v3 scene identity",
        )
        raw = {}
        for stream in ("rgb", "instance"):
            path = local_path(capture_path.parent, source[stream]["path"])
            require(
                sha256_file(path) == source[stream]["sha256"]
                and path.stat().st_size == 640 * 384 * 4,
                "raw image hash/layout",
            )
            raw[stream] = path.read_bytes()
        pixels = np.frombuffer(raw["rgb"], np.uint8).reshape(384, 640, 4)
        rgb_path = f"rgb/{source['frame']:08d}.rgb"
        (output / rgb_path).write_bytes(
            np.ascontiguousarray(pixels[:, :, [2, 1, 0]]).tobytes()
        )
        rgb_sha = sha256_file(output / rgb_path)
        require(
            part == "preparation" or rgb_sha not in prior,
            "consumed v1/v2/preparation RGB cannot become v3 evaluation data",
        )
        manifest["frames"].append(
            dict(
                scene=case["id"],
                frame=source["frame"],
                source_ns=source["source_ns"],
                rgb_path=rgb_path,
                rgb_sha256=rgb_sha,
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
        actors = []
        ids = [a["actor_id"] % 65536 for a in scene["actors"]]
        require(len(set(ids)) == len(ids), "aliased instance IDs")
        for planned, actual in zip(case["actors"], scene["actors"]):
            require(
                all(planned[k] == actual[k] for k in ("class_id", "blueprint", "role")),
                "actor lineage",
            )
            check_pose(capture["base_pose"], actual["pose"], planned)
            key = (actual["class_id"], actual["actor_id"] % 65536)
            actors.append(
                dict(
                    actual,
                    included=any(
                        (o["class_id"], o["instance_id"]) == key for o in objects
                    ),
                    excluded_small=any(
                        (o["class_id"], o["instance_id"]) == key for o in excluded
                    ),
                )
            )
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
    truth["rgb_manifest_sha256"] = sha256_file(output / "rgb.json")
    write_new(output / "evaluation-only-gt.json", truth)
    metadata.update(
        rgb_manifest_sha256=sha256_file(output / "rgb.json"),
        truth_sha256=sha256_file(output / "evaluation-only-gt.json"),
    )
    write_new(output / "benchmark.json", metadata)
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
        )
    }
    seal.update(
        schema="m10-quality-data-seal-v3",
        metadata_sha256=sha256_file(output / "benchmark.json"),
    )
    write_new(output / "benchmark-seal.json", seal)
    return dict(
        partition=part,
        frames=len(cases),
        missing_primary=sum(
            not a["included"]
            for m in metadata["scenes"]
            for a in m["actors"]
            if a["role"] == "target"
        ),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(prepare(args.capture, args.output))

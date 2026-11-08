#!/usr/bin/env python3
"""Build separate RGB and evaluation-only labels for the frozen quality plan."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import read_json
from prepare_dataset import prepare


def prepare_quality(capture_path, plan_path, output):
    capture, plan = read_json(capture_path), read_json(plan_path)
    partition = capture["partition"]
    cases = plan["partitions"][partition]["cases"]
    if (
        capture["schema"] != "m10-quality-capture-v1"
        or capture["plan_sha256"] != sha256_file(plan_path)
        or len(cases) != 81
        or len(capture["scenes"]) != len(cases)
        or [r["scene"] for r in capture["frames"]] != [c["id"] for c in cases]
        or [r["id"] for r in capture["scenes"]] != [c["id"] for c in cases]
    ):
        raise ValueError("quality capture/plan denominator")
    server = read_json(capture_path.parent.parent / "server.json")
    if (
        server["status"] != "PASS"
        or server["server_exit"] != 130
        or server.get("forced_stop")
    ):
        raise ValueError("capture server cleanup")
    if partition == "holdout" and (
        not server.get("selection_sha256")
        or server["selection_sha256"]
        != sha256_file(capture_path.parent.parent / "candidate-selection.json")
    ):
        raise ValueError("holdout selection was not sealed before acquisition")
    manifest = prepare(capture_path, output, expected_frames=len(cases))
    truth = read_json(output / "evaluation-only-gt.json")
    scene_metadata = []
    for planned, scene, gt in zip(cases, capture["scenes"], truth["frames"]):
        if (
            scene["frame"] != gt["frame"]
            or scene["weather"] != planned["weather"]
            or scene["stratum"] != planned["stratum"]
            or scene["target_class"] != planned["target_class"]
            or len(scene["actors"]) != len(planned["actors"])
        ):
            raise ValueError("scene metadata mismatch")
        visible = []
        for expected, actual in zip(planned["actors"], scene["actors"]):
            if any(actual[k] != expected[k] for k in ("blueprint", "class_id", "role")):
                raise ValueError("actor blueprint/class mismatch")
            matching = [
                t
                for t in gt["objects"]
                if (t["instance_id"], t["class_id"])
                == (actual["actor_id"] % 65536, actual["class_id"])
            ]
            excluded = [
                t
                for t in gt["excluded"]
                if (t["instance_id"], t["class_id"])
                == (actual["actor_id"] % 65536, actual["class_id"])
            ]
            visible.append(
                dict(
                    actor_id=actual["actor_id"],
                    blueprint=actual["blueprint"],
                    class_id=actual["class_id"],
                    role=actual["role"],
                    included=len(matching) == 1,
                    excluded_small=len(excluded) == 1,
                )
            )
        scene_metadata.append(
            dict(
                scene=planned["id"],
                weather=planned["weather"],
                stratum=planned["stratum"],
                target_class=planned["target_class"],
                actors=visible,
            )
        )
    metadata = dict(
        schema="m10-quality-dataset-v1",
        partition=partition,
        plan_sha256=sha256_file(plan_path),
        capture_sha256=sha256_file(capture_path),
        rgb_manifest_sha256=sha256_file(output / "rgb.json"),
        truth_sha256=sha256_file(output / "evaluation-only-gt.json"),
        selection_sha256=server.get("selection_sha256"),
        scenes=scene_metadata,
    )
    (output / "benchmark.json").write_text(json.dumps(metadata, indent=2) + "\n")
    seal = dict(
        schema="m10-quality-data-seal-v1",
        partition=partition,
        plan_sha256=sha256_file(plan_path),
        capture_sha256=metadata["capture_sha256"],
        rgb_manifest_sha256=metadata["rgb_manifest_sha256"],
        truth_sha256=metadata["truth_sha256"],
        metadata_sha256=sha256_file(output / "benchmark.json"),
        selection_sha256=metadata["selection_sha256"],
    )
    (output / "benchmark-seal.json").write_text(json.dumps(seal, indent=2) + "\n")
    return dict(
        frames=len(manifest["frames"]),
        partition=partition,
        missing_visible_targets=sum(
            not a["included"]
            for c in scene_metadata
            for a in c["actors"]
            if a["role"] == "target"
        ),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("capture", type=Path)
    p.add_argument("plan", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    print(json.dumps(prepare_quality(a.capture, a.plan, a.output)))

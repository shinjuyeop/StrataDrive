"""Rejoin moving native physics receipts, measured component state and actual clone exposures."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import sys

from PIL import Image

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "tests/integration/perception")
)
from endurance_recording_v1 import Zstd

from m10_compare_visual_scene import measured, read, sha


def transform_error(a, b):
    if len(a) != 10 or len(b) != 10 or not all(math.isfinite(x) for x in (*a, *b)):
        raise ValueError("invalid UE component transform")
    lengths = [math.sqrt(sum(x * x for x in t[3:7])) for t in (a, b)]
    if min(lengths) <= 0 or any(abs(v - 1) > 1e-4 for v in lengths):
        raise ValueError("invalid UE rotation")
    dot = abs(sum(x * y for x, y in zip(a[3:7], b[3:7]))) / math.prod(lengths)
    return (
        math.dist(a[:3], b[:3]),
        math.degrees(2 * math.acos(min(1, dot))),
        max(abs(x - y) for x, y in zip(a[7:], b[7:])),
    )


def checked(root, record):
    path = root / record["path"]
    if path.parent != root or sha(path) != record["sha256"]:
        raise ValueError("retained original changed")
    return read(path)


def compare(source, renderer):
    src, dst = read(source / "index.json"), read(renderer / "result.json")
    if (
        dst["source_index_sha256"] != sha(source / "index.json")
        or dst["physical_world"] != src["world"]
    ):
        raise ValueError("renderer bound a different physical source")
    physical = {r["frame"]: checked(source, r) for r in src["frames"]}
    if len(physical) != 16:
        raise ValueError("missing native samples")
    native = read(source.parent / "result.json")
    with (source.parent / "trace.jsonl").open() as stream:
        seen = set()
        for line in stream:
            receipt = json.loads(line).get("receipt")
            if not receipt:
                continue
            frame = int(receipt["frame"])
            if frame in physical:
                if frame in seen or receipt != physical[frame]["original_receipt"]:
                    raise ValueError("ambiguous physical receipt")
                seen.add(frame)
        if seen != set(physical):
            raise ValueError("missing trace receipt")
    by_frame = {r["frame"]: r for r in dst["inspected"]}
    if len(by_frame) != len(dst["inspected"]):
        raise ValueError("duplicate renderer frame")
    source_digests = {r["frame"]: r["sha256"] for r in src["frames"]}
    packages = set()
    mismatches = Counter()
    measures = defaultdict(lambda: [0.0, 0.0, 0.0])
    source_wheels = defaultdict(set)
    max_omega = 0.0
    mappings = []
    codec = Zstd()
    for image in dst["images"]:
        path = renderer / image["path"]
        if (
            path.parent != renderer
            or (image["width"], image["height"]) != (2560, 1536)
            or image["original_bytes"] != 2560 * 1536 * 4
        ):
            raise ValueError("camera image dimensions or file identity")
        packed = path.read_bytes()
        original_bytes = codec.decompress(packed, image["original_bytes"])
        rgb = Image.frombytes(
            "RGB", (2560, 1536), original_bytes, "raw", "BGRX"
        ).tobytes()
        if (
            len(packed) != image["stored_bytes"]
            or hashlib.sha256(original_bytes).hexdigest() != image["original_sha256"]
            or hashlib.sha256(rgb).hexdigest() != image["rgb_sha256"]
        ):
            raise ValueError("original BGRA or RGB camera bytes changed")
        br = by_frame[image["frame"]]
        number = br["physical_frame"]
        if (
            image["physical_frame"] != number
            or image["physical_payload_sha256"] != source_digests[number]
            or br["physical_payload_sha256"] != source_digests[number]
            or abs(image["source_seconds"] - br["source_seconds"]) > 1e-6
            or hashlib.sha256(packed).hexdigest() != image["stored_sha256"]
        ):
            raise ValueError("camera-to-native-frame association changed")
        original = physical[number]
        if (
            br["physical_world"] != original["world"]
            or br["physical_receipt_ticket"] != original["original_receipt"]["ticket"]
            or br["physical_source_seconds"] != original["source_seconds"]
        ):
            raise ValueError("original world, ticket or physical timestamp mismatch")
        observation = checked(renderer, br)
        if (
            int(observation["frame"]) != image["frame"]
            or observation["source_seconds"] != br["source_seconds"]
        ):
            raise ValueError("renderer observation identity")
        max_omega = max(
            max_omega,
            *(
                abs(w["solver_omega_rad_s"])
                for w in original["original_receipt"]["physics"]["wheels"]
            ),
        )
        for source_actor in src["actors"]:
            name = source_actor["blueprint"]
            (target,) = [m for m in dst["actors"] if m["blueprint"] == name]
            (a,) = [
                m
                for m in original["visual"]["actors"]
                if m["actor"] == source_actor["id"]
            ]
            (b,) = [m for m in observation["actors"] if m["actor"] == target["id"]]
            af, _ = measured(a, packages)
            bf, _ = measured(b, packages)
            for component in af.keys() | bf.keys():
                if component not in af or component not in bf:
                    mismatches[name + "/component_inventory"] += 1
                    continue
                ac, bc = af[component], bf[component]
                for k in ac.keys() | bc.keys():
                    if k not in ac or k not in bc:
                        mismatches[name + "/" + k] += 1
                    elif k == "bones":
                        by_name = {v["name"]: v for v in bc[k]}
                        if {v["name"] for v in ac[k]} != set(by_name):
                            mismatches[name + "/bone_inventory"] += 1
                        for bone in ac[k]:
                            other = by_name.get(bone["name"])
                            if not other:
                                continue
                            group = (
                                "wheel" if "wheel" in bone["name"].lower() else "bone"
                            )
                            key = name + "/" + group
                            src_transform = bone["component_transform_cm_xyzw_scale"]
                            if group == "wheel":
                                source_wheels[(name, bone["name"])].add(
                                    tuple(src_transform)
                                )
                            if (bone["parent"], bone["visibility"]) != (
                                other["parent"],
                                other["visibility"],
                            ):
                                mismatches[key + "/hierarchy_or_visibility"] += 1
                            values = transform_error(
                                src_transform,
                                other["component_transform_cm_xyzw_scale"],
                            )
                            measures[key] = list(map(max, measures[key], values))
                    elif k.endswith("transform_cm_xyzw_scale"):
                        values = transform_error(ac[k], bc[k])
                        key = name + "/" + k
                        measures[key] = list(map(max, measures[key], values))
                    elif ac[k] != bc[k]:
                        mismatches[name + "/" + k] += 1
        mappings.append(
            dict(
                physical_frame=number,
                renderer_frame=image["frame"],
                original_bgra_sha256=image["original_sha256"],
                rgb_sha256=image["rgb_sha256"],
            )
        )
    if len(mappings) != len(physical) or {r["physical_frame"] for r in mappings} != set(
        physical
    ):
        raise ValueError("incomplete camera coverage of declared samples")
    positions = [r["poses"][0]["xyz"] for r in physical.values()]
    return dict(
        scope="Native simulation-time acquisition and independent offline renderer replay. Measured fields on the sampled exposures.",
        status="MEASURED",
        complete_scene_proof=False,
        live_native_perception_admissions=0,
        physical_source_sha256=sha(source / "index.json"),
        renderer_index_sha256=sha(renderer / "result.json"),
        physical_intervals=native["receipts"],
        settlements=native["settlements"],
        samples=len(physical),
        maximum_ego_displacement_m=max(math.dist(positions[0], p) for p in positions),
        max_abs_solver_wheel_rad_s=max_omega,
        unique_source_wheel_bone_transforms={
            name + "/" + bone: len(s)
            for (name, bone), s in sorted(source_wheels.items())
        },
        component_max_error_cm_degrees_scale=dict(sorted(measures.items())),
        categorical_differences=dict(sorted(mismatches.items())),
        original_camera_images_redecoded=len(mappings),
        camera_links=mappings,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "renderer", "output"):
        p.add_argument(name, type=Path)
    a = p.parse_args()
    result = compare(a.source, a.renderer)
    with a.output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")

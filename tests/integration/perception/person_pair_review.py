"""Verify paired intervention geometry and measure actual walker mask loss."""

import argparse
from collections import Counter, defaultdict
import hashlib
import math
from pathlib import Path
import zlib


from camera_resolution_v1_common import annotate
from person_pair_candidate import TOWNS, dump, read


def audit(root, split):
    town = TOWNS[split]
    run = root / town
    server = read(run / "server.json")
    ds = run / "dataset"
    plan = read(ds / "plan.json")
    if server["status"] != "PASS" or server["xodr_sha256"] != plan["xodr_sha256"]:
        raise ValueError("capture or map identity")
    groups = defaultdict(dict)
    for scene, gt in zip(plan["scenes"], read(ds / "labels.json"), strict=True):
        if scene["id"] != gt["id"] or scene["role"] in groups[scene["group"]]:
            raise ValueError("scene association")
        mask = zlib.decompress((ds / (scene["id"] + ".mask.z")).read_bytes())
        if hashlib.sha256(mask).hexdigest() != gt["mask_sha256"] or annotate(
            mask, *plan["size"]
        ) != (gt["objects"], gt["excluded"]):
            raise ValueError("mask hash or annotation mismatch")
        walkers = [a for a in scene["actors"] if a["blueprint"].startswith("walker.")]
        n = 0
        eligible = False
        if walkers:
            ident = gt["actor_ids"][0] % 65536
            match = [
                o
                for o in gt["objects"] + gt["excluded"]
                if o["semantic_tags"] == [12] and o["instance_id"] == ident
            ]
            if match:
                (target,) = match
                n = target["native_visible_pixels"]
                eligible = target in gt["objects"]
            if scene["actors"][0] != walkers[0]:
                raise ValueError("target actor association")
        groups[scene["group"]][scene["role"]] = (scene, n, eligible)
    counts = defaultdict(Counter)
    pairs = []
    for group, v in groups.items():
        if set(v) != {"clear", "car", "cycle", "car_only", "cycle_only"}:
            raise ValueError("incomplete paired capture")
        ref, pixels, eligible = v["clear"]
        loc = ref["actors"][0]["pose"]["location"]
        distance = math.dist(
            [ref["camera"]["location"][k] for k in "xyz"], [loc[k] for k in "xyz"]
        )
        if abs(distance - ref["distance_m"]) > 1e-6:
            raise ValueError("target distance")
        for role, (scene, n, ok) in v.items():
            if any(
                scene[k] != ref[k]
                for k in ("weather", "camera", "distance_m", "split", "roads")
            ):
                raise ValueError("scene pair changed")
            if role in ("car", "cycle") and scene["actors"] != [
                ref["actors"][0],
                *v[role + "_only"][0]["actors"],
            ]:
                raise ValueError("actor pair changed")
            if role.endswith("_only"):
                continue
            ratio = n / pixels if pixels else None
            for key in (role, role + ("-30m+" if distance >= 30 else "-under30m")):
                c = counts[key]
                c["planned"] += 1
                c["eligible"] += int(ok)
                c["visible_pixels_nonzero"] += int(n > 0)
                c["partial_10to90pct_loss"] += int(
                    ratio is not None and 0.10 <= ratio <= 0.90 and ok
                )
            pairs.append(
                dict(
                    group=group,
                    role=role,
                    distance_m=distance,
                    eligible=ok,
                    clear_pixels=pixels,
                    visible_pixels=n,
                )
            )
    return dict(
        town=town,
        groups=len(groups),
        frames=len(groups) * 5,
        roads=sorted({r for v in groups.values() for r in v["clear"][0]["roads"]}),
        counts=counts,
        pairs=pairs,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("root", type=Path)
    p.add_argument("split", choices=TOWNS)
    args = p.parse_args()
    dump(
        args.root / ("visibility-" + args.split + ".json"), audit(args.root, args.split)
    )

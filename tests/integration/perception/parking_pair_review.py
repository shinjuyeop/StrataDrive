"""Measure visible-mask support in matched single-car and overlapping pairs."""

import argparse
from collections import defaultdict
from pathlib import Path
from fresh_quality_2k_plan import read, digest


def review(dataset):
    plan = read(dataset / "plan.json")
    frames = read(dataset / "labels.json")
    if read(dataset.parent / "server.json")["status"] != "PASS":
        raise ValueError("incomplete server run")
    groups = defaultdict(dict)
    for scene, frame in zip(plan["scenes"], frames, strict=True):
        if frame["id"] != scene["id"] or frame["split"] != scene["split"]:
            raise ValueError("pair linkage")
        if "group" in scene:
            groups[scene["group"]][scene["role"]] = (scene, frame)
    changed = []
    for group, cases in groups.items():
        both, pair = cases["both"]
        for i, role in enumerate(("front", "rear")):
            alone, frame = cases[role]
            if (
                alone["camera"] != both["camera"]
                or alone["actors"] != [both["actors"][i]]
                or alone["weather"] != both["weather"]
            ):
                raise ValueError("paired geometry or weather changed")

            def support(row, index):
                ident = row["actor_ids"][index] % 65536
                return sum(
                    o["native_visible_pixels"]
                    for o in row["objects"] + row["excluded"]
                    if o["class_id"] == 2 and o["instance_id"] == ident
                )

            total = support(frame, 0)
            visible = support(pair, i)
            changed.append(
                dict(
                    group=group,
                    role=role,
                    alone=total,
                    with_neighbor=visible,
                    ratio=visible / total if total else None,
                )
            )
    partial = sum(r["alone"] > 0 and 0.05 <= r["ratio"] <= 0.85 for r in changed)
    return dict(
        map=plan["map"],
        frames=len(frames),
        matched_triplets=len(groups),
        partially_occluded_actor_observations=partial,
        fully_hidden_actor_observations=sum(
            r["alone"] > 0 and r["with_neighbor"] == 0 for r in changed
        ),
        plan_sha256=digest(dataset / "plan.json"),
        labels_sha256=digest(dataset / "labels.json"),
        pairs=changed,
    )


if __name__ == "__main__":
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with args.output.open("x") as f:
        json.dump(review(args.dataset), f, indent=2)

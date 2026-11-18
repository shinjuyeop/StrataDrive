"""Compare the measured visual fields of parked actors in two independent worlds."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
FIELDS = (
    "class",
    "visible",
    "parent",
    "socket",
    "relative_transform_cm_xyzw_scale",
    "world_transform_cm_xyzw_scale",
    "mesh",
    "mesh_package",
    "master_pose",
    "morph_weights",
    "active_morph_targets",
    "bones",
    "bones_truncated",
    "declared_bones",
    "parallel_evaluation",
    "clothing_present",
)
TAG_CLASS = "/Script/Carla.TaggedComponent"


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(data)
    return digest.hexdigest()


def read(path):
    return json.loads(path.read_text())


def frames(root):
    index = read(root / "result.json")
    values = []
    for item in index["inspected"]:
        path = root / item["path"]
        value = read(path)
        if (
            sha(path) != item["sha256"]
            or not value["ok"]
            or value["complete_scene_proof"] is not False
            or int(value["frame"]) != item["frame"]
            or set(x["id"] for x in index["actors"])
            != set(a["actor"] for a in value["actors"])
            or int(value["acquired_end_ns"]) - int(value["acquired_begin_ns"])
            != item["acquisition_ns"]
        ):
            raise ValueError("inspection identity, original acquisition or payload")
        values.append(value)
    if len(values) != 16 or any(
        int(b["frame"]) != int(a["frame"]) + 1 for a, b in zip(values, values[1:])
    ):
        raise ValueError("expected sixteen distinct consecutive inspected frames")
    return index, values


def measured(actor, packages):
    parts = {}
    tags = []
    packages.add(actor["class"].split(".")[0])
    for component in actor["components"]:
        key = (
            component["name"],
            component["parent"],
            component["socket"],
            component["class"],
        )
        if component["class"] == TAG_CLASS:
            tags.append(key)
            continue
        if key in parts:
            raise ValueError(f"ambiguous original component {key}")
        fields = {k: component[k] for k in FIELDS if k in component}
        if fields.get("mesh_package"):
            packages.add(fields["mesh_package"])
        if "materials" in component:
            materials = []
            for item in component["materials"]:
                # Object-instance paths belong to their own worlds. Compare the
                # resolved parent asset and all measured parameter values.
                m = {k: v for k, v in item.items() if k != "object"}
                materials.append(m)
                if m.get("package"):
                    packages.add(m["package"])
                packages.update(
                    v["package"] for v in m.get("textures", []) if v["package"]
                )
            fields["materials"] = materials
        parts[key] = fields
    return parts, sorted(tags)


def package_files(packages, mounts):
    inventory = {}
    for name in sorted(packages):
        prefix, matched = next(
            ((key, v) for key, v in mounts.items() if name.startswith(key)),
            (None, None),
        )
        parts = Path(name[len(prefix) :]).parts if prefix else ()
        if not parts or ".." in parts:
            inventory[name] = dict(error="unknown package mount")
            continue
        stem = matched.joinpath(*parts)
        files = [
            p
            for ext in (".uasset", ".umap", ".uexp", ".ubulk", ".uptnl")
            if (p := stem.with_suffix(ext)).is_file()
        ]
        if not any(p.suffix in (".uasset", ".umap") for p in files):
            inventory[name] = dict(error="package file missing")
        else:
            inventory[name] = [
                dict(path=str(p), bytes=p.stat().st_size, sha256=sha(p)) for p in files
            ]
    return inventory


def compare(pair):
    bundle = read(pair / "result.json")
    owner, physical = frames(pair / "owner/inspect")
    replica, rendered = frames(pair / "renderer/inspect")
    if owner["map"] != replica["map"] or owner["xodr_sha256"] != replica["xodr_sha256"]:
        raise ValueError("map identity mismatch")
    packages = {owner["map"].replace("Carla/Maps/", "/Game/Carla/Maps/")}
    reports = []
    for model in owner["actors"]:
        (match,) = [
            a for a in replica["actors"] if a["blueprint"] == model["blueprint"]
        ]
        if (
            model["spawn_index"] != match["spawn_index"]
            or model["attributes"] != match["attributes"]
        ):
            raise ValueError("actor recipe mismatch")
        mismatch = Counter()
        examples = []
        tags = set()
        for number, (source, image) in enumerate(zip(physical, rendered)):
            (a,) = [x for x in source["actors"] if x["actor"] == model["id"]]
            (b,) = [x for x in image["actors"] if x["actor"] == match["id"]]
            af, at = measured(a, packages)
            bf, bt = measured(b, packages)
            tags.add((len(at), len(bt)))
            for name in sorted(set(af) | set(bf)):
                reasons = (
                    ["component_inventory"]
                    if name not in af or name not in bf
                    else [
                        k
                        for k in sorted(set(af[name]) | set(bf[name]))
                        if af[name].get(k) != bf[name].get(k)
                    ]
                )
                for reason in reasons:
                    mismatch[reason] += 1
                    if len(examples) < 16:
                        examples.append(
                            dict(index=number, component=name, field=reason)
                        )
        bones = [v for v in af.values() if "bones" in v]
        materials = [m for v in af.values() for m in v.get("materials", ())]
        reports.append(
            dict(
                blueprint=model["blueprint"],
                owner_id=model["id"],
                renderer_id=match["id"],
                compared_components=len(af),
                skeletal_bones=sum(len(v["bones"]) for v in bones),
                wheel_bones=[
                    b["name"]
                    for v in bones
                    for b in v["bones"]
                    if "wheel" in b["name"].lower()
                ],
                material_slots=len(materials),
                parameter_counts={
                    k: sum(len(m.get(k, ())) for m in materials)
                    for k in (
                        "scalars",
                        "vectors",
                        "textures",
                        "unsupported_parameters",
                    )
                },
                tagged_auxiliary_counts=sorted(tags),
                mismatches=dict(mismatch),
                examples=examples,
            )
        )
    args = bundle["stages"]["owner"]["argv"]
    inventory = package_files(
        packages,
        {
            "/Game/": Path(args[1]).parent / "Content",
            "/Engine/": Path(args[0]).parents[2] / "Content",
        },
    )
    return dict(
        schema="m10-parked-visual-comparison-v1",
        status="MEASURED",
        pair_status=bundle["status"],
        scope="Paired ordinal samples in separately parked worlds. Directly named asset packages and enumerated fields only.",
        complete_scene_proof=False,
        native_perception_admissions=0,
        map=owner["map"],
        xodr_sha256=owner["xodr_sha256"],
        owner_world=owner["world"],
        renderer_world=replica["world"],
        independent_frames=16,
        actors=reports,
        owner_acquisition_ms_median=statistics.median(
            v["acquisition_ns"] for v in owner["inspected"]
        )
        / 1e6,
        renderer_acquisition_ms_median=statistics.median(
            v["acquisition_ns"] for v in replica["inspected"]
        )
        / 1e6,
        owner_index_sha256=sha(pair / "owner/inspect/result.json"),
        renderer_index_sha256=sha(pair / "renderer/inspect/result.json"),
        measured_field_mismatches=sum(sum(r["mismatches"].values()) for r in reports),
        packages=inventory,
        unresolved_packages=[k for k, v in inventory.items() if isinstance(v, dict)],
        retained_images=len(replica["images"]),
        camera_errors=replica["errors"],
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("pair", type=Path)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    result = compare(args.pair)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as out:
        json.dump(result, out, indent=2, allow_nan=False)
        out.write("\n")
    print(
        f"{result['measured_field_mismatches']} differences, {len(result['packages'])} packages, unresolved {result['unresolved_packages']}"
    )

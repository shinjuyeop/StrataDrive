"""Project registered static vehicles into the consumed development camera."""

import argparse
import json
from pathlib import Path

import carla
from quality_geometry_v4 import camera_projection


def inspect(port, plan, out):
    client = carla.Client("127.0.0.1", port)
    client.set_timeout(30)
    world = client.get_world()
    if world.get_map().name.split("/")[-1] != "Town04_Opt":
        raise ValueError("unexpected survey map")
    camera = plan["partitions"]["development"]["camera_pose"]
    entries = []
    for tag in ("Car", "Truck", "Bus"):
        for obj in world.get_environment_objects(getattr(carla.CityObjectLabel, tag)):
            box = obj.bounding_box
            vertices = box.get_world_vertices(carla.Transform())
            projected = [
                camera_projection(camera, {"location": dict(x=v.x, y=v.y, z=v.z)})
                for v in vertices
            ]
            if any(p["depth_m"] <= 0 for p in projected):
                continue
            us, vs = [p["u"] for p in projected], [p["v"] for p in projected]
            if min(us) >= 640 or max(us) <= 0 or max(vs) <= 0 or min(vs) >= 384:
                continue
            entries.append(
                dict(
                    name=obj.name,
                    registry_id=obj.id,
                    label=tag,
                    bounds_xyz=[dict(x=v.x, y=v.y, z=v.z) for v in vertices],
                    box=[min(us), min(vs), max(us), max(vs)],
                    depth_m=min(p["depth_m"] for p in projected),
                )
            )
    if not entries:
        raise ValueError("no registered vehicle bounding boxes in the source view")
    with out.open("x") as f:
        json.dump(
            dict(
                map=world.get_map().name,
                world=world.id,
                camera=camera,
                scope="Static environment registry and projected bounding boxes. Registry and mask IDs use distinct namespaces.",
                vehicles=sorted(entries, key=lambda row: row["depth_m"]),
            ),
            f,
            indent=2,
        )
        f.write("\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", type=int)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    a = parser.parse_args()
    inspect(a.port, json.loads(a.plan.read_text()), a.output)

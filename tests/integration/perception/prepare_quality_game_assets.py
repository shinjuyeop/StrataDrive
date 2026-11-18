"""Prepare the fixed map and blueprint resources with the two sensor streams absent."""

import argparse
import json
import os
from pathlib import Path
import time

import carla


def prepare(port, plan, output):
    selected = json.loads(plan.read_text())
    blueprints = sorted(
        {
            actor["blueprint"]
            for partition in selected["partitions"].values()
            for case in partition["cases"]
            for actor in case["actors"]
        }
    )
    client = carla.Client("127.0.0.1", port)
    client.set_timeout(300)
    world = client.get_world()
    road = world.get_map()
    if road.name.split("/")[-1] != selected["map"]:
        raise ValueError("unexpected preparation map")
    settings = world.get_settings()
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = 0.01
    world.apply_settings(settings)
    report = dict(
        world=world.id,
        map=road.name,
        blueprints=[],
        barriers=[],
        images=0,
        model_calls=0,
    )

    def save():
        temp = output.with_suffix(".tmp")
        temp.write_text(json.dumps(report, indent=2) + "\n")
        temp.replace(output)

    def barrier():
        begin = time.monotonic_ns()
        request = dict(
            op="quality_asset_barrier", key=os.environ["STRATADRIVE_M10_QUALITY_KEY"]
        )
        value = json.loads(client.m7_nodrive(json.dumps(request)))
        report["barriers"].append(
            dict(begin_ns=begin, end_ns=time.monotonic_ns(), result=value)
        )
        save()
        if (
            not value.get("ok")
            or value["distance_tasks_after"]
            or value["shader_jobs_after"]
        ):
            raise RuntimeError("renderer resource queue remained active")

    barrier()
    points = road.get_spawn_points()
    for index, name in enumerate(blueprints):
        blueprint = world.get_blueprint_library().find(name)
        actor = None
        for offset in range(len(points)):
            road_point = points[(index + offset) % len(points)]
            transform = carla.Transform(road_point.location, road_point.rotation)
            transform.location.z += 3.0
            actor = world.try_spawn_actor(blueprint, transform)
            if actor is not None:
                break
        if actor is None:
            raise RuntimeError(f"no clear preparation spawn for {name}")
        if not actor.destroy():
            raise RuntimeError("preparation actor cleanup failed")
        report["blueprints"].append(name)
        save()
    barrier()
    report["status"] = "PASS"
    save()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", type=int, required=True)
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    prepare(args.port, args.plan, args.output)

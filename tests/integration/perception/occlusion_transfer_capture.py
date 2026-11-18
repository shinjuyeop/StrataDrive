"""Collect road-separated parked-vehicle training pairs on an isolated Town04 server."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import random
import time
import zlib

import carla
import numpy as np
from PIL import Image

from fresh_quality_2k_capture import transform
from fresh_quality_2k_plan import SURVEY, read
from quality_geometry_v4 import road_pose
from quality_sites_v9 import select_fresh
from quality_staging_v5 import staging_pose
from camera_resolution_v1_common import annotate

CARS = (
    "vehicle.audi.etron",
    "vehicle.tesla.model3",
    "vehicle.ford.mustang",
    "vehicle.toyota.prius",
    "vehicle.lincoln.mkz_2020",
    "vehicle.mini.cooper_s",
)
OTHERS = (
    "walker.pedestrian.0014",
    "vehicle.gazelle.omafiets",
    "vehicle.kawasaki.ninja",
    "vehicle.carlamotors.carlacola",
    "vehicle.mitsubishi.fusorosa",
)
WEATHER = ("ClearNoon", "CloudyNoon", "WetCloudyNoon", "ClearSunset")


def plan():
    survey = read(SURVEY)
    sites = {s["spawn_point_index"]: s for s in survey["sites"]}
    prior = [sites[i] for i in (7, 25, 38, 85, 90, 101)]
    chosen = []
    for _ in range(2):
        used = dict(
            schema="m10-used-map-roads-v9",
            map="Town04_Opt",
            route_road_ids=[n["road_id"] for s in prior for n in s["nodes"].values()],
            route_origins=[s["nodes"]["0"]["pose"]["location"] for s in prior],
        )
        pair = select_fresh(survey["sites"], used)
        chosen.extend(pair)
        prior.extend(pair)
    rows = []
    for si, site in enumerate(chosen):
        rand = random.Random(91837 + si)
        nodes = site["nodes"]
        for index in range(48):
            camera = road_pose(
                nodes["0"],
                rand.uniform(-1.3, 1.3),
                rand.uniform(1.75, 2.3),
                rand.uniform(-10, 10),
            )
            camera["rotation"]["pitch"] -= rand.uniform(3, 7)
            entries = []
            cars = rand.sample(CARS[:4] if si < 3 else CARS[4:], 2)
            for bp, dist in zip(
                [*cars, OTHERS[index % len(OTHERS)]],
                [rand.randint(11, 17), rand.randint(23, 28), rand.randint(34, 40)],
            ):
                p = road_pose(
                    nodes[str(dist)],
                    rand.uniform(-1.4, 1.4),
                    0.95 if bp.startswith("walker.") else 0.35,
                    rand.choice((0, 20, 55, 90, 135, 180)),
                )
                entries.append(dict(blueprint=bp, pose=p))
            # Unobstructed far actors and negative road scenes supplement the occluded pairs.
            if index % 6 == 0:
                entries = entries[-1:]
            if index % 16 == 0:
                entries = []
            rows.append(
                dict(
                    id=f"{site['spawn_point_index']}-{index:02}",
                    split="validation" if si == 3 else "train",
                    roads=sorted({n["road_id"] for n in nodes.values()}),
                    camera=camera,
                    weather=WEATHER[index % 4],
                    actors=entries,
                )
            )
    return dict(map=survey["map"], xodr_sha256=survey["xodr_sha256"], scenes=rows)


def parked_plan(world, out):
    """Choose independent banks of registered parked vehicles using geometry alone."""
    road = world.get_map()
    if road.name.split("/")[-1] != "Town05_Opt":
        raise ValueError("parked transfer requires the independent Town05 map")
    cars = [
        (
            obj.id,
            obj.bounding_box.location.x,
            obj.bounding_box.location.y,
            obj.bounding_box.location.z,
        )
        for obj in world.get_environment_objects(carla.CityObjectLabel.Car)
    ]
    candidates = []
    for index, spawn in enumerate(road.get_spawn_points()):
        wp = road.get_waypoint(spawn.location)
        nodes = {}
        for step in range(12):
            tr = wp.transform
            nodes[str(step)] = dict(
                road_id=wp.road_id,
                lane_width=wp.lane_width,
                pose=dict(
                    location=dict(x=tr.location.x, y=tr.location.y, z=tr.location.z),
                    rotation=dict(
                        yaw=tr.rotation.yaw,
                        pitch=tr.rotation.pitch,
                        roll=tr.rotation.roll,
                    ),
                ),
            )
            following = wp.next(1.0)
            if len(following) != 1 or following[0].road_id != wp.road_id:
                break
            wp = following[0]
        if len(nodes) != 12:
            continue
        site = dict(spawn_point_index=index, nodes=nodes)
        loc = nodes["0"]["pose"]["location"]
        xy = (loc["x"], loc["y"])
        near = [
            c
            for c in cars
            if 10 < math.dist(xy, c[1:3]) < 52 and abs(c[3] - loc["z"]) < 4
        ]
        if len(near) >= 2:
            candidates.append((site, xy, sorted(near)))
    (out / "registry-summary.json").write_text(
        json.dumps(dict(objects=len(cars), candidate_sites=len(candidates)))
    )
    selected = []
    for site, xy, near in sorted(
        candidates, key=lambda v: (-len(v[2]), v[0]["spawn_point_index"])
    ):
        if any(
            math.dist(xy, previous[1]) < 150
            or site["nodes"]["0"]["road_id"] == previous[0]["nodes"]["0"]["road_id"]
            for previous in selected
        ):
            continue
        selected.append((site, xy, near))
        if len(selected) == 4:
            break
    if not selected:
        raise ValueError("no independently mapped parked vehicles")
    single_cluster = len(selected) == 1
    if single_cluster:
        # All views of this bank belong to training. Town04 remains validation.
        for candidate in sorted(
            candidates, key=lambda c: (-len(c[2]), c[0]["spawn_point_index"])
        ):
            if all(math.dist(candidate[1], other[1]) >= 15 for other in selected):
                selected.append(candidate)
                if len(selected) == 4:
                    break
    scenes = []
    for i, (site, xy, near) in enumerate(selected):
        rand = random.Random(9973 + i)
        for j in range(60):
            node = site["nodes"][str(j % 12)]
            pos = road_pose(node, rand.uniform(-1, 1), rand.uniform(1.6, 2.4))
            eye = pos["location"]
            car = near[j % len(near)]
            yaw = math.degrees(math.atan2(car[2] - eye["y"], car[1] - eye["x"]))
            pos["rotation"].update(
                yaw=yaw + rand.uniform(-24, 24), pitch=rand.uniform(-9, -2)
            )
            actors = []
            if j % 3:
                target = OTHERS[j % len(OTHERS)]
                distance = rand.uniform(10, 24)
                angle = math.radians(pos["rotation"]["yaw"] + rand.uniform(-26, 26))
                lx, ly = (
                    eye["x"] + distance * math.cos(angle),
                    eye["y"] + distance * math.sin(angle),
                )
                wp = road.get_waypoint(
                    carla.Location(x=lx, y=ly, z=eye["z"]), project_to_road=True
                )
                if (
                    wp
                    and math.dist(
                        (lx, ly), (wp.transform.location.x, wp.transform.location.y)
                    )
                    < 5
                ):
                    actors.append(
                        dict(
                            blueprint=target,
                            pose=dict(
                                location=dict(
                                    x=lx,
                                    y=ly,
                                    z=wp.transform.location.z
                                    + (0.95 if target.startswith("walker.") else 0.35),
                                ),
                                rotation=dict(
                                    yaw=rand.uniform(-180, 180), pitch=0, roll=0
                                ),
                            ),
                        )
                    )
            scenes.append(
                dict(
                    id=f"parked-{site['spawn_point_index']}-{j:02}",
                    split="validation"
                    if not single_cluster and i == len(selected) - 1
                    else "train",
                    roads=[node["road_id"]],
                    registry_target=car[0],
                    camera=pos,
                    weather=WEATHER[j % 4],
                    actors=actors,
                )
            )
    return dict(
        map=road.name,
        xodr_sha256=hashlib.sha256(road.to_opendrive().encode()).hexdigest(),
        scenes=scenes,
    )


def capture(out, port, parked=False):
    out.mkdir(parents=True, exist_ok=False)
    client = carla.Client("localhost", port)
    client.set_timeout(30)
    world = client.get_world()
    spec = parked_plan(world, out) if parked else plan()
    (out / "plan.json").write_text(json.dumps(spec, indent=2))
    road = world.get_map()
    if hashlib.sha256(road.to_opendrive().encode()).hexdigest() != spec["xodr_sha256"]:
        raise ValueError("training map mismatch")
    original = world.get_settings()
    settings = world.get_settings()
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = 0.05
    sensors, actors = [], []
    inbox = queue.Queue()
    results = []
    try:
        world.apply_settings(settings)
        library = world.get_blueprint_library()
        for kind, name in (("rgb", "rgb"), ("mask", "instance_segmentation")):
            bp = library.find("sensor.camera." + name)
            for k, v in {
                "image_size_x": "1280",
                "image_size_y": "768",
                "fov": "90",
                "sensor_tick": "0.05",
            }.items():
                bp.set_attribute(k, v)
            sensor = world.spawn_actor(bp, transform(spec["scenes"][0]["camera"]))
            sensors.append(sensor)
            sensor.listen(lambda image, k=kind: inbox.put((k, image)))
        for scene in spec["scenes"]:
            while actors:
                actors.pop().destroy()
            for sensor in sensors:
                sensor.set_transform(transform(scene["camera"]))
            world.set_weather(getattr(carla.WeatherParameters, scene["weather"]))
            for i, actor in enumerate(scene["actors"]):
                bp = library.find(actor["blueprint"])
                a = world.spawn_actor(bp, transform(staging_pose(actor["pose"], i)))
                actors.append(a)
                a.set_simulate_physics(False)
                a.set_transform(transform(actor["pose"]))
            for _ in range(10):
                world.tick(30)
                while not inbox.empty():
                    inbox.get_nowait()
            target = world.tick(30)
            pair = {}
            for _ in range(4):
                world.tick(30)
            deadline = time.monotonic() + 10
            while len(pair) < 2:
                kind, image = inbox.get(timeout=max(0.01, deadline - time.monotonic()))
                if image.frame == target:
                    pair[kind] = bytes(image.raw_data)
            rgb = (
                np.frombuffer(pair["rgb"], np.uint8)
                .reshape(768, 1280, 4)[:, :, 2::-1]
                .copy()
            )
            basename = scene["id"]
            Image.fromarray(rgb).save(out / (basename + ".png"), compress_level=1)
            (out / (basename + ".mask.z")).write_bytes(zlib.compress(pair["mask"], 1))
            objects, excluded = annotate(pair["mask"], 1280, 768)
            results.append(
                dict(
                    id=basename,
                    split=scene["split"],
                    frame=target,
                    rgb_sha256=hashlib.sha256(rgb).hexdigest(),
                    mask_sha256=hashlib.sha256(pair["mask"]).hexdigest(),
                    actor_ids=[a.id for a in actors],
                    objects=objects,
                    excluded=excluded,
                )
            )
            if len(results) % 12 == 0:
                print(len(results), basename, flush=True)
        (out / "labels.json").write_text(json.dumps(results))
    finally:
        for sensor in sensors:
            sensor.stop()
        for a in [*sensors, *actors]:
            a.destroy()
        world.apply_settings(original)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("out", type=Path)
    p.add_argument("--port", type=int, default=2400)
    p.add_argument("--parked", action="store_true")
    a = p.parse_args()
    capture(a.out, a.port, a.parked)

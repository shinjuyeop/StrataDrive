"""Collect matched unobstructed, occluded and background controls on two separate towns."""

import argparse
import hashlib
import math
from pathlib import Path

from occlusion_transfer_capture import capture

TOWNS = {"Town01_Opt": "train", "Town07_Opt": "validation"}


def pose(tr):
    return dict(
        location={k: getattr(tr.location, k) for k in "xyz"},
        rotation={k: getattr(tr.rotation, k) for k in ("pitch", "yaw", "roll")},
    )


def plan(world, town):
    road = world.get_map()
    if road.name.rsplit("/", 1)[-1] != town:
        raise ValueError("unexpected town")
    split = TOWNS[town]
    starts = []
    for idx, spawn in enumerate(road.get_spawn_points()):
        wp = road.get_waypoint(spawn.location)
        if wp.is_junction or any(
            wp.road_id == w.road_id
            or spawn.location.distance(w.transform.location) < 65
            for _, w in starts
        ):
            continue
        steps = [wp.next(d) for d in (15, 20, 27, 31, 34, 38)]
        if any(
            len(v) != 1
            or v[0].is_junction
            or v[0].road_id != wp.road_id
            or abs(
                (v[0].transform.rotation.yaw - wp.transform.rotation.yaw + 180) % 360
                - 180
            )
            > 8
            for v in steps
        ):
            continue
        starts.append((idx, wp))
        if len(starts) == 2:
            break
    if len(starts) != 2:
        raise ValueError("two straight roads required")
    scenes = []
    walkers = ("0004", "0010", "0015") if split == "train" else ("0001", "0014", "0021")
    for idx, wp in starts:
        for dist in (20, 31, 34, 38):
            for view, weather in enumerate(
                ("ClearNoon", "WetCloudyNoon", "ClearSunset")
            ):
                camera = pose(wp.transform)
                camera["location"]["z"] += 1.8
                camera["rotation"]["pitch"] -= 4
                camera["rotation"]["yaw"] += (view - 1) * 7
                target = pose(wp.next(dist)[0].transform)
                target["location"]["z"] += 0.95
                target["rotation"]["yaw"] += (20, 90, 150)[view]
                walker = dict(
                    blueprint="walker.pedestrian." + walkers[view], pose=target
                )
                group = f"{town}-{idx}-{dist}-{view}"
                for kind, bp, shift in (
                    ("car", "vehicle.toyota.prius", 0.94),
                    ("cycle", "vehicle.kawasaki.ninja", 0.33),
                ):
                    tr = pose(wp.next(dist - 4)[0].transform)
                    origin = camera["location"]
                    end = target["location"]
                    dx, dy = end["x"] - origin["x"], end["y"] - origin["y"]
                    length = math.hypot(dx, dy)
                    sign = 1 if view % 2 else -1
                    tr["location"].update(
                        x=end["x"] - 4 * dx / length - sign * shift * dy / length,
                        y=end["y"] - 4 * dy / length + sign * shift * dx / length,
                    )
                    tr["location"]["z"] += 0.12
                    occluder = dict(blueprint=bp, pose=tr)
                    roles = [(kind, [walker, occluder]), (kind + "_only", [occluder])]
                    if kind == "car":
                        roles.insert(0, ("clear", [walker]))
                    for role, actors in roles:
                        scenes.append(
                            dict(
                                id=group + "-" + role,
                                group=group,
                                role=role,
                                site=idx,
                                roads=[wp.road_id],
                                split=split,
                                distance_m=math.dist(
                                    [origin[k] for k in "xyz"], [end[k] for k in "xyz"]
                                ),
                                camera=camera,
                                actors=actors,
                                weather=weather,
                            )
                        )
    return dict(
        map=road.name,
        xodr_sha256=hashlib.sha256(road.to_opendrive().encode()).hexdigest(),
        size=[2560, 1536],
        scenes=scenes,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("out", type=Path)
    p.add_argument("--parking-map", choices=TOWNS, required=True)
    p.add_argument("--port", type=int, required=True)
    a = p.parse_args()
    capture(
        a.out, a.port, parking_map=a.parking_map, plan_factory=plan, size=(2560, 1536)
    )

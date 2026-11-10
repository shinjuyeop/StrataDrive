#!/usr/bin/env python3
"""Read-only road survey. Produces deterministic route nodes, never RGB or models."""

from quality_sites_v9 import select_fresh
import argparse
import hashlib
import json
from pathlib import Path
from quality_geometry_v4 import (
    route_choice,
    road_pose,
    camera_projection,
    angle_delta,
)


def pose(t):
    return {
        g: {k: getattr(getattr(t, g), k) for k in keys}
        for g, keys in (
            ("location", ("x", "y", "z")),
            ("rotation", ("pitch", "yaw", "roll")),
        )
    }


def node(wp):
    return dict(
        id=wp.id,
        road_id=wp.road_id,
        section_id=wp.section_id,
        lane_id=wp.lane_id,
        s=wp.s,
        lane_width=wp.lane_width,
        is_junction=wp.is_junction,
        pose=pose(wp.transform),
    )


def main():
    import carla

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--port", type=int, default=2300)
    p.add_argument("--used-roads", type=Path, required=True)
    a = p.parse_args()
    used = json.loads(a.used_roads.read_text())
    a.output.mkdir(parents=True, exist_ok=False)
    client = carla.Client("127.0.0.1", a.port)
    client.set_timeout(20)
    world = client.get_world()
    road = world.get_map()
    if road.name.rsplit("/", 1)[-1] != "Town04_Opt":
        raise ValueError("V9 survey requires fixed Town04_Opt")
    spawns = road.get_spawn_points()
    rows = []
    for index, spawn in enumerate(spawns):
        base = road.get_waypoint(
            spawn.location, project_to_road=True, lane_type=carla.LaneType.Driving
        )
        nodes = {"0": node(base)}
        wp = base
        reason = None
        try:
            for distance in range(1, 43):
                options = wp.next(1.0)
                by_id = {v.id: v for v in options}
                chosen = route_choice(
                    wp.transform.rotation.yaw, [node(v) for v in options]
                )
                wp = by_id[chosen["id"]]
                nodes[str(distance)] = chosen
            clearance = spawn.location.z - base.transform.location.z
            camera = road_pose(nodes["0"], 0, clearance + 1.7)
            camera["rotation"]["pitch"] -= 6
            projections = [
                camera_projection(camera, road_pose(n, 0, clearance + 0.5))
                for n in nodes.values()
            ]
            max_turn = max(
                abs(
                    angle_delta(
                        n["pose"]["rotation"]["yaw"],
                        nodes["0"]["pose"]["rotation"]["yaw"],
                    )
                )
                for n in nodes.values()
            )
            eligible = (
                index >= 7
                and not any(n["is_junction"] for n in nodes.values())
                and all(v["in_frame"] for v in projections[5:])
                and max_turn <= 15
                and all(n["lane_width"] >= 3.2 for n in nodes.values())
            )
            if not eligible:
                reason = "previously used site, junction, narrow lane, camera frustum or turn>15deg"
            row = dict(
                spawn_point_index=index,
                spawn_pose=pose(spawn),
                base_clearance_m=clearance,
                camera_pose=camera,
                nodes=nodes,
                max_turn_degrees=max_turn,
                eligible=eligible,
                reason=reason,
            )
        except ValueError as error:
            row = dict(
                spawn_point_index=index, eligible=False, reason=str(error), nodes=nodes
            )
        rows.append(row)
    try:
        selected = select_fresh(rows, used)
    except ValueError:
        selected = []
    report = dict(
        schema="m10-road-survey-v4",
        status="PASS" if len(selected) == 2 else "FAIL",
        client_version=client.get_client_version(),
        server_version=client.get_server_version(),
        map=road.name,
        xodr_sha256=hashlib.sha256(road.to_opendrive().encode()).hexdigest(),
        sites=rows,
        selected_sites=[s["spawn_point_index"] for s in selected],
        used_roads_sha256=hashlib.sha256(a.used_roads.read_bytes()).hexdigest(),
        selection="First eligible complete unused road sets >=50m from old and selected sites; no images/models",
        scope="Nearest driving-lane route and pinhole geometry; RGB/mask visibility remains mandatory at both selected sites",
    )
    (a.output / "survey.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            dict(
                status=report["status"],
                selected=report["selected_sites"],
                sites=len(rows),
            )
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

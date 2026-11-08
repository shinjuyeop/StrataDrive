#!/usr/bin/env python3
"""Read-only map screening at every planned site; no sensors, actors or models.

Nearest-lane elevation is a diagnostic proxy, not collision-mesh ground truth.
This post-v3 tool does not change the completed v3 plan or quality results.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path


def screen(base_z, base_lane_z, planned_z, z_offset, lane_z, projection_error):
    values = (base_z, base_lane_z, planned_z, z_offset, lane_z, projection_error)
    if (
        not all(type(v) in (int, float) and math.isfinite(v) for v in values)
        or projection_error < 0
    ):
        raise ValueError("finite geometry measurements")
    expected_clearance = base_z - base_lane_z + z_offset
    clearance_error = planned_z - lane_z - expected_clearance
    return dict(
        clearance_error_m=clearance_error,
        projection_error_m=projection_error,
        elevation_ok=abs(clearance_error) <= 0.15,
        projection_ok=projection_error <= 2.0,
        passed=abs(clearance_error) <= 0.15 and projection_error <= 2.0,
    )


def main():
    import carla

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--partition")  # Runner compatibility; all sites are checked.
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--port", type=int, default=2300)
    a = p.parse_args()
    plan = json.loads(a.plan.read_text())
    a.output.mkdir(parents=True, exist_ok=False)
    client = carla.Client("127.0.0.1", a.port)
    client.set_timeout(20)
    world = client.get_world()
    road = world.get_map()
    if road.name.rsplit("/", 1)[-1] != plan["map"]:
        raise ValueError("map identity")
    rows = []
    for part, settings in plan["partitions"].items():
        base = road.get_spawn_points()[settings["spawn_point_index"]]
        base_lane = road.get_waypoint(
            base.location, project_to_road=True, lane_type=carla.LaneType.Any
        )
        angle = math.radians(base.rotation.yaw)
        for case in settings["cases"]:
            for actor in case["actors"]:
                f, r = actor["forward_m"], actor["right_m"]
                target = carla.Location(
                    x=base.location.x + f * math.cos(angle) - r * math.sin(angle),
                    y=base.location.y + f * math.sin(angle) + r * math.cos(angle),
                    z=base.location.z + actor["z_offset_m"],
                )
                lane = road.get_waypoint(
                    target, project_to_road=True, lane_type=carla.LaneType.Any
                )
                position = lane.transform.location
                result = screen(
                    base.location.z,
                    base_lane.transform.location.z,
                    target.z,
                    actor["z_offset_m"],
                    position.z,
                    math.hypot(target.x - position.x, target.y - position.y),
                )
                rows.append(
                    dict(
                        partition=part,
                        scene=case["id"],
                        stratum=case["stratum"],
                        blueprint=actor["blueprint"],
                        role=actor["role"],
                        class_id=actor["class_id"],
                        planned_xyz=[target.x, target.y, target.z],
                        nearest_lane_xyz=[position.x, position.y, position.z],
                        road_id=lane.road_id,
                        lane_id=lane.lane_id,
                        lane_type=str(lane.lane_type),
                        **result,
                    )
                )
    report = dict(
        schema="m10-quality-site-geometry-v1",
        status="PASS" if all(r["passed"] for r in rows) else "FAIL",
        acquisition_status="PASS",
        plan_sha256=hashlib.sha256(a.plan.read_bytes()).hexdigest(),
        client_version=client.get_client_version(),
        server_version=client.get_server_version(),
        xodr_sha256=hashlib.sha256(road.to_opendrive().encode()).hexdigest(),
        actors=len(rows),
        elevation_failures=sum(not r["elevation_ok"] for r in rows),
        projection_failures=sum(not r["projection_ok"] for r in rows),
        rows=rows,
        scope="Post-hoc map-only screen at every final site; no changes to v3 scores; lane projection is not exact mesh ground or proof of visibility",
    )
    (a.output / "capture.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "status",
                    "actors",
                    "elevation_failures",
                    "projection_failures",
                )
            }
        )
    )
    return 0  # Acquisition succeeded; screen FAIL is retained in its own field.


if __name__ == "__main__":
    raise SystemExit(main())

"""Map-only next unused complete routes; no images, annotations or model inputs."""

import math
from quality_geometry_v4 import route_eligible


def select_fresh(sites, used):
    if used["schema"] != "m10-used-map-roads-v9" or used["map"] != "Town04_Opt":
        raise ValueError("map-specific used-road descriptor")
    roads = set(used["route_road_ids"])
    origins = list(used["route_origins"])
    selected = []
    for site in sorted(sites, key=lambda row: row["spawn_point_index"]):
        if not route_eligible(site):
            continue
        route_roads = {node["road_id"] for node in site["nodes"].values()}
        origin = site["nodes"]["0"]["pose"]["location"]
        if roads.intersection(route_roads) or any(
            math.dist(
                [origin[k] for k in ("x", "y", "z")],
                [previous[k] for k in ("x", "y", "z")],
            )
            < 50
            for previous in origins
        ):
            continue
        selected.append(site)
        roads.update(route_roads)
        origins.append(origin)
        if len(selected) == 2:
            return selected
    raise ValueError("two fresh separated map-only routes required")

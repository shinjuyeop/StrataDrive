"""Frozen M8 curve fixture and original ActorSnapshot rear-axle conversion."""
import json
import math
from pathlib import Path

REAR = [-1.3886322021484376, 7.6293945e-8, .3595409393310547]


def load_route(path):
    r = json.loads(Path(path).read_text())
    if (r['schema'] != 'm8-curve30-v1' or r['map'] != 'Town04_Opt'
            or r['completion_m'] != 300 or r['ticks'] != 6000
            or r['rear_axle_actor_m'] != REAR
            or len(r['xodr_sha256']) != 64 or len(r['points']) != 721):
        raise ValueError('route contract')
    previous = None
    for p in r['points']:
        if (not all(math.isfinite(p[k]) for k in ('x','y','z','yaw','pitch','width'))
                or p['junction'] or p['width'] < 3 or p['lane'] != -1):
            raise ValueError('route point')
        if previous:
            d = math.hypot(p['x']-previous['x'], p['y']-previous['y'])
            turn = math.atan2(math.sin(math.radians(p['yaw']-previous['yaw'])),
                              math.cos(math.radians(p['yaw']-previous['yaw'])))
            if not .48 < d < .53 or abs(turn)/d > .008:
                raise ValueError('route spacing/curvature')
        previous = p
    return r


def pose_from_snapshot(transform, route, carla):
    x,y,z = route['rear_axle_actor_m']
    rear = transform.transform(carla.Location(x=x,y=y,z=z))
    yaw = -math.radians(transform.rotation.yaw)
    return dict(x_m=rear.x,y_m=-rear.y,yaw_rad=math.atan2(math.sin(yaw),math.cos(yaw)))

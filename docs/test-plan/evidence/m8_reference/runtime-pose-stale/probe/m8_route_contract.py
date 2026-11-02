"""Frozen M8 curve fixture and original ActorSnapshot rear-axle conversion."""
import json
import math
import hashlib
from pathlib import Path

REAR = [-1.3886322021484376, 7.6293945e-8, .3595409393310547]


def load_route(path):
    r = json.loads(Path(path).read_text())
    reference = r['schema'] in ('m8-reference-v1','m8-reference-v2')
    v2 = r['schema']=='m8-reference-v2'
    scenario = r.get('scenario') if reference else 'S02'
    contracts = {'S01': (300,6000,721,'d4a00933dacfabc7574a1737b2e602b57fed19eb16f5ec8b0a900af61c84e533'),
                 'S03': (345,8000,679,'9403807df84667d8f4364e8e0a1e5bdce86b6f302f0da053cfb999e7068b45d5')}
    if v2:contracts={'S03':(395,8000,779,'696f12a9bfc128958f73f8d0da17f1a7ad265dc5e27c611760f023cdfd387638')}
    if reference and (scenario not in contracts or
            hashlib.sha256(Path(path).read_bytes()).hexdigest()!=contracts[scenario][3]):
        raise ValueError('frozen reference identity')
    completion,ticks,size = contracts[scenario][:3] if reference else (300,6000,721)
    if (r['schema'] not in ('m8-curve30-v1','m8-reference-v1','m8-reference-v2')
            or r['map'] != ('Town06_Opt' if reference else 'Town04_Opt')
            or r['completion_m'] != completion or r['ticks'] != ticks
            or r['rear_axle_actor_m'] != REAR
            or len(r['xodr_sha256']) != 64 or len(r['points']) != size):
        raise ValueError('route contract')
    previous = None
    for p in r['points']:
        if (not all(math.isfinite(p[k]) for k in ('x','y','z','yaw','pitch','width'))
                or p['junction'] or p['width'] < 3
                or (reference and p['lane_type'] != 'Driving')
                or (not reference and p['lane'] != -1)):
            raise ValueError('route point')
        if previous:
            d = math.hypot(p['x']-previous['x'], p['y']-previous['y'])
            turn = math.atan2(math.sin(math.radians(p['yaw']-previous['yaw'])),
                              math.cos(math.radians(p['yaw']-previous['yaw'])))
            upper_spacing = .75 if scenario=='S03' else .53
            max_curvature = {'S01':1e-5,'S02':.008,'S03':.0225}[scenario]
            if not .48 < d < upper_spacing or abs(turn)/d > max_curvature:
                raise ValueError('route spacing/curvature')
        previous = p
    return r


def pose_from_snapshot(transform, route, carla):
    x,y,z = route['rear_axle_actor_m']
    rear = transform.transform(carla.Location(x=x,y=y,z=z))
    yaw = -math.radians(transform.rotation.yaw)
    return dict(x_m=rear.x,y_m=-rear.y,yaw_rad=math.atan2(math.sin(yaw),math.cos(yaw)))

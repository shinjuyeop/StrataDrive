#!/usr/bin/env python3
"""Generate the preselected non-junction curve from the local CARLA OpenDRIVE."""
import argparse
import hashlib
import json
import carla
from m8_route_contract import REAR, load_route

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('xodr');p.add_argument('output');a=p.parse_args()
from pathlib import Path
source=Path(a.xodr).read_bytes()
world=carla.Map('Town04_Opt',source.decode())
w=world.get_waypoint(carla.Location(x=-503.7298889160156,y=177.5872344970703,z=0))
points=[]
for i in range(721):
    t=w.transform
    points.append(dict(x=t.location.x,y=t.location.y,z=t.location.z,yaw=t.rotation.yaw,
                       pitch=t.rotation.pitch,road=w.road_id,lane=w.lane_id,width=w.lane_width,junction=w.is_junction))
    if i<720:
        successors=w.next(.5)
        if len(successors)!=1:raise ValueError('route branches')
        w=successors[0]
out=Path(a.output)
with out.open('x') as f:
    json.dump(dict(schema='m8-curve30-v1',map='Town04_Opt',xodr_sha256=hashlib.sha256(source).hexdigest(),
                   completion_m=300,ticks=6000,rear_axle_actor_m=REAR,points=points),f,indent=2)
    f.write('\n')
load_route(out)
print(json.dumps(dict(path=str(out),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),points=len(points))))

#!/usr/bin/env python3
"""Freeze Town06 driving-lane S01/S03 fixtures from the installed OpenDRIVE."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import carla
from m8_route_contract import REAR

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('xodr',type=Path);p.add_argument('scenario',choices=['S01','S03']);p.add_argument('output',type=Path)
p.add_argument('--revision',choices=['v1','v2'],default='v1')
a=p.parse_args()
if a.revision=='v2' and a.scenario!='S03':raise ValueError('v2 is S03 only')
source=a.xodr.read_bytes();world=carla.Map('Town06_Opt',source.decode())
w=world.get_waypoint_xodr(40,-7,50 if a.scenario=='S01' else 190 if a.revision=='v2' else 240)
points=[];distance=0;previous=None
while True:
    t=w.transform
    if w.is_junction or w.lane_type!=carla.LaneType.Driving:raise ValueError('non-driving/junction')
    if previous:distance+=math.hypot(t.location.x-previous.location.x,t.location.y-previous.location.y)
    points.append(dict(x=t.location.x,y=t.location.y,z=t.location.z,yaw=t.rotation.yaw,
        pitch=t.rotation.pitch,road=w.road_id,lane=w.lane_id,width=w.lane_width,junction=False,lane_type='Driving'))
    if distance>= (360 if a.scenario=='S01' else 408 if a.revision=='v2' else 358):break
    successors=w.next(.5)
    if len(successors)!=1:raise ValueError('branch')
    previous=t;w=successors[0]
r=dict(schema='m8-reference-'+a.revision,scenario=a.scenario,map='Town06_Opt',
       xodr_sha256=hashlib.sha256(source).hexdigest(),rear_axle_actor_m=REAR,
       ticks=6000 if a.scenario=='S01' else 8000,completion_m=300 if a.scenario=='S01' else 395 if a.revision=='v2' else 345,points=points)
with a.output.open('x') as f:json.dump(r,f,indent=2);f.write('\n')
print(json.dumps(dict(scenario=a.scenario,points=len(points),length_m=distance,sha256=hashlib.sha256(a.output.read_bytes()).hexdigest())))

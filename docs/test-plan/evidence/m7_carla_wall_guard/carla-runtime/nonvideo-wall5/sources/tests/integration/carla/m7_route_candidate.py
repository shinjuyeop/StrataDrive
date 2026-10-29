#!/usr/bin/env python3
"""Read-only deterministic M7 map candidate. M8 route/speed suitability remains untested."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import carla


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--xodr',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():raise FileExistsError(a.output)
    m=carla.Map('Town03_Opt',a.xodr.read_text())
    w=m.get_waypoint(carla.Location(x=220.40966796875,y=-5.085507869720459,z=.27530714869499207))
    rows=[]
    for i in range(61):
        t=w.transform
        rows.append(dict(s_m=i*2,road=w.road_id,lane=w.lane_id,junction=w.is_junction,
                         x=t.location.x,y=t.location.y,z=t.location.z,yaw_deg=t.rotation.yaw,lane_width_m=w.lane_width))
        following=w.next(2.)
        if not following or any(q.is_junction for q in following):break
        w=min(following,key=lambda q:abs((q.transform.rotation.yaw-t.rotation.yaw+180)%360-180))
    for start,end in zip(rows,rows[1:]):
        start['curvature_estimate_1_m']=math.radians((end['yaw_deg']-start['yaw_deg']+180)%360-180)/2
    result=dict(schema='m7-route-candidate-v1',map='Town03_Opt',xodr_sha256=hashlib.sha256(a.xodr.read_bytes()).hexdigest(),
                step_m=2,waypoints=rows,scope='M7 frozen candidate; M8 30km/h suitability NOT RUN',
                signal_interaction='excluded; stops before first junction',randomness='none; nearest heading branch, no TrafficManager',
                units='UE x forward/y right/z up; position m, yaw deg')
    a.output.write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()

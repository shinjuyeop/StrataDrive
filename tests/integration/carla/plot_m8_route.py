#!/usr/bin/env python3
"""Plot original snapshot geometry and body speed, independently of controller errors."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from evidence_io import json_rows
from m8_route_oracle import RouteOracle, rear_pose
from audit_m8_route import target
from m8_reference_oracle import Reference

p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path)
p.add_argument('--output',type=Path,required=True);a=p.parse_args()
r=json.loads((a.directory/'result.json').read_text())['route_profile']['definition'];route=RouteOracle(r)
origin=None;data=[];reference=Reference(r['scenario'],r['schema'].rsplit('-',1)[-1]) if r['schema'].startswith('m8-reference-') else None
for row in json_rows(a.directory/'trace.jsonl'):
    s=row.get('native',{}).get('speed_control')
    if s:
        origin=s['origin_ns']
        if reference:reference.observe(s['release_ns']-origin,row['native']['lateral_control']['progress_m'])
    if row['index']%5 or not row.get('vehicle_state',{}).get('valid'):continue
    pose=rear_pose(row['vehicle_state'],r['rear_axle_actor_m']);q=route.project(pose)
    data.append((round(row['simulation_seconds']*1e9),pose,q,row['physics']['body_forward_velocity_m_s']))
data=[((ns-origin)*1e-9,p,q,v) for ns,p,q,v in data if ns>=origin]
fig,axes=plt.subplots(2,2,figsize=(12,8),constrained_layout=True)
ax=axes[0,0];ax.plot(*zip(*route.points),label='Frozen route',color='black',linestyle='--')
ax.plot([p['x_m'] for _,p,_,_ in data],[p['y_m'] for _,p,_,_ in data],label='Original rear axle')
ax.set(xlabel='Project world x (m)',ylabel='Project world y, left positive (m)',title=r['map']+' '+r.get('scenario','S02'));ax.axis('equal');ax.legend()
t=[x[0] for x in data]
axes[0,1].plot(t,[(reference.target(x) if reference else target(x))*3.6 for x in t],label='Target',linestyle='--')
axes[0,1].plot(t,[v*3.6 for _,_,_,v in data],label='Body forward');axes[0,1].set(ylabel='Speed (km/h)',xlabel='Control time (s)');axes[0,1].legend()
axes[1,0].plot(t,[q['cross_track_m'] for _,_,q,_ in data]);axes[1,0].set(xlabel='Control time (s)',ylabel='Signed cross-track error (m)')
import math
axes[1,1].plot(t,[math.degrees(q['heading_error_rad']) for _,_,q,_ in data]);axes[1,1].set(xlabel='Control time (s)',ylabel='Signed heading error (deg)')
if reference and reference.scenario=='S03':
    for ns,label in [(reference.slow_ns,'20 km/h request'),(reference.stop_ns,'Stop request')]:
        axes[0,1].axvline(ns*1e-9,color='gray',alpha=.5,label=label)
    axes[0,1].legend()
for ax in axes.flat:ax.grid(alpha=.25)
fig.savefig(a.output,dpi=150)

"""Independent fixed STOP30 geometry, pose/control lineage and plateau audit."""
import hashlib
import json
import math
from audit_m7_1q_native import check, frame, wire
from evidence_io import json_rows
from m8_route_contract import load_route
from m8_route_oracle import RouteOracle, rear_pose, pursuit


def plateau_samples(samples, physics, origin):
    # PI stops at35s before consuming the last pre-event acquisition. Sample
    # the original100Hz Drive Actual, not the truncated list of PI consumers.
    bins={}
    for source,omega in sorted(samples.items()):
        elapsed=source-origin-25000000000
        if not 0<=elapsed<10000000000:continue
        check(source in physics and abs(omega-physics[source])<=.005+1e-12,'stop30 original plateau wheel')
        bins.setdefault(elapsed//20000000,[]).append(omega)
    check(set(bins)==set(range(500)) and all(len(v)==2 for v in bins.values()),'complete stop30 wheel acquisition grid')
    return [abs(v[0]*.355*3.6-30) for _,v in sorted(bins.items())]


def audit_route(directory, rows=None):
    result=json.loads((directory/'result.json').read_text())
    frozen=directory/'frozen-route.json';definition=load_route(frozen)
    check(definition['schema']=='m8-normal-stop30-v1' and result['execution_profile']==definition['schema'] and
          definition==result['route_profile']['definition'] and hashlib.sha256(frozen.read_bytes()).hexdigest()==result['route_profile']['sha256'],'frozen stop30 identity')
    check(not result['speed_loop'] and not result['propulsion_aware'] and result['continuous_simulation'] and result['fault']=='none','stop30 nominal scope')
    check(result['route_fixture']['opendrive_sha256']==definition['xodr_sha256'],'original stop30 map')
    route=RouteOracle(definition);poses={};controls={};laterals={};body=[];wheel_sources={};physics={};states=[]
    origin=None;angle=progress=pose_progress=0.;final=None
    for row in json_rows(directory/'trace.jsonl') if rows is None else rows:
        ns=math.floor(row['simulation_seconds']*1e9+.5);n=row['native'];pose=row['route_pose'];state=row['vehicle_state']
        check(state['valid'] and state['frame']==row['frame'] and state['timestamp']==row['simulation_seconds'] and state['source_identity']=='CARLA.ActorSnapshot','stop30 original snapshot')
        raw=rear_pose(state,definition['rear_axle_actor_m'])
        check(pose['epoch']==42 and pose['actor']==int(result['binding']['actor']) and pose['frame']==row['frame'] and pose['source_ns']==ns,'stop30 pose identity')
        check(all(abs(pose[k]-raw[k])<5e-5 for k in ('x_m','y_m','yaw_rad')),'stop30 rear axle conversion')
        fields=row['pose_input'].split()
        check(fields[:5]==['POSE',str(pose['actor']),'42',str(row['frame']),str(ns)] and len(fields)==8 and
              [float(v) for v in fields[5:]]==[pose[k] for k in ('x_m','y_m','yaw_rad')],'stop30 original pose input')
        physics[ns]=sum(w['solver_omega_rad_s'] for w in row['physics']['wheels'][2:])/2
        packet=n['native_export']['actual'][2]
        if packet:
            actual=frame(wire(packet,1,7,9),2,True,require_wheel=False)
            if actual['wheel_valid']:
                source=actual['wheel_source'];value=actual['wheel']
                check(source not in wheel_sources or wheel_sources[source]==value,'stop30 immutable wheel acquisition')
                wheel_sources[source]=value
        poses[ns]=pose;q=route.project(raw,pose_progress);pose_progress=max(pose_progress,q['progress_m']);final=q
        s=n.get('speed_control')
        if s:
            seq=s['sequence'];origin=s['origin_ns']
            if seq in controls:check(s==controls[seq] and n['lateral_control']==laterals[seq],'stop30 held PI/lateral state')
            else:
                l=n['lateral_control'];source=l['source_ns']
                check(source in poses and 0<=s['release_ns']-source<=30000000,'stop30 current pose source')
                expected,angle,progress=pursuit(route,poses[source],s['speed_mps'],angle,progress)
                check(all(abs(l[k]-v)<1e-9 for k,v in expected.items()),'stop30 independent pursuit')
                check(seq==len(controls) and s['release_ns']<origin+35000000000,'stop30 control sequence')
                controls[seq]=dict(s);laterals[seq]=dict(l)
        if origin:
            elapsed=ns-origin
            if 25000000000<=elapsed<35000000000:body.append(abs(row['physics']['body_forward_velocity_m_s']*3.6-30))
            if row['index']%5==0 and 0<=elapsed<=45000000000:states.append(q)
            proof=n['native_export']
            if proof['normal']:
                for role,packet in enumerate(proof['commands']):
                    decoder=wire(packet,0 if role<2 else 1,role+2,5);decoder.get('IQQQI');frame(decoder,role,False)
                    check(decoder.get('B')==1,'stop30 child context')
                    epoch,seq,source,expiry,accel,curvature,braking,hold=decoder.get('IIQQdddB');oldest,child_expiry=decoder.get('QQ')
                    if source<origin+35000000000:
                        check(seq in controls,'stop30 computed parent');c=controls[seq];l=laterals[seq]
                        check(epoch==42 and source==c['release_ns'] and expiry==c['expiry_ns'] and accel==c['acceleration_mps2'] and curvature==l['curvature_inv_m'] and braking==0 and hold==(c['target_mps']==0),'stop30 unchanged computed request')
                        check(oldest<=min(c['source_ns'],l['source_ns']) and child_expiry<=c['input_expiry_ns'],'stop30 preserved pose/wheel dependency')
                    else:check(accel in (-1,0) and curvature==0 and braking==0 and hold,'stop30 original fixed deceleration request')
    wheel=plateau_samples(wheel_sources,physics,origin)
    check(len(controls)==1750 and len(body)==1000 and len(wheel)==500,'complete stop30 plateau')
    check(max(body)<=.5 and max(wheel)<=.5,'stop30 plateau performance')
    check(states and 240<=final['progress_m']<=270,'stop30 final stationary corridor')
    rank=math.ceil(.95*len(states))-1
    cross=sorted(abs(q['cross_track_m']) for q in states)[rank]
    heading=sorted(abs(math.degrees(q['heading_error_rad'])) for q in states)[rank]
    check(cross<=.3 and heading<=3,'stop30 geometry performance')
    return dict(original_wheel_acquisitions=1000,body_plateau_samples=len(body),wheel_plateau_samples=len(wheel),body_max_error_kmh=max(body),wheel_max_error_kmh=max(wheel),
                trajectory_samples=len(states),cross_track_p95_m=cross,heading_p95_deg=heading,final_progress_m=final['progress_m'])

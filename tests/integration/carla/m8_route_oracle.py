"""Independent double-precision rear-axle and polyline calculations; no CARLA SDK."""
import bisect
import math
from audit_m7_1q_native import check


def wrap(x):
    return math.atan2(math.sin(x),math.cos(x))


def rear_pose(state, offset):
    roll,pitch,yaw=map(math.radians,state['rotation_ue_deg'])
    sr,cr,sp,cp,sy,cy=math.sin(roll),math.cos(roll),math.sin(pitch),math.cos(pitch),math.sin(yaw),math.cos(yaw)
    x,y,z=offset;px,py,_=state['position_ue_m']
    return dict(x_m=px+x*cp*cy+y*(cy*sp*sr-sy*cr)+z*(-cy*sp*cr-sy*sr),
                y_m=-(py+x*cp*sy+y*(sy*sp*sr+cy*cr)+z*(-sy*sp*cr+cy*sr)),yaw_rad=wrap(-yaw))


class RouteOracle:
    def __init__(self,definition):
        self.points=[(p['x'],-p['y']) for p in definition['points']]
        self.segments=[];self.distances=[0.]
        for a,b,pa,pb in zip(self.points,self.points[1:],definition['points'],definition['points'][1:]):
            dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
            self.segments.append((a[0],a[1],dx,dy,length,self.distances[-1],abs(wrap(math.radians(pb['yaw']-pa['yaw'])))/length))
            self.distances.append(self.distances[-1]+length)

    def project(self,p,progress=None):
        best=None
        for x,y,dx,dy,length,s,curvature in self.segments:
            if progress is not None and (s+length<progress-2 or s>progress+20):continue
            u=max(0.,min(1.,((p['x_m']-x)*dx+(p['y_m']-y)*dy)/(length*length)))
            ex,ey=p['x_m']-x-u*dx,p['y_m']-y-u*dy
            d=math.hypot(ex,ey)
            if best is None or d<best['distance']:
                best=dict(distance=d,progress_m=s+u*length,cross_track_m=(dx*ey-dy*ex)/length,
                          heading_error_rad=wrap(p['yaw_rad']-math.atan2(dy,dx)),route_curvature=curvature)
        check(best is not None,'projection exists')
        return best

    def point(self,s):
        i=max(0,bisect.bisect_left(self.distances,s,1)-1)
        x,y,dx,dy,length,start,_=self.segments[i]
        u=(s-start)/length
        return x+u*dx,y+u*dy


def pursuit(route,p,speed,angle,progress):
    q=route.project(p,progress);lookahead=max(4.,1.2*speed)
    x,y=route.point(min(route.distances[-1],q['progress_m']+lookahead))
    dx,dy=x-p['x_m'],y-p['y_m']
    local_y=-math.sin(p['yaw_rad'])*dx+math.cos(p['yaw_rad'])*dy
    wanted=math.atan(2.860470886230469*2*local_y/(dx*dx+dy*dy))
    selected=max(angle-.02,min(angle+.02,max(-.3,min(.3,wanted))))
    expected={k:q[k] for k in ('progress_m','cross_track_m','heading_error_rad')}
    expected.update(lookahead_m=lookahead,curvature_inv_m=math.tan(selected)/2.860470886230469)
    return expected,selected,max(progress,q['progress_m'])


def route_metrics(states,origin,completion):
    reached=next(((i,ns,q) for i,ns,q in states if ns>=origin and q['progress_m']>=completion),None)
    check(reached is not None,'completion marker reached')
    sampled=[(i,ns,q) for i,ns,q in states if i%5==0 and ns>=origin and i<=reached[0]]
    check(sampled and all(b[0]-a[0]==5 for a,b in zip(sampled,sampled[1:])),'complete 20Hz trajectory')
    plateau=[q for _,ns,q in sampled if 25<=(ns-origin)*1e-9<35]
    check(len(plateau)==200 and min(q['route_curvature'] for q in plateau)>=.001,'10s curved plateau')
    rank=math.ceil(.95*len(sampled))-1
    cross=sorted(abs(q['cross_track_m']) for _,_,q in sampled)
    heading=sorted(abs(math.degrees(q['heading_error_rad'])) for _,_,q in sampled)
    return dict(samples=len(sampled),missing_samples=0,first_index=sampled[0][0],last_index=sampled[-1][0],
                completion_index=reached[0],completion_seconds=(reached[1]-origin)*1e-9,
                plateau_samples=len(plateau),cross_track_p95_m=cross[rank],heading_p95_deg=heading[rank],
                cross_track_max_m=max(cross),heading_max_deg=max(heading))

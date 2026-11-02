"""Independent S01/S03 reference timeline and complete-window measurements.

Events are reconstructed from original pose and control releases, never from
recorded request markers. No production profile or CARLA SDK is imported.
"""
import math
from audit_m7_1q_native import check


class Reference:
    def __init__(self,scenario,revision='v1'):
        check(scenario in ('S01','S03'),'known reference scenario')
        check(revision in ('v1','v2') and (revision=='v1' or scenario=='S03'),'known reference revision')
        self.scenario=scenario;self.revision=revision
        self.offset=50 if revision=='v2' else 0
        self.ramp=20 if revision=='v2' else 10
        self.slow_ns=self.stop_ns=None

    def observe(self,elapsed_ns,projection):
        if self.scenario=='S03':
            if self.slow_ns is None and projection>=180+self.offset:self.slow_ns=elapsed_ns
            if self.slow_ns is not None and self.stop_ns is None and projection>=330+self.offset:self.stop_ns=elapsed_ns
        return self.target(elapsed_ns*1e-9)

    def target(self,t):
        if t<0:return 0.
        if self.scenario=='S01':
            return min(30.,max(0.,min(1.5*t,30.-2.*(t-40))))/3.6
        if self.stop_ns is not None and t>=self.stop_ns*1e-9:
            return max(0.,20.-2.5*(t-self.stop_ns*1e-9))/3.6
        if self.slow_ns is not None and t>=self.slow_ns*1e-9:
            return max(20.,30.-(10./6.)*(t-self.slow_ns*1e-9))/3.6
        return min(30.,30.*t/self.ramp)/3.6

    def record(self,t):
        return dict(requested_mps=(0. if self.stop_ns is not None else 20/3.6 if self.slow_ns is not None else 30/3.6)
                    if self.scenario=='S03' else self.target(t),
                    slow_elapsed_ns=self.slow_ns,stop_elapsed_ns=self.stop_ns)

    def windows(self):
        if self.scenario=='S01':return [(25.,35.,30.)],(57.,59.)
        check(self.slow_ns is not None and self.stop_ns is not None,'both position markers reached')
        slow,stop=self.slow_ns*1e-9,self.stop_ns*1e-9
        check(slow>=self.ramp+15 and stop>=slow+21,'plateaus precede next position request')
        return [(self.ramp+5.,self.ramp+15.,30.),(slow+11,slow+21,20.)],(stop+10,stop+12)

    def metrics(self,samples,plateau_n,stop_n):
        windows,stop=self.windows();plateaus=[]
        for begin,end,speed in windows:
            values=[abs(v*3.6-speed) for t,v in samples if begin<=t<end]
            check(len(values)==plateau_n,'complete reference plateau')
            plateaus.append(dict(begin_s=begin,end_s=end,target_kmh=speed,samples=len(values),max_error_kmh=max(values)))
        stopped=[abs(v)*3.6 for t,v in samples if stop[0]<=t<stop[1]]
        over=[max(0.,(v/self.target(t)-1)*100) for t,v in samples if self.target(t)>0]
        check(len(stopped)==stop_n and over,'complete reference stop')
        return dict(samples=len(samples),plateaus=plateaus,stop_samples=len(stopped),
            max_plateau_error_kmh=max(p['max_error_kmh'] for p in plateaus),max_stop_error_kmh=max(stopped),
            max_positive_target_overspeed_percent=max(over),
            max_tracking_error_kmh=max(abs(v-self.target(t))*3.6 for t,v in samples if t>=0))

    def route_metrics(self,states,origin,completion,body):
        reached=next(((i,ns,q) for i,ns,q in states if ns>=origin and q['progress_m']>=completion),None)
        check(reached is not None,'completion marker reached')
        sampled=[(i,ns,q) for i,ns,q in states if i%5==0 and ns>=origin and i<=reached[0]]
        check(sampled and all(b[0]-a[0]==5 for a,b in zip(sampled,sampled[1:])),'complete 20Hz trajectory')
        plateaus,_=self.windows();counts=[]
        for index,(begin,end,_) in enumerate(plateaus):
            values=[q['route_curvature'] for _,ns,q in sampled if begin<=(ns-origin)*1e-9<end]
            check(len(values)==200,'complete 20Hz reference plateau')
            check(min(values)>=.001 if index else max(values)<=1e-5,'reference plateau geometry')
            counts.append(len(values))
        check(reached[2]['route_curvature']<=1e-5,'completion on final straight')
        rank=math.ceil(.95*len(sampled))-1
        cross=sorted(abs(q['cross_track_m']) for _,_,q in sampled)
        heading=sorted(abs(math.degrees(q['heading_error_rad'])) for _,_,q in sampled)
        result=dict(samples=len(sampled),missing_samples=0,first_index=sampled[0][0],last_index=sampled[-1][0],
            completion_index=reached[0],completion_seconds=(reached[1]-origin)*1e-9,plateau_samples=counts,
            cross_track_p95_m=cross[rank],heading_p95_deg=heading[rank],cross_track_max_m=max(cross),heading_max_deg=max(heading))
        if self.scenario=='S01':
            check(all(q['route_curvature']<=1e-5 for _,_,q in sampled),'entire S01 straight')
        else:
            entry=next((i,ns,q) for i,ns,q in states if ns>=origin and q['route_curvature']>=.001)
            speed=dict(body)[entry[1]]*3.6
            check(abs(speed-20)<=1,'curve entry speed')
            result.update(curve_entry_speed_kmh=speed,curve_entry_seconds=(entry[1]-origin)*1e-9)
        return result

#!/usr/bin/env python3
"""Finite M6 MIL. Independent Python plant/actuator approximation; no SDK/ECU.
Reference is fixed before execution; writes all samples even when verdict fails.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
from model import SpeedPI, Sample

DT=.002
END=87.0
PLATEAUS=((20.,35.,30/3.6),(43.,58.,20/3.6),(72.,87.,0.))

def reference(t):
    if t<20:return (30/3.6)*t/20
    if t<35:return 30/3.6
    if t<43:return 30/3.6-(10/3.6)*(t-35)/8
    if t<58:return 20/3.6
    if t<72:return (20/3.6)*(72-t)/14
    return 0.

def approach(x,target,rate):return x+max(-rate*DT,min(rate*DT,target-x))

def simulate():
    controller=SpeedPI();controller.initialize(1)
    speed=torque=pressure=0.;sample=None;accel=0.;rows=[];pending=[]
    target_torque=target_pressure=0.;active_torque=active_pressure=0.
    for tick in range(round(END/DT)+1):
        ns=tick*2_000_000;t=tick*DT
        if tick%25==0:sample=Sample(1,tick//25,ns,speed)
        if tick%10==0:
            out=controller.step(ns,reference(t),sample,True)
            if not out.valid:raise ValueError(out.reason)
            accel=out.acceleration
            wheel=accel*1000*.3
            target_torque=max(-200.,min(300.,wheel)) if speed/.3>=2 or wheel>=0 else 0.
            target_pressure=max(0.,-wheel+min(0.,target_torque))/.001
            target_pressure=min(1500000.,target_pressure)
            pending.append((tick+25,target_torque,target_pressure))
        while pending and pending[0][0]<=tick:
            _,active_torque,active_pressure=pending.pop(0)
        if tick%25==0:
            rows.append({'time_s':t,'reference_mps':reference(t),'speed_mps':speed,'acceleration_demand':accel,'integral':controller.integral,'torque_nm':torque,'pressure_pa':pressure,'speed_source_ns':sample.source_ns,'control_speed_source_ns':controller.sample.source_ns})
        if tick==round(END/DT):break
        # Vehicle force from actual actuator values at BEGIN, never from demand.
        force=(torque-pressure*.001)/.3-100-.4*speed*speed
        speed=max(0.,speed+force/1000*DT)
        torque=approach(torque,active_torque,1000.)
        pressure=approach(pressure,active_pressure,5000000. if active_pressure>pressure else 10000000.)
    return rows

def judge(rows):
    errors=[];plateaus=[]
    if len(rows)!=1741 or any(abs(r['time_s']-i*.05)>1e-9 for i,r in enumerate(rows)):errors.append('missing/off-grid samples')
    for begin,end,target in PLATEAUS:
        window=[r for r in rows if begin+5<=r['time_s']<end]
        maximum=max(abs(r['speed_mps']-target)*3.6 for r in window) if window else math.inf
        plateaus.append({'begin_s':begin,'end_s':end,'samples':len(window),'max_error_kph':maximum})
        if len(window)!=200 or maximum>1:errors.append(f'plateau {begin}: error/sample count')
    ratios=[max(0.,r['speed_mps']-r['reference_mps'])/r['reference_mps'] for r in rows if r['reference_mps']>0]
    overspeed=max(ratios)
    if overspeed>.1:errors.append('positive-reference overspeed')
    if not all(-5<=r['acceleration_demand']<=2 and all(math.isfinite(v) for v in r.values()) for r in rows):errors.append('bounds/finite')
    return {'pass':not errors,'errors':errors,'plateaus':plateaus,'max_positive_overspeed_ratio':overspeed,'samples':len(rows)}

def main():
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    metadata={'model':'m6-pi-v1','python':platform.python_version(),'clock':'logical','dt_s':DT,'controller_period_s':.02,'sensor_period_s':.05,'duration_s':END,'parameters':{k:getattr(SpeedPI,k) for k in ('kp','ki','low','high','slew','max_age_ns')},'sources':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in Path(__file__).parent.glob('*.py')}}
    (a.output/'plan.json').write_text(json.dumps(metadata,indent=2)+'\n')
    try:
        rows=simulate()
        with (a.output/'samples.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        result=judge(rows)
    except Exception as e:result={'pass':False,'errors':[repr(e)]}
    (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));return 0 if result['pass'] else 1
if __name__=='__main__':sys.exit(main())

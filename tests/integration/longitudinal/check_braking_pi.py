#!/usr/bin/env python3
"""Independent v3/C++ directional anti-windup replay; synthetic plant only."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import uuid
from check_equivalence import compare_records, read_records
from check_propulsion_pi import replay as replay_v2
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'models/longitudinal'))
from model_v3 import SpeedPI,Sample


def replay(text):
    rows=[];c=None;name=None
    for i,line in enumerate(text.splitlines()):
        f=line.split();op=f[0];accepted=out=None
        if op=='new':name=f[1];c=SpeedPI()
        elif op=='init':accepted=c.initialize(int(f[1]))
        else:
            x=Sample(int(f[5]),int(f[6]),int(f[7]),float(f[8])) if f[4]=='1' else None
            out=asdict(c.step(int(f[1]),float(f[2]),x,f[3]=='1',f[-2]=='1',f[-1]=='1'))
        state=dict(epoch=c.epoch,integral=c.integral,previous=c.previous,last_ns=c.last_ns,
            sample=asdict(c.sample) if c.sample else None,fault=c.fault,target=c.target)
        rows.append(dict(index=i,case=name,op=op,accepted=accepted,output=out,state=state))
    return rows


def vectors():
    rng=random.Random(803);lines=[]
    for name in ('braking','release','unwind','both','changing','fault','legacy'):
        lines+=['new '+name,'init 1']
        for i in range(1200):
            t=i*20000000;speed=1. if i<600 else 0.
            drive=name=='both';brake=name!='legacy'
            if name=='release' and i>=600:brake=False
            if name=='changing':drive=rng.random()<.5;brake=rng.random()<.5
            if name=='fault' and i==400:t+=1
            lines.append(f'step {t} 0.5 1 1 1 {i} {i*20000000} {speed} {int(drive)} {int(brake)}')
        lines+=['init 2','step 30000000000 0 1 1 2 0 30000000000 0 1 1']
    return '\n'.join(lines)+'\n'


def loop(aware):
    c=SpeedPI();c.initialize(1);speed=3.;limited=False;rows=[];lines=['new plant','init 1']
    # Declared synthetic longitudinal plant, constant +.08 m/s2 disturbance.
    # Brake capacity .12 for 15s, then 1.5; no CARLA/vehicle acceptance claim.
    for i in range(2500):
        t=i*.02;cap=.12 if t<15 else 1.5;flag=limited if aware else False
        lines.append(f'step {i*20000000} 2 1 1 1 {i} {i*20000000} {speed!r} 0 {int(flag)}')
        out=c.step(i*20000000,2.,Sample(1,i,i*20000000,speed),True,False,flag)
        demand=out.acceleration;selected=max(-cap,demand);limited=selected>demand
        speed=max(0.,speed+.02*(selected+.08))
        rows.append(dict(time_s=t,speed_mps=speed,acceleration=demand,selected=selected,integral=c.integral,limited=limited))
    return rows,'\n'.join(lines)+'\n'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('binary',type=Path);p.add_argument('--output-root',type=Path,required=True);a=p.parse_args()
    out=a.output_root/str(uuid.uuid4());out.mkdir(parents=True,exist_ok=False)
    def compare(name,source):
        (out/(name+'-input.txt')).write_text(source)
        run=subprocess.run([str(a.binary.resolve())],input=source,text=True,capture_output=True)
        (out/(name+'-cpp.jsonl')).write_text(run.stdout);(out/(name+'-stderr.txt')).write_text(run.stderr)
        if run.returncode:raise ValueError('C++ replay failed')
        expected=replay(source);(out/(name+'-python.jsonl')).write_text(''.join(json.dumps(r)+'\n' for r in expected))
        return compare_records(expected,read_records(run.stdout))
    source=vectors();comparison=compare('matrix',source)
    v2='\n'.join(line.rsplit(' ',1)[0] if line.startswith('step ') else line for line in source.splitlines())+'\n'
    off='\n'.join(line+' 0' if line.startswith('step ') else line for line in v2.splitlines())+'\n'
    compatibility=compare_records(replay_v2(v2),replay(off));compare('braking-disabled',off)
    measures={};plants={}
    for aware in (False,True):
        name='aware' if aware else 'legacy';rows,source=loop(aware);plants[name]=compare(name,source)
        (out/(name+'-plant.json')).write_text(json.dumps(rows))
        measures[name]=dict(min_speed_mps=min(r['speed_mps'] for r in rows),min_integral=min(r['integral'] for r in rows),final_speed_mps=rows[-1]['speed_mps'])
    old,new=measures['legacy'],measures['aware']
    if not (new['min_integral']>old['min_integral'] and new['min_speed_mps']>old['min_speed_mps'] and abs(new['final_speed_mps']-2)<.01):
        raise ValueError('synthetic braking recovery failed: '+repr(measures))
    result=dict(status='PASS_BRAKING_MODEL_EQUIVALENCE',comparison=comparison,v2_compatibility=compatibility,plants=plants,synthetic_plant=measures,
        model_sha256=hashlib.sha256((ROOT/'models/longitudinal/model_v3.py').read_bytes()).hexdigest(),binary_sha256=hashlib.sha256(a.binary.read_bytes()).hexdigest())
    (out/'verdict.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':main()

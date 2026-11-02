#!/usr/bin/env python3
"""Independent v2 model/C++ comparison and reproducible saturation/recovery plant."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import uuid
from check_equivalence import compare_records, read_records, python_replay
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'models/longitudinal'))
from model_v2 import SpeedPI,Sample


def replay(text):
    rows=[];c=None;name=None
    for i,line in enumerate(text.splitlines()):
        f=line.split();op=f[0];accepted=out=None
        if op=='new':name=f[1];c=SpeedPI()
        elif op=='init':accepted=c.initialize(int(f[1]))
        else:
            sample=Sample(int(f[5]),int(f[6]),int(f[7]),float(f[8])) if f[4]=='1' else None
            out=asdict(c.step(int(f[1]),float(f[2]),sample,f[3]=='1',f[-1]=='1'))
        state=dict(epoch=c.epoch,integral=c.integral,previous=c.previous,last_ns=c.last_ns,
            sample=asdict(c.sample) if c.sample else None,fault=c.fault,target=c.target)
        rows.append(dict(index=i,case=name,op=op,accepted=accepted,output=out,state=state))
    return rows


def vectors():
    rng=random.Random(801);lines=[]
    for name in ('clipped','recovery','unwind','changing_limits','faults','legacy'):
        lines += ['new '+name,'init 1']
        for i in range(1200):
            t=i*20000000;target=.8;speed=0. if i<600 else 1.
            sat=name!='legacy' and (name!='changing_limits' or rng.random()<.5)
            if name=='recovery' and i>=600:sat=False
            if name=='faults' and i==400:t+=1
            lines.append(f'step {t} {target!r} 1 1 1 {i} {i*20000000} {speed!r} {int(sat)}')
        lines += ['init 2','step 30000000000 0 1 1 2 0 30000000000 0 1']
    return '\n'.join(lines)+'\n'


def loop(aware):
    c=SpeedPI();c.initialize(1);speed=0.;limited=False;rows=[]
    # Explicit synthetic plant: 1 m/s target, capacity .12 for 15s, then 1.5.
    # It isolates downstream clipping; no CARLA/vehicle acceptance claim.
    for i in range(2500):
        t=i*.02;cap=.12 if t<15 else 1.5
        out=c.step(i*20000000,1.,Sample(1,i,i*20000000,speed),True,limited if aware else False)
        demand=out.acceleration;selected=min(demand,cap);limited=demand>selected
        speed=max(0.,speed+.02*(selected-.08*speed))
        rows.append(dict(time_s=t,target_mps=1.,speed_mps=speed,acceleration=demand,selected=selected,integral=c.integral,limited=limited))
    return rows


def main():
    p=argparse.ArgumentParser();p.add_argument('binary',type=Path)
    destination=p.add_mutually_exclusive_group(required=True)
    destination.add_argument('--output',type=Path);destination.add_argument('--output-root',type=Path);a=p.parse_args()
    if a.output_root:a.output=a.output_root/str(uuid.uuid4())
    a.output.mkdir(parents=True,exist_ok=False);text=vectors();(a.output/'input.txt').write_text(text)
    run=subprocess.run([str(a.binary.resolve())],input=text,text=True,capture_output=True)
    (a.output/'cpp.jsonl').write_text(run.stdout);(a.output/'stderr.txt').write_text(run.stderr)
    assert run.returncode==0
    expected=replay(text);(a.output/'python.jsonl').write_text(''.join(json.dumps(r,allow_nan=False)+'\n' for r in expected))
    comparison=compare_records(expected,read_records(run.stdout))
    # False external feedback must be numerically identical to frozen v1.
    off='\n'.join(line[:-2] if line.startswith('step ') else line for line in text.splitlines())+'\n'
    off_v2='\n'.join(line+' 0' if line.startswith('step ') else line for line in off.splitlines())+'\n'
    compatibility=compare_records(python_replay(off),replay(off_v2))
    legacy,aware=loop(False),loop(True)
    for name,data in [('legacy',legacy),('aware',aware)]:
        (a.output/(name+'-loop.json')).write_text(json.dumps(data))
    measure=lambda rows:dict(max_speed_mps=max(r['speed_mps'] for r in rows),max_integral=max(r['integral'] for r in rows),final_speed_mps=rows[-1]['speed_mps'])
    l,w=measure(legacy),measure(aware)
    assert w['max_integral']<l['max_integral'] and w['max_speed_mps']<l['max_speed_mps'] and abs(w['final_speed_mps']-1)<.01
    # Replay exactly the two independently simulated acquisitions through C++.
    for name,rows in [('legacy',legacy),('aware',aware)]:
        lines=['new plant_'+name,'init 1'];speed=0.;limited=False
        for i,r in enumerate(rows):
            lines.append(f'step {i*20000000} 1 1 1 1 {i} {i*20000000} {speed!r} {int(limited if name=="aware" else False)}')
            speed=r['speed_mps'];limited=r['limited']
        source='\n'.join(lines)+'\n';(a.output/(name+'-plant-input.txt')).write_text(source)
        result=subprocess.run([str(a.binary.resolve())],input=source,text=True,capture_output=True);assert result.returncode==0
        (a.output/(name+'-plant-cpp.jsonl')).write_text(result.stdout);compare_records(replay(source),read_records(result.stdout))
    verdict=dict(status='PASS_PROPULSION_MODEL_EQUIVALENCE',comparison=comparison,legacy_compatibility=compatibility,
        synthetic_plant=dict(legacy=l,aware=w),model_v1_sha256=hashlib.sha256((ROOT/'models/longitudinal/model.py').read_bytes()).hexdigest(),
        model_v2_sha256=hashlib.sha256((ROOT/'models/longitudinal/model_v2.py').read_bytes()).hexdigest(),binary_sha256=hashlib.sha256(a.binary.read_bytes()).hexdigest())
    (a.output/'verdict.json').write_text(json.dumps(verdict,indent=2)+'\n');print(json.dumps(dict(status=verdict['status'],events=comparison['events'],plant=verdict['synthetic_plant'])))


if __name__=='__main__':main()

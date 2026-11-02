#!/usr/bin/env python3
"""STOP30 frozen runner scope and native JSON prefix; no physics execution."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
from evidence_io import json_rows
from m8_route_contract import load_route
p=argparse.ArgumentParser();p.add_argument('binary',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=False)
base=Path(__file__).resolve().parent;route=base/'scenarios/m8_stop30_v1.json';definition=load_route(route)
header=a.output/'route.txt';header.write_text('PROFILE STOP30\n'+''.join(f"{p['x']:.17g} {-p['y']:.17g}\n" for p in definition['points']))
source=base.parents[2]/'docs/test-plan/evidence/m8_reference/S01-01'
# Discover the original S01 directory from the evidence result identity, not timestamps.
if not (source/'result.json').exists():
    candidates=[]
    for q in (base.parents[2]/'docs/test-plan/evidence/m8_reference').glob('*/result.json'):
        r=json.loads(q.read_text())
        if r.get('route_profile',{}).get('definition',{}).get('scenario')=='S01' and r['status'].startswith('PASS'):candidates.append(q.parent)
    assert len(candidates)==1;candidates.sort();source=candidates[0]
r=json.loads((source/'result.json').read_text());inputs=[]
for row in json_rows(source/'trace.jsonl'):
    if row['index']>=100:break
    if row.get('work_input'):inputs.append(row['work_input'])
    inputs.append(row['pose_input']);inputs.append(row['native_input'])
cmd=[str(a.binary.resolve()),'--native-solver-work','1','42','7',str(r['binding']['actor']),'--sim-horizon-ms','60000','--route',str(header)]
run=subprocess.run(cmd,input='\n'.join(inputs)+'\n',text=True,capture_output=True,timeout=30)
(a.output/'stderr.txt').write_text(run.stderr);assert run.returncode==0,run.stderr
rows=[json.loads(s) for s in run.stdout.splitlines()];assert len(rows)==100
for row in rows:
    assert row['stop_configuration']==definition['stop_configuration']
    assert row['speed_terminal']['mode']==4 and row['admission']['ok']
    assert len(row['native_export']['stop_requests'])==len(row['native_export']['stop_results'])==3
rejected={}
runner=[sys.executable,str(base/'m7_1o_run.py'),'--engine','/missing','--source','/missing','--python','/missing','--fixture','/missing','--native-actual',str(a.binary),'--runtime',str(a.output/'forbidden-runtime'),'--output',str(a.output/'forbidden-output'),'--route-profile',str(route),'--ticks','6000','--simulation-continuous','--solver-work']
for name,args in [('speed-loop',['--speed-loop']),('other-terminal',['--speed-terminal','normal-stop']),('propulsion-aware',['--propulsion-aware']),('other-fault',['--native-fault','pose-stale']),('wrong-ticks',['--ticks','4000']),('wall',['--wall-native'])]:
    bad=subprocess.run(runner+args,text=True,capture_output=True,timeout=10)
    assert bad.returncode==2 and 'error:' in bad.stderr,(name,bad.stderr)
    assert not (a.output/'forbidden-runtime').exists() and not (a.output/'forbidden-output').exists()
    rejected[name]=bad.stderr.splitlines()[-1]
for name,text,horizon in [('aw','PROFILE STOP30_AW\n0 0\n5 0\n','60000'),('wrong-horizon','PROFILE STOP30\n0 0\n5 0\n','80000')]:
    q=a.output/(name+'.txt');q.write_text(text)
    bad=subprocess.run(cmd[:-4]+['--sim-horizon-ms',horizon,'--route',str(q)],input='',text=True,capture_output=True,timeout=10)
    assert bad.returncode!=0,(name,bad.stdout)
    assert ('stop30 uses frozen v1 PI' if name=='aw' else 'route profile scope') in bad.stderr
    rejected[name]=bad.stderr.strip()
report=dict(status='PASS_STOP30_CLI_SCOPE',prefix_observations=len(rows),rejected=rejected,physics_executed=False,binary_sha256=hashlib.sha256(a.binary.read_bytes()).hexdigest())
(a.output/'verdict.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

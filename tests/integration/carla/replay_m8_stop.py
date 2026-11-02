#!/usr/bin/env python3
"""Replay original work/sensor packets through a final native binary; no physics."""
import argparse,gzip,hashlib,json,subprocess
from pathlib import Path
from evidence_io import json_rows
p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('binary',type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
r=json.loads((a.directory/'result.json').read_text());expected=[];inputs=[]
for row in json_rows(a.directory/'trace.jsonl'):
    if row.get('work_input'):inputs.append(row['work_input'])
    inputs.append(row['native_input']);expected.append(row['native'])
cmd=[str(a.binary.resolve()),'--native-solver-work','1','42','7',str(r['binding']['actor']),'--sim-horizon-ms','60000','--speed-profile',{'normal-stop':'v1-stop','input-loss':'v1-input-loss'}[r['speed_terminal']]]
run=subprocess.run(cmd,input='\n'.join(inputs)+'\n',text=True,capture_output=True,timeout=60)
a.output.mkdir(parents=True,exist_ok=False)
(a.output/'stderr.txt').write_text(run.stderr)
with gzip.open(a.output/'native.jsonl.gz','wt') as f:f.write(run.stdout)
actual=[json.loads(s) for s in run.stdout.splitlines()]
assert run.returncode==0 and len(actual)==len(expected),(run.returncode,len(actual),len(expected))
for i,(x,y) in enumerate(zip(actual,expected)):assert x==y,('native replay mismatch',i)
report=dict(status='PASS_EXACT_NATIVE_REPLAY',observations=len(actual),binary_sha256=hashlib.sha256(a.binary.read_bytes()).hexdigest(),argv=cmd,physics_executed=False)
(a.output/'verdict.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

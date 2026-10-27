import json
from pathlib import Path
import subprocess
import sys

root=Path('/d/shin/StrataDrive')
out=root/'docs/test-plan/evidence/m7_carla_1s'
runtime=Path('/d/shin/stratadrive-tools/m7-source/m7-1s')
rows=[]
for run in json.loads((out/'live-suite.json').read_text()):
    name,mode=run['name'],run['mode']
    if run['exit'] or mode=='disabled': continue
    dest=out/(name+'-audit.json')
    if dest.exists(): continue
    script='audit_m7_1q_native.py' if mode=='legacy' else 'audit_m7_1k_server_probe.py' if mode=='zero' else 'audit_m7_1r_work.py'
    inp=out/name/'result.json' if mode=='zero' else out/name
    cmd=[sys.executable,str(root/'tests/integration/carla'/script),str(inp),'--output',str(dest)]
    if mode=='legacy':cmd+=['--model',str(root/'tools/carla/m7_nodrive/virtual_ev_v1.json')]
    with (runtime/(name+'-audit.log')).open('w') as log:
        proc=subprocess.run(cmd,cwd=root,stdout=log,stderr=subprocess.STDOUT)
    rows.append(dict(name=name,argv=cmd,exit=proc.returncode))
    print(name,'audit',proc.returncode,flush=True)
    if proc.returncode:break
prev=json.loads((out/'audit-suite.json').read_text()) if (out/'audit-suite.json').exists() else []
(out/'audit-suite.json').write_text(json.dumps(prev+rows,indent=2)+'\n')
sys.exit(1 if any(r['exit'] for r in rows) else 0)

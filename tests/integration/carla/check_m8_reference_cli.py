#!/usr/bin/env python3
"""Exercise route selection/header/horizon guards without a server or physics."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('binary',type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
cases=[('S01_AW',60000,'PROFILE S01_AW\n0 0\n5 0\n',True),
       ('S03v2_AW',80000,'PROFILE S03v2_AW\n0 0\n5 0\n',True),
       ('S03_AW',80000,'PROFILE S03_AW\n0 0\n5 0\n',False),
       ('S01',60000,'PROFILE S01\n0 0\n5 0\n',True),
       ('S03v2',80000,'PROFILE S03v2\n0 0\n5 0\n',True),
       ('S03v2_short',60000,'PROFILE S03v2\n0 0\n5 0\n',False),
       ('S03',80000,'PROFILE S03\n0 0\n5 0\n',True),
       ('legacy',60000,'0 0\n5 0\n',True),
       ('unknown',60000,'PROFILE S04\n0 0\n5 0\n',False),
       ('double_header',80000,'PROFILE S03\nPROFILE S03\n0 0\n5 0\n',False),
       ('late_header',80000,'0 0\nPROFILE S03\n5 0\n',False),
       ('S01_extended',80000,'PROFILE S01\n0 0\n5 0\n',False),
       ('S03_short',60000,'PROFILE S03\n0 0\n5 0\n',False),
       ('legacy_extended',80000,'0 0\n5 0\n',False),
       ('arbitrary_horizon',70000,'PROFILE S03\n0 0\n5 0\n',False)]
results=[]
with tempfile.TemporaryDirectory() as d:
    route=Path(d)/'route.txt'
    for name,horizon,content,accepted in cases:
        route.write_text(content)
        r=subprocess.run([str(a.binary.resolve()),'--native-solver-work','1','42','7','99',
            '--sim-horizon-ms',str(horizon),'--route',str(route)],input='',text=True,capture_output=True,timeout=5)
        assert (r.returncode==0)==accepted,(name,r.returncode,r.stderr)
        results.append(dict(case=name,accepted=accepted,returncode=r.returncode,diagnostic=r.stderr.strip()))
a.output.write_text(json.dumps(dict(status='PASS_ROUTE_CLI_SCOPE',cases=results),indent=2)+'\n')
print(f'PASS: {len(results)} route CLI scope cases; no observation or physics')

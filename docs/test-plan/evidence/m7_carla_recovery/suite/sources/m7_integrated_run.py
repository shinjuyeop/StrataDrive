#!/usr/bin/env python3
"""Reproduce the bounded M7 integration suite; fresh server per case, no ambiguous tick retry."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

CASES=('normal-a','normal-b','camera-a','camera-b','protection','rgb-drop','snapshot-stop','work-missing','zero','disabled','loading-abort')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('engine','source','python','fixture','native','runtime','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--cases',nargs='+',choices=CASES,default=list(CASES))
    a=p.parse_args();root=Path(__file__).resolve().parents[3];here=Path(__file__).resolve().parent
    a.output.mkdir(parents=True,exist_ok=False);a.runtime.mkdir(parents=True,exist_ok=False)
    frozen=a.output/'sources';frozen.mkdir()
    for path in [Path(__file__),here/'m7_1o_run.py',here/'m7_1q_probe.py',here/'m7_sensor_capture.py',
                 here/'audit_m7_integrated.py',here/'audit_m7_1r_work.py',here/'audit_m7_1q_native.py',
                 here/'audit_m7_protection.py',
                 here/'scenarios/m7_integrated_v1.txt']:
        shutil.copy2(path,frozen/path.name)
    report=dict(status='RUNNING',cases=[],source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in frozen.iterdir()})
    for name in a.cases:
        command=[sys.executable,str(here/'m7_1o_run.py'),'--engine',str(a.engine),'--source',str(a.source),
                 '--python',str(a.python),'--fixture',str(a.fixture),'--runtime',str(a.runtime/name),
                 '--output',str(a.output/name),'--vehicle-substeps','320']
        if name=='zero':command+=['--zero']
        elif name in ('disabled','loading-abort'):
            command+=['--flag-check','disabled']
            if name=='loading-abort':command+=['--abort-on-port']
        else:
            command+=['--native-actual',str(a.native),'--solver-work']
            if name.startswith(('normal','camera')) or name=='rgb-drop':
                command+=['--scenario',str(here/'scenarios/m7_integrated_v1.txt'),'--ticks','900']
            if name.startswith('camera') or name=='rgb-drop':command+=['--cameras']
            if name=='rgb-drop':command+=['--native-fault','rgb-drop']
            if name=='snapshot-stop':command+=['--native-fault','snapshot']
            if name=='work-missing':command+=['--native-fault','work-missing']
            if name=='protection':command+=['--native-fault','protection','--ticks','400',
                                         '--scenario',str(here/'scenarios/m7_integrated_v1.txt')]
        started=time.monotonic();entry=dict(name=name,argv=command,audits=[])
        with (a.output/(name+'-runner.log')).open('w') as log:
            completed=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
        entry.update(exit=completed.returncode,elapsed_seconds=time.monotonic()-started)
        if completed.returncode==0 and name not in ('zero','disabled','loading-abort','snapshot-stop','work-missing'):
            for audit in ('audit_m7_1r_work.py','audit_m7_protection.py' if name=='protection' else 'audit_m7_integrated.py'):
                out=a.output/(name+'-'+audit.removesuffix('.py')+'.json')
                cmd=[sys.executable,str(here/audit),str(a.output/name),'--output',str(out)]
                with out.with_suffix('.log').open('w') as log:
                    r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
                entry['audits'].append(dict(argv=cmd,exit=r.returncode))
        entry['status']='PASS_CASE_ONLY' if not entry['exit'] and all(not r['exit'] for r in entry['audits']) else 'FAIL'
        report['cases'].append(entry)
        (a.output/'suite.json').write_text(json.dumps(report,indent=2)+'\n')
        print(name,entry['status'],flush=True)
    report['status']='COMPLETE_BOUNDED_SUITE' if all(r['status']=='PASS_CASE_ONLY' for r in report['cases']) else 'COMPLETE_WITH_FAILURES'
    report['full_m7_closed']=False
    (a.output/'suite.json').write_text(json.dumps(report,indent=2)+'\n')
    return int(report['status']=='COMPLETE_WITH_FAILURES')


if __name__=='__main__':raise SystemExit(main())

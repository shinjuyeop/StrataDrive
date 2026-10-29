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

CASES=('normal-a','normal-b','camera-a','camera-b','protection','wall-gap','rgb-drop','snapshot-stop','work-missing','zero','disabled','loading-abort','protected-sleep','client-loss','client-loss-cameras')


SIMULATION_CASES=('continuous','continuous-cameras','protected-sleep','rgb-drop','snapshot-stop','work-missing','native-stall')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('engine','source','python','fixture','native','runtime','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--held-steer-sleep',action='store_true')
    p.add_argument('--compact-work',action='store_true')
    p.add_argument('--simulation-time',action='store_true',help='explicit simulation-time acceptance; wall real-time gate stays open')
    p.add_argument('--cases',nargs='+',choices=tuple(dict.fromkeys(CASES+SIMULATION_CASES)))
    a=p.parse_args();root=Path(__file__).resolve().parents[3];here=Path(__file__).resolve().parent
    if a.cases is None:a.cases=list(SIMULATION_CASES if a.simulation_time else CASES)
    if any(name in ('continuous','continuous-cameras','native-stall') for name in a.cases) and not a.simulation_time:
        p.error('continuous/liveness cases require explicit simulation-time profile')
    if a.simulation_time and any(name not in SIMULATION_CASES for name in a.cases):
        p.error('case is outside the simulation-time suite')
    if a.compact_work and any(name.startswith('client-loss') for name in a.cases):
        p.error('compact journal requires drain before close; exclude client-loss cases')
    a.output.mkdir(parents=True,exist_ok=False);a.runtime.mkdir(parents=True,exist_ok=False)
    frozen=a.output/'sources';frozen.mkdir()
    for path in [Path(__file__),here/'m7_1o_run.py',here/'m7_1q_probe.py',here/'m7_sensor_capture.py',
                 here/'audit_m7_integrated.py',here/'audit_m7_1r_work.py',here/'audit_m7_1q_native.py',
                 here/'audit_m7_protection.py',here/'audit_m7_wall.py',here/'audit_m7_closeout.py',here/'evidence_io.py',
                 here/'scenarios/m7_integrated_v1.txt',here/'scenarios/m7_continuous_v1.txt',here/'audit_m7_simulation.py']:
        shutil.copy2(path,frozen/path.name)
    report=dict(status='RUNNING',execution_profile='m7-simulation-time-v1' if a.simulation_time else 'legacy-bounded',cases=[],source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in frozen.iterdir()})
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
            if a.compact_work and not name.startswith('continuous'):command+=['--compact-work']
            if a.held_steer_sleep or name=='protected-sleep':command+=['--held-steer-sleep']
            if name.startswith('continuous'):
                command+=['--simulation-continuous','--ticks','6000','--scenario',str(here/'scenarios/m7_continuous_v1.txt')]
                if name.endswith('cameras'):command+=['--cameras']
            if name=='native-stall':command+=['--native-fault','native-stall','--scenario',str(here/'scenarios/m7_integrated_v1.txt')]
            if a.simulation_time and name=='protected-sleep':command+=['--cameras']
            if name.startswith('client-loss'):
                command+=['--native-fault','client-loss','--scenario',str(here/'scenarios/m7_integrated_v1.txt')]
                if name.endswith('cameras'):command+=['--cameras']
            if name.startswith(('normal','camera')) or name=='rgb-drop':
                command+=['--scenario',str(here/'scenarios/m7_integrated_v1.txt'),'--ticks','900']
            if name.startswith('camera') or name=='rgb-drop':command+=['--cameras']
            if name=='rgb-drop':command+=['--native-fault','rgb-drop']
            if name=='snapshot-stop':command+=['--native-fault','snapshot']
            if name=='work-missing':command+=['--native-fault','work-missing']
            if name=='wall-gap':command+=['--native-fault','wall-gap','--scenario',str(here/'scenarios/m7_integrated_v1.txt')]
            if name in ('protection','protected-sleep'):command+=['--native-fault','protection','--ticks','400',
                                         '--scenario',str(here/'scenarios/m7_integrated_v1.txt')]
        started=time.monotonic();entry=dict(name=name,argv=command,audits=[])
        with (a.output/(name+'-runner.log')).open('w') as log:
            completed=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
        entry.update(exit=completed.returncode,elapsed_seconds=time.monotonic()-started)
        if completed.returncode==0 and name=='wall-gap':
            out=a.output/'wall-gap-audit.json'
            cmd=[sys.executable,str(here/'audit_m7_wall.py'),str(a.output/name),'--output',str(out)]
            with out.with_suffix('.log').open('w') as log:
                r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
            entry['audits'].append(dict(argv=cmd,exit=r.returncode))
        if completed.returncode==0 and name not in ('zero','disabled','loading-abort','snapshot-stop','work-missing','wall-gap','client-loss','client-loss-cameras','native-stall'):
            for audit in ('audit_m7_1r_work.py','audit_m7_protection.py' if name in ('protection','protected-sleep') else 'audit_m7_integrated.py'):
                out=a.output/(name+'-'+audit.removesuffix('.py')+'.json')
                cmd=[sys.executable,str(here/audit),str(a.output/name),'--output',str(out)]
                with out.with_suffix('.log').open('w') as log:
                    r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
                entry['audits'].append(dict(argv=cmd,exit=r.returncode))
        if completed.returncode==0 and name not in ('zero','disabled','loading-abort','snapshot-stop','work-missing','native-stall'):
            out=a.output/(name+'-closeout.json')
            kind='client-loss' if name.startswith('client-loss') else 'sleep' if name=='protected-sleep' else 'clock'
            cmd=[sys.executable,str(here/'audit_m7_closeout.py'),str(a.output/name),'--kind',kind,'--output',str(out)]
            with out.with_suffix('.log').open('w') as log:
                r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
            entry['audits'].append(dict(argv=cmd,exit=r.returncode))
        if completed.returncode==0 and a.simulation_time and name=='protected-sleep':
            out=a.output/(name+'-sensors-audit.json')
            cmd=[sys.executable,str(here/'audit_m7_integrated.py'),str(a.output/name),'--output',str(out)]
            with out.with_suffix('.log').open('w') as log:
                r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
            entry['audits'].append(dict(argv=cmd,exit=r.returncode))
        if completed.returncode==0 and a.simulation_time and name in ('snapshot-stop','work-missing','native-stall'):
            out=a.output/(name+'-partial-work-audit.json')
            cmd=[sys.executable,str(here/'audit_m7_1r_work.py'),str(a.output/name),'--output',str(out)]
            with out.with_suffix('.log').open('w') as log:
                r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
            entry['audits'].append(dict(argv=cmd,exit=r.returncode))
        if completed.returncode==0 and a.simulation_time:
            out=a.output/(name+'-simulation-audit.json')
            cmd=[sys.executable,str(here/'audit_m7_simulation.py'),str(a.output/name),'--case',name,'--output',str(out)]
            with out.with_suffix('.log').open('w') as log:
                r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
            entry['audits'].append(dict(argv=cmd,exit=r.returncode))
        entry['status']='PASS_CASE_ONLY' if not entry['exit'] and all(not r['exit'] for r in entry['audits']) else 'FAIL'
        report['cases'].append(entry)
        (a.output/'suite.json').write_text(json.dumps(report,indent=2)+'\n')
        print(name,entry['status'],flush=True)
    report['status']='COMPLETE_BOUNDED_SUITE' if all(r['status']=='PASS_CASE_ONLY' for r in report['cases']) else 'COMPLETE_WITH_FAILURES'
    report['full_m7_closed']=False
    report['simulation_profile_accepted']=a.simulation_time and set(a.cases)==set(SIMULATION_CASES) and report['status']=='COMPLETE_BOUNDED_SUITE'
    report['wall_realtime_accepted']=False
    (a.output/'suite.json').write_text(json.dumps(report,indent=2)+'\n')
    return int(report['status']=='COMPLETE_WITH_FAILURES')


if __name__=='__main__':raise SystemExit(main())

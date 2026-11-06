#!/usr/bin/env python3
"""Fixed fresh-server STOP30 sampled-Actual cohort with original replay/audits."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from evidence_io import json_rows
from audit_m7_1q_native import audit

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent


def replay(directory,binary,fault,sampled):
    result=json.loads((directory/'result.json').read_text())
    command=[str(binary),'--native-solver-work','1','42','7',str(result['binding']['actor']),
             '--sim-horizon-ms','60000','--route',str(directory/'route.txt'),'--diagnostic-fault',fault]
    if sampled:command+=['--admission-profile','sampled-actual-v1']
    count=0;digest=hashlib.sha256()
    with (directory/'replay.stderr').open('w') as err:
        process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True)
        try:
            for row in json_rows(directory/'trace.jsonl'):
                for field in ('work_input','pose_input','native_input'):
                    if row.get(field):process.stdin.write(row[field]+'\n')
                process.stdin.flush();line=process.stdout.readline();actual=json.loads(line)
                if actual!=row['native']:raise ValueError('native replay mismatch at '+str(row['index']))
                digest.update(line.encode());count+=1
            process.stdin.close()
            if process.wait(timeout=10)!=0:raise ValueError('native replay exit')
        finally:
            if process.poll() is None:process.kill();process.wait()
    if count!=6001:raise ValueError('incomplete native replay')
    return dict(passed=True,observations=count,sha256=digest.hexdigest(),command=command)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('engine','source','python','fixture','native'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('output',type=Path);a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    a.native=a.native.resolve()
    # Resolving a venv's interpreter symlink selects the system environment.
    # Keep its lexical absolute path and validate the required client before
    # launching any owned server.
    a.python=a.python.absolute()
    probe=subprocess.run([str(a.python),'-c','import carla,json,sys;print(json.dumps(dict(executable=sys.executable,prefix=sys.prefix,carla=carla.__file__)))'],capture_output=True,text=True)
    (out/'python-preflight.json').write_text(json.dumps(dict(command_python=str(a.python),exit=probe.returncode,stdout=probe.stdout,stderr=probe.stderr),indent=2)+'\n')
    if probe.returncode:return probe.returncode
    cases=[('whole-nominal',False,'none'),('sampled-nominal',True,'none'),
           ('sampled-silent-1',True,'front-command-loss'),('sampled-silent-2',True,'front-command-loss')]
    files=[p for folder in ('tests/integration/carla','tools/carla/m7_nodrive') for p in (ROOT/folder).rglob('*')
           if p.is_file() and p.suffix in ('.py','.cpp','.hpp','.h','.json','.txt')]
    files+=[ROOT/'docs/test-plan/carla-sampled-actual-protocol.md']
    sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    digest=hashlib.sha256(a.native.read_bytes()).hexdigest()
    (out/'protocol.json').write_text(json.dumps(dict(cases=cases,sources=sources,binary_sha256=digest),indent=2)+'\n')
    rows=[]
    for name,sampled,fault in cases:
        if hashlib.sha256(a.native.read_bytes()).hexdigest()!=digest:raise ValueError('native binary changed during cohort')
        if any(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=value for path,value in sources.items()):raise ValueError('source changed during cohort')
        directory=out/name
        command=[sys.executable,str(HERE/'m7_1o_run.py')]
        for option in ('engine','source','python','fixture'):
            path=getattr(a,option)
            command+=['--'+option,str(path if option=='python' else path.resolve())]
        command+=['--native-actual',str(a.native),'--runtime',str(out/('runtime-'+name)),'--output',str(directory),
                  '--vehicle-substeps','320','--settle-mode','sleep','--solver-work','--simulation-continuous',
                  '--ticks','6000','--route-profile',str(HERE/'scenarios/m8_stop30_v1.json'),
                  '--held-steer-sleep','--route-startup-seconds','600','--diagnostic-fault',fault]
        if sampled:command.append('--sampled-actual')
        row=dict(name=name,command=command,sampled=sampled,fault=fault)
        with (out/(name+'.runtime.log')).open('w') as log:
            row['runtime_exit']=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT).returncode
        row['audits']=[]
        for script,options in [('audit_m7_1r_work.py',['--output',str(out/(name+'.work.json'))]),('audit_m9_diagnostics.py',['--mutations'])]:
            with (out/(name+'.'+script+'.log')).open('w') as log:
                code=subprocess.run([sys.executable,str(HERE/script),str(directory),*options],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT).returncode
            row['audits'].append(dict(tool=script,exit=code))
        try:
            row['replay']=replay(directory,a.native,fault,sampled)
            if sampled:
                model=json.loads((ROOT/'tools/carla/m7_nodrive/virtual_ev_v1.json').read_text())
                changes=[lambda r:r['receipt'].__setitem__('admission_profile','whole-interval-v1'),
                         lambda r:r['receipt']['original_actual']['admitted_actual'].__setitem__('command_checked_through_ns',str(r['native']['now_ns']+10000000)),
                         lambda r:r['receipt']['original_actual']['admitted_actual'].__setitem__('exclusive_expiry_ns','999999999999')]
                rejected=0
                for mutate in changes:
                    try:audit(directory,model,mutate,work_mode=True)
                    except (ValueError,KeyError):rejected+=1
                if rejected!=len(changes):raise ValueError('sampled profile/horizon/expiry mutation accepted')
                row['sampled_mutations_rejected']=rejected
        except (ValueError,KeyError,OSError,subprocess.SubprocessError) as error:row['error']=str(error)
        row['passed']=row['runtime_exit']==0 and all(x['exit']==0 for x in row['audits']) and row.get('replay',{}).get('passed',False) and 'error' not in row
        rows.append(row);(out/'results.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(row),flush=True)
    return int(not all(r['passed'] for r in rows))


if __name__=='__main__':sys.exit(main())

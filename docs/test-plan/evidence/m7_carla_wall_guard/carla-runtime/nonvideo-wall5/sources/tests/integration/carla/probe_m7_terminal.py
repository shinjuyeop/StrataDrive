#!/usr/bin/env python3
"""Recorded warmup then real wall-triggered native continuation; no CARLA execution."""
import argparse
import gzip
import json
from pathlib import Path
import select
import shutil
import subprocess
from replay_m7_native import digest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('native','scenario','trace','output'):
        p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    exe=a.output/'native-frozen';shutil.copy2(a.native,exe)
    report=dict(status='FAIL',carla_executed=False,trace_sha256=digest(a.trace),
                native_sha256=digest(exe),scenario_sha256=digest(a.scenario),exact_warmup_rows=0)
    process=None
    def read():
        if not select.select([process.stdout],[],[],10)[0]:raise AssertionError('native timeout')
        return json.loads(process.stdout.readline())
    try:
        with gzip.open(a.trace,'rt') as trace,(a.output/'native.stderr').open('w') as stderr:
            for line in trace:
                row=json.loads(line)
                if process is None:
                    f=row['native_input'].split()
                    argv=[str(exe.resolve()),'--native-solver-work',f[1],f[2],f[3],f[8],
                          '--scenario',str(a.scenario.resolve()),'--wall-watch',str((a.output/'native-wall.csv').resolve()),
                          '--wall-response',str((a.output/'terminal.jsonl').resolve())]
                    report['argv']=argv
                    process=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=stderr,text=True)
                if 'work_input' in row:process.stdin.write(row['work_input']+'\n')
                process.stdin.write(row['native_input']+'\n');process.stdin.flush()
                observed=read()
                if observed!=row['native']:raise AssertionError('warmup output mismatch')
                report['exact_warmup_rows']+=1
                if row['index']==199:
                    (a.output/'barrier.json').write_text(json.dumps(observed,indent=2)+'\n')
                    break
            if report['exact_warmup_rows']!=200:raise AssertionError('missing normal barrier')
            process.stdin.write('WALL_ARM\n');process.stdin.flush()
            report['arm']=read();report['stop']=read()
            if report['arm']['status']!='WALL_GUARD_ARMED' or report['stop']['status']!='WALL_GUARD_STOP':
                raise AssertionError('terminal status')
            # stdin stays OPEN, silent; no PROTECT, WHEEL, WORK or synthetic values.
            report['exit']=process.wait(timeout=10)
            if report['exit']!=2:raise AssertionError('expected terminal exit')
            report['status']='RECORDED_WARMUP_WALL_PROBE_COMPLETE_REQUIRES_AUDIT'
    except Exception as error:report['error']=repr(error)
    finally:
        if process and process.poll() is None:process.kill();process.wait(timeout=5)
        (a.output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report));return int(report['status']=='FAIL')

if __name__=='__main__':raise SystemExit(main())

#!/usr/bin/env python3
"""Replay frozen native inputs and compare every native output; no CARLA execution."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import select
import shutil
import subprocess
import time


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--native',type=Path,required=True)
    p.add_argument('--scenario',type=Path,required=True)
    p.add_argument('--trace',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    exe=a.output/'native-frozen';shutil.copy2(a.native,exe)
    report=dict(status='FAIL',carla_executed=False,source_trace=str(a.trace),trace_sha256=digest(a.trace),
                native_sha256=digest(exe),scenario_sha256=digest(a.scenario),rows=0,protection_requests=0)
    process=None;started=time.monotonic()
    try:
        with gzip.open(a.trace,'rt') as source,(a.output/'native.stderr').open('w') as stderr:
            for line in source:
                row=json.loads(line)
                if 'native_input' not in row or 'native' not in row:
                    raise AssertionError('incomplete input/output evidence')
                if process is None:
                    fields=row['native_input'].split()
                    argv=[str(exe.resolve()),'--native-solver-work',fields[1],fields[2],fields[3],fields[8],
                          '--scenario',str(a.scenario.resolve())]
                    report['argv']=argv
                    process=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=stderr,text=True)
                if 'work_input' in row:
                    process.stdin.write(row['work_input']+'\n')
                process.stdin.write(row['native_input']+'\n');process.stdin.flush()
                if not select.select([process.stdout],[],[],10)[0]:
                    raise AssertionError('native response timeout')
                observed=json.loads(process.stdout.readline())
                if observed!=row['native']:
                    (a.output/'mismatch.json').write_text(json.dumps(dict(index=row['index'],expected=row['native'],observed=observed),indent=2)+'\n')
                    raise AssertionError('native output changed at '+str(row['index']))
                report['rows']+=1
                if 'protection_request' in row:
                    process.stdin.write('PROTECT\n');process.stdin.flush();report['protection_requests']+=1
            if process is None:
                raise AssertionError('empty trace')
            process.stdin.close();report['native_exit']=process.wait(timeout=10)
            if report['native_exit']!=0:
                raise AssertionError('native exit')
            report['status']='PASS_EXACT_NATIVE_REPLAY'
    except Exception as error:
        report['error']=repr(error)
    finally:
        if process and process.poll() is None:
            process.kill();process.wait(timeout=5);report['forced_native_stop']=True
        report['elapsed_seconds']=time.monotonic()-started
        (a.output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
    return int(report['status']=='FAIL')


if __name__=='__main__':
    raise SystemExit(main())

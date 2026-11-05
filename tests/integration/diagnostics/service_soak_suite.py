#!/usr/bin/env python3
"""Fixed noninstrumented terminal-service baseline + 3 quiet/3 loaded finite soaks."""
import argparse
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]


def duration_check(path, hold, loaded):
    summary=json.loads((path/'result.json').read_text())
    if not summary['pass'] or not summary['load_control']:raise ValueError('runtime/load control')
    capture=summary['packet_capture']
    if capture['socket_drops'] or capture['overflow'] or capture['affinity']!=[0] or not capture['buffered']:
        raise ValueError('complete dedicated packet capture')
    periods=[]
    for name,epoch in (('central-2',2),('central-2-service',3)):
        with (path/(name+'.events.csv')).open() as f:rows=list(csv.DictReader(f))
        armed=[int(r['ns']) for r in rows if r['event']=='normal-armed' and int(r['epoch'])==epoch]
        stop=[int(r['ns']) for r in rows if r['event']=='normal-stop-requested' and int(r['epoch'])==epoch]
        if len(armed)!=1 or len(stop)!=1 or not hold*1_000_000-1000<=stop[0]-armed[0]<hold*1_000_000+1_000_000_000:
            raise ValueError('declared uninterrupted normal duration')
        periods.append(stop[0]-armed[0])
    loads=[]
    if loaded:
        for cpu in (1,2,7):
            data=json.loads((path/f'load-{cpu}'/'load.json').read_text())
            if data['affinity']!=[cpu] or data['policy']!=0 or data['priority']!=0 or data['windows']<1 or data['cpu_ns']<data['wall_ns']*.1:
                raise ValueError('measured competing CPU load')
            loads.append(data)
    return dict(passed=True,normal_duration_ns=periods,loads=loads)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    binary=ROOT/'build/m5-someip-normal/project/tests/integration/someip/someip_front_adapter'
    plan=[('baseline',500,False)]+[(f'{kind}-{i}',60000,kind=='loaded') for kind in ('quiet','loaded') for i in range(1,4)]
    (out/'protocol.json').write_text(json.dumps(dict(cases=plan,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),profile='normal',scope='finite Host service soak'),indent=2)+'\n')
    results=[]
    for name,hold,loaded in plan:
        command=[sys.executable,str(ROOT/'tests/integration/someip/front_run.py'),str(out/name),'--profile','normal','--three','--simple-vehicle','--diagnostics','--diagnostic-service','--isolated-ecus','--cases','central-rejoin','--split-owner-io','--separate-aux-io','--owner-fifo','--sdk-io-threads','2','--service-hold-ms',str(hold)]
        if loaded:command.append('--loaded')
        row=dict(case=name,hold_ms=hold,loaded=loaded,command=command)
        with (out/(name+'.log')).open('w') as log:
            try:row['exit']=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=180).returncode
            except subprocess.TimeoutExpired:row['exit']=124
        path=out/name/'central-rejoin-1';audits=[]
        for tool in ('audit_native_service','audit_service_ordering','audit_service_timing','audit_service_response'):
            run=subprocess.run([sys.executable,str(ROOT/'tests/integration/diagnostics'/f'{tool}.py'),str(path),'--mutations'],cwd=ROOT,capture_output=True,text=True)
            (out/(name+'-'+tool+'.log')).write_text(run.stdout+run.stderr);audits.append(dict(tool=tool,exit=run.returncode))
        row['audits']=audits
        try:row['duration']=duration_check(path,hold,loaded)
        except (ValueError,KeyError,OSError) as error:row['duration']=dict(passed=False,error=str(error))
        row['passed']=row['exit']==0 and all(x['exit']==0 for x in audits) and row['duration']['passed']
        results.append(row);(out/'results.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(row),flush=True)
    return int(not all(r['passed'] for r in results))


if __name__=='__main__':sys.exit(main())

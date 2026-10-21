#!/usr/bin/env python3
"""Prospective finite48 requests on the actual remote adapter; never retries."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
from run import supervise

ROOT=Path(__file__).resolve().parents[3]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);args=parser.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for base in ('tests/integration/someip','interfaces/someip','simulation/runtime') for p in sorted((ROOT/base).iterdir()) if p.is_file()}
    conditions=[(policy,loaded,case) for policy in ('other','fifo') for loaded,case in [(False,'normal'),(True,'normal'),(False,'owner-pause'),(False,'monitor-overrun')]]
    rows=[];plan={'source':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'source_sha256':sources,'profiles':['normal','asan'],'repetitions':3,'duration_ms':2540,'deadline_ms':4,'opportunity_ms':2,'guard_lead_ms':100,'tail_ms':20,'conditions':conditions,'cpus':{'central':1,'front':2,'plant':3,'monitors':0,'sdk_central':4,'sdk_front':5,'plant_aux':6,'loads':[1,2]},'rtprio':resource.getrlimit(resource.RLIMIT_RTPRIO),'allowed_cpus':sorted(os.sched_getaffinity(0)),'binary_sha256':{p:hashlib.sha256((ROOT/f'build/m5-someip-{p}/project/tests/integration/someip/someip_front_adapter').read_bytes()).hexdigest() for p in ('normal','asan')}}
    (out/'protocol.json').write_text(json.dumps(plan,indent=2)+'\n')
    for profile in plan['profiles']:
        for rep in range(3):
            rotated=conditions[rep:]+conditions[:rep]
            for policy,loaded,case in rotated:
                name=f'{profile}-{rep+1}-{policy}-{int(loaded)}-{case}';folder=out/name
                command=[sys.executable,str(ROOT/'tests/integration/someip/front_run.py'),str(folder),'--profile',profile,'--native-watch','--timing','--cases',case]
                if policy=='fifo':command.append('--fifo')
                if loaded:command.append('--loaded')
                # The child applies its shared exclusive build/test lock before
                # source/binary identity and runtime. No concurrent work is launched.
                monitor=out/(name+'-runner');monitor.mkdir()
                code=supervise(command,monitor,30)
                row={'name':name,'profile':profile,'repeat':rep+1,'policy':policy,'loaded':loaded,'case':case,'exit':code,'verdict':'PASS' if code==0 else 'FAIL','argv':command}
                result_path=folder/f'{case}-1/result.json'
                if result_path.exists():
                    result=json.loads(result_path.read_text());row['native']=result.get('native');row['load_control']=result.get('load_control')
                    # Refused RT setup is not an executed performance result.
                    if policy=='fifo' and not any(p.get('summary',{}).get('armed_ns',0) for p in result.get('processes',[])):
                        logs='\n'.join(p.read_text(errors='replace') for p in folder.glob('*/*.stderr'))
                        if 'Operation not permitted' in logs or 'Permission denied' in logs:row['verdict']='NOT RUN';row['reason']='actual RT setup refused'
                rows.append(row);(out/'results.json').write_text(json.dumps(rows,indent=2)+'\n')
                print(name,row['verdict'],flush=True)
    return 0 if all(r['verdict']=='PASS' for r in rows) else 1

if __name__=='__main__':sys.exit(main())

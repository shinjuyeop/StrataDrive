#!/usr/bin/env python3
"""Prospective one-factor Host DDS comparison; never a control acceptance gate."""
import argparse
import csv
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

import check_dds_lifecycle as d

SANITIZERS = {'TSAN_OPTIONS':'halt_on_error=0:exitcode=66:history_size=7',
              'ASAN_OPTIONS':'detect_leaks=1:exitcode=1',
              'UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'}
CONFIGS = {'A':(1,1,5,'full'), 'B':(1,1,5,'minimal'),
           'C':(1,2,5,'minimal'), 'D':(1,2,20,'minimal')}


def trials():
    rows=[]
    for repeat in range(1,4):
        for label in CONFIGS:
            rows.append(dict(id=f'normal-{label}-{repeat}',profile='normal',case='normal',config=label,coordinated=False))
    for profile in d.PROFILES:
        if profile!='normal':
            rows.append(dict(id=profile+'-normal',profile=profile,case='normal',config='D',coordinated=False))
        for case in ('overflow','peer-stop','peer-kill','restart','coordinated-restart','partial','callback-delete','close-saturated'):
            rows.append(dict(id=profile+'-'+case,profile=profile,case='restart' if case=='coordinated-restart' else case,
                             config='D',coordinated=case=='coordinated-restart'))
    return rows


def readiness_trials():
    rows=[dict(id=f'normal-A-ready-{i}',profile='normal',config='A',case='normal',withhold=False) for i in range(1,4)]
    rows += [dict(id=p+'-D-ready',profile=p,config='D',case='normal',withhold=False) for p in ('asan-ubsan','tsan')]
    rows.append(dict(id='normal-withheld-ready',profile='normal',config='D',case='normal',withhold=True))
    return rows


def sanitizer_verdict(profile, case, warnings, completed=True):
    if warnings:return 'FAIL'
    if profile=='normal':return 'NOT APPLICABLE'
    if case=='peer-kill':return 'INCOMPLETE (expected peer SIGKILL)'
    if not completed:return 'INCOMPLETE (process failure)'
    return 'PASS'


def evidence_errors(folder, row, detail):
    """Missing observation is not zero; preserve functional and sanitizer failures."""
    errors=[]
    if not isinstance(detail,dict) or not isinstance(detail.get('processes'),list):
        return ['missing/invalid process outcomes']
    if detail.get('functional') not in ('PASS','FAIL') or detail.get('control_gate_open') is not False:
        errors.append('invalid functional/control-gate result')
    identities=[]
    for process in detail['processes']:
        if not isinstance(process,dict) or process.get('role') not in ('central','zone') or type(process.get('epoch')) is not int or type(process.get('exit')) is not int:
            errors.append('invalid process identity/exit');continue
        role,epoch=process['role'],process['epoch'];prefix=folder/f'{role}-{epoch}'
        identities.append((role,epoch))
        if process.get('expected_kill') and not (process['expected_kill'] is True and row['case']=='peer-kill' and role=='zone' and epoch==42 and process['exit']==-signal.SIGKILL):
            errors.append('invalid expected peer kill')
        for entity in ('reader','writer'):
            try:
                values=list(csv.DictReader(Path(str(prefix)+f'.{entity}-qos.csv').open()))
                if len(values)!=1 or values[0]['read']!='1' or values[0]['matches']!='1':raise ValueError('QoS mismatch')
            except (OSError,ValueError,KeyError) as error:errors.append(f'{role}/{entity} QoS: {error}')
        phases=('matched',) if process.get('expected_kill') else ('matched','closing')
        for phase in phases:
            try:
                threads=list(csv.DictReader(Path(str(prefix)+f'.{phase}.threads.csv').open()))
                cpu=CONFIGS[row['config']][0 if role=='central' else 1]
                if not threads or any(t['policy']!='0' or t['priority']!='0' or t['affinity']!=f'{cpu};' for t in threads):
                    raise ValueError('missing threads or requested placement/policy not applied')
            except (OSError,ValueError,KeyError) as error:errors.append(f'{role}/{phase} threads: {error}')
        if process.get('expected_kill'):continue
        try:
            statuses=list(csv.DictReader(Path(str(prefix)+'.reader-status.csv').open()))
            if len(statuses)!=1 or statuses[0]['rejected_rc']!='0' or statuses[0]['lost_rc']!='0':raise ValueError('status unavailable')
        except (OSError,ValueError,KeyError) as error:errors.append(f'{role} status: {error}')
        summary=process.get('summary',{})
        if not isinstance(summary,dict):
            errors.append(f'{role} invalid summary');summary={}
        if summary.get('functional') is not True or summary.get('control_gate_open') is not False:
            errors.append(f'{role} missing/failed functional summary or open control gate')
        if row['case']=='partial' and role=='zone' and (type(summary.get('received_after_writer_delete')) is not int or summary['received_after_writer_delete']<=0):
            errors.append('writer-only deletion still stopped reader ingress')
        if row['case'] in ('peer-stop','peer-kill','overflow') and role=='central' and not summary.get('availability_loss_ns'):
            errors.append('original valid deadline loss not observed')
        try:
            events=list(csv.DictReader(Path(str(prefix)+'.csv').open()))
            for event in events:
                if event['event']!='send' and event['accepted']=='1' and (
                    int(event['time_ns'])>=int(event['deadline_ns']) or int(event['time_ns'])>=int(event['inner_expiry_ns'])):
                    errors.append('accepted event at/after original expiry')
        except (OSError,ValueError,KeyError) as error:errors.append(f'{role} events: {error}')
    if not detail.get('processes'):errors.append('missing process outcomes')
    expected={('central',42),('zone',42)}
    if row['case']=='restart':expected.add(('zone',43))
    if len(identities)!=len(expected) or set(identities)!=expected:
        errors.append('missing/duplicate/unexpected process identity')
    return errors


def main():
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path)
    parser.add_argument('--readiness',action='store_true');args=parser.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    rows=[{**r,'verdict':'NOT RUN'} for r in (readiness_trials() if args.readiness else trials())]
    protocol_name='readiness-protocol.md' if args.readiness else 'protocol.md'
    d.save(out/'plan.json',dict(base=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
           protocol='docs/test-plan/evidence/m5_dds_operating_profile/'+protocol_name,configs=CONFIGS,trials=rows,
           case_timeout_s=35,campaign_timeout_s=600,storage_limit_bytes=536870912,sanitizers=SANITIZERS))
    d.save(out/'results.json',rows)
    sources=out/'sources';sources.mkdir()
    for file in d.HERE.iterdir():
        if file.is_file():shutil.copy2(file,sources/file.name)
    protocol=d.ROOT/'docs/test-plan/evidence/m5_dds_operating_profile'/protocol_name
    shutil.copy2(protocol,out/'protocol.md')
    hashes={p.name:d.sha(p) for p in sources.iterdir()}
    d.save(out/'metadata.json',dict(sources=hashes,protocol_sha256=d.sha(protocol),
           sdk_libraries={k:d.sha(d.ROOT/v[0]/'lib/libddsc.so.11') for k,v in d.PROFILES.items()}))
    with d.open_build_lock() as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        code=d.build_probes(out)
        if code:return code
        d.save(out/'binaries.json',{k:d.sha(out/k/'lifecycle-probe') for k in d.PROFILES})
        began=time.monotonic()
        for row in rows:
            folder=out/row['id'];folder.mkdir();cpu_c,cpu_z,period,observer=CONFIGS[row['config']]
            env={k:v for k,v in os.environ.items() if not k.startswith('SD_')}
            env.update(SANITIZERS,SD_CENTRAL_CPU=str(cpu_c),SD_ZONE_CPU=str(cpu_z),SD_PERIOD_MS=str(period),
                       SD_OBSERVER=observer,SD_LIFETIME_TRACE='off' if observer=='minimal' else 'full')
            if row.get('coordinated'):env['SD_COORDINATED_RESTART']='1'
            if args.readiness:env['SD_TRANSPORT_READY']='1'
            if row.get('withhold'):env['SD_TEST_WITHHOLD_READY']='1'
            cmd=['unshare','-Urnm',sys.executable,str(d.HERE/'check_dds_lifecycle.py'),'--inside',str(folder),str(out/row['profile']/'lifecycle-probe'),row['case']]
            if row['profile']=='tsan':cmd=['setarch','x86_64','-R',*cmd]
            d.save(folder/'command.json',dict(argv=cmd,env={k:v for k,v in env.items() if k.startswith('SD_') or k in SANITIZERS}))
            with (folder/'run.log').open('w') as log:
                with subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True) as process:
                    try:code=process.wait(timeout=35)
                    except subprocess.TimeoutExpired:
                        try:os.killpg(process.pid,signal.SIGKILL)
                        except ProcessLookupError:pass
                        process.wait();code=124
            logs='\n'.join(p.read_text(errors='replace') for p in [folder/'run.log',*folder.glob('*.stderr')])
            bad=any(x in logs for x in ('WARNING: ThreadSanitizer','FATAL: ThreadSanitizer','ERROR: AddressSanitizer','ERROR: LeakSanitizer','runtime error:'))
            detail=d.lifetime_result((folder/'result.json').read_text().replace('\n','')) if (folder/'result.json').exists() else {}
            errors=evidence_errors(folder,row,detail) if not row.get('withhold') else []
            row.update(exit=code,functional=detail.get('functional','FAIL'),sanitizer_clean=not bad,
                       sanitizer_verdict=sanitizer_verdict(row['profile'],row['case'],bad,code==0),
                       tsan_warnings=logs.count('WARNING: ThreadSanitizer'),evidence_errors=errors,result=detail)
            row['verdict']='PASS' if code==0 and row['functional']=='PASS' and not bad and not errors else 'FAIL'
            if row.get('withhold'):
                ready_path=folder/'central-42.transport-ready.json'
                ready=json.loads(ready_path.read_text()) if ready_path.exists() else {}
                row['negative_control_pass']=code!=0 and ready.get('received') is False and not (folder/'go').exists() and len(detail.get('processes',[]))==2 and all(p.get('exit') is not None for p in detail['processes'])
            d.save(out/'results.json',rows)
            print(json.dumps({k:v for k,v in row.items() if k!='result'}),flush=True)
            if time.monotonic()-began>600 or sum(p.stat().st_size for p in out.rglob('*') if p.is_file())>536870912:
                (out/'limit-stop.txt').write_text('time/storage cap; remaining NOT RUN\n');return 2
        stable=all(d.sha(d.HERE/name)==value for name,value in hashes.items())
        d.save(out/'source-stability.json',dict(unchanged=stable))
        return 0 if stable and all(row['verdict']=='PASS' for row in rows) else 1


if __name__=='__main__':raise SystemExit(main())

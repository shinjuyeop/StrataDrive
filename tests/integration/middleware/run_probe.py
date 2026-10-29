#!/usr/bin/env python3
"""Prospective DDS/Zenoh candidate cohort, isolated user/net namespaces (36 runs)."""
import argparse, csv, hashlib, json, os, platform, signal, subprocess, sys, time
from pathlib import Path
import runpy
ROOT=Path(__file__).resolve().parents[3]
BASE=runpy.run_path(str(ROOT/'tests/integration/runtime/check_m4_async.py'))

def call(cmd, log):
    p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    log.write(p.stdout);log.flush()
    if p.returncode: raise RuntimeError(f'{cmd}: {p.returncode}: {p.stdout}')
    return p.stdout

SUMMARY_FIELDS = ('cpu','affinity_count','cpu1','policy','sent','received',
                  'accepted','rejected','echo_mismatch','channel_failures')

def result_schema_errors(result):
    if not isinstance(result,dict):return ['result must be a JSON object']
    issues=[]
    if type(result.get('verdict')) is not str or result['verdict'] not in ('PASS','FAIL'):
        issues.append('verdict must be PASS or FAIL')
    codes=result.get('codes')
    if not isinstance(codes,list) or len(codes)!=2 or any(type(c) is not int for c in codes):
        issues.append('codes must contain two integer process exit codes')
    for field in ('invalid_accepted','expired_echoes'):
        if type(result.get(field)) is not int or result[field]<0:issues.append(f'{field} must be a nonnegative integer')
    for role in ('central','zone'):
        summary=result.get(role)
        if not isinstance(summary,dict):issues.append(f'{role} must be a summary object');continue
        for field in SUMMARY_FIELDS:
            if type(summary.get(field)) is not int or summary[field]<0:
                issues.append(f'{role}.{field} must be a nonnegative integer')
    if 'diagnostic_errors' in result and (not isinstance(result['diagnostic_errors'],list) or
            any(type(x) is not str for x in result['diagnostic_errors'])):
        issues.append('diagnostic_errors must be a list of strings')
    return issues

def checked_result(folder, result, code=0, error=''):
    issues=[error] if error else []
    schema=result_schema_errors(result);issues.extend(schema)
    original=result
    if not isinstance(result,dict):result={'raw_result':original}
    previous=result.get('diagnostic_errors')
    if isinstance(previous,list):issues.extend(x for x in previous if type(x) is str)
    if code:issues.append(f'runner exit {code}')
    if result.get('verdict')!='PASS':issues.append('workload did not PASS')
    if not schema and result['codes']!=[0,0]:issues.append('probe process exit was nonzero')
    if not schema and result['invalid_accepted']!=0:issues.append('invalid input accepted')
    for role in ('central','zone'):
        path=Path(folder)/(role+'.stderr')
        try:text=path.read_text(errors='replace')
        except OSError as missing:issues.append(f'missing/unreadable {role}.stderr: {missing}');continue
        if any(marker in text for marker in ('WARNING: ThreadSanitizer','FATAL: ThreadSanitizer',
                'ERROR: AddressSanitizer','ERROR: LeakSanitizer','UndefinedBehaviorSanitizer','runtime error:')):
            issues.append(f'sanitizer diagnostic in {role}.stderr')
    return {**result,'verdict':'FAIL' if issues else 'PASS','runner_exit':code,
            'diagnostic_errors':list(dict.fromkeys(issues))}

def run_trial(command, folder, timeout=30):
    with (Path(folder)/'runner.log').open('w') as log:
        try:
            with subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True) as process:
                try:return process.wait(timeout=timeout),''
                except subprocess.TimeoutExpired:
                    try:os.killpg(process.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    process.wait()
                    return 124,f'timeout after {timeout}s; owned process group terminated'
        except OSError as error:return 127,f'{type(error).__name__}: {error}'

def child(folder, binary, condition):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    with (folder/'network.log').open('w') as log:
        call(['mount','-t','tmpfs','tmpfs','/run'],log)
        for name in ('central','zone'):call(['ip','netns','add',name],log)
        call(['ip','link','add','sdc','type','veth','peer','name','sdz'],log)
        for name,interface,address in [('central','sdc','10.88.0.1/30'),('zone','sdz','10.88.0.2/30')]:
            call(['ip','link','set',interface,'netns',name],log)
            for cmd in (['link','set','lo','up'],['addr','add',address,'dev',interface],['link','set',interface,'up']):call(['ip','netns','exec',name,'ip',*cmd],log)
        config='<CycloneDDS><Domain Id="37"><General><AllowMulticast>false</AllowMulticast></General><Discovery><ParticipantIndex>auto</ParticipantIndex><Peers><Peer Address="10.88.0.1"/><Peer Address="10.88.0.2"/></Peers></Discovery></Domain></CycloneDDS>'
        env={**os.environ,'CYCLONEDDS_URI':config,'RUST_LOG':'error'}
        procs=[];streams=[];times={};load=None
        try:
            if condition=='loaded':
                load=subprocess.Popen([sys.executable,str(ROOT/'tests/integration/runtime/check_m4_faults.py'),'--load-child',str(folder),'--cpu','1'],stdout=subprocess.PIPE,text=True)
                if load.stdout.readline().strip()!='LOAD_READY':raise RuntimeError('load readiness')
            for role in ('central','zone'):
                stream=(folder/(role+'.json')).open('w');streams.append(stream)
                err=(folder/(role+'.stderr')).open('w');streams.append(err)
                times[role+'_start_ns']=time.monotonic_ns()
                command=['ip','netns','exec',role,'taskset','-c','1',binary,role,str(folder/(role+'.csv')),'42',condition]
                (folder/(role+'-command.json')).write_text(json.dumps(command)+'\n')
                procs.append(subprocess.Popen(command,stdout=stream,stderr=err,env=env))
                if role=='central':time.sleep(.1)
            time.sleep(.4)
            setup=[]
            for process,role in zip(procs,('central','zone')):
                tasks=[]
                for tid in sorted((Path('/proc')/str(process.pid)/'task').iterdir()):
                    n=int(tid.name)
                    tasks.append({'tid':n,'policy':os.sched_getscheduler(n),'priority':os.sched_getparam(n).sched_priority,'affinity':sorted(os.sched_getaffinity(n))})
                setup.append({'role':role,'pid':process.pid,'tasks':tasks})
            (folder/'threads.json').write_text(json.dumps(setup,indent=2)+'\n')
            if condition in ('down-loss','up-loss','down-delay'):
                target=times['central_start_ns']+2_200_000_000
                time.sleep(max(0,(target-time.monotonic_ns())/1e9))
                role,interface=('zone','sdz') if condition=='up-loss' else ('central','sdc')
                prefix=['ip','netns','exec',role,'tc','qdisc']
                times['fault_command_ns']=time.monotonic_ns()
                call(prefix+['add','dev',interface,'root','netem',*(['delay','100ms'] if condition=='down-delay' else ['loss','100%'])],log)
                times['fault_applied_ns']=time.monotonic_ns();call(prefix+['show','dev',interface],log)
                time.sleep(.3);call(['ip','netns','exec',role,'tc','-s','qdisc','show','dev',interface],log)
                call(prefix+['del','dev',interface,'root'],log);times['fault_cleared_ns']=time.monotonic_ns()
            codes=[p.wait(timeout=12) for p in procs]
        finally:
            for p in procs:
                if p.poll() is None:p.kill();p.wait()
            if load:load.terminate();load.wait(timeout=5)
            for stream in streams:stream.close()
        (folder/'events.json').write_text(json.dumps(times,indent=2)+'\n')
        summaries={role:json.loads((folder/(role+'.json')).read_text()) for role in ('central','zone')}
        rows=list(csv.DictReader((folder/'zone.csv').open()));seen=set();bad=0
        for r in rows:
            if r['event']!='receive' or r['accepted']!='1':continue
            identity=(r['epoch'],r['sequence'])
            if r['epoch']!='42' or identity in seen or not (int(r['source_ns'])<=int(r['time_ns'])<int(r['expiry_ns'])) or int(r['time_ns'])-int(r['source_ns'])>30_000_000:bad+=1
            seen.add(identity)
        echoes=list(csv.DictReader((folder/'central.csv').open()))
        expired_echoes=sum(r['event']=='echo' and (int(r['time_ns'])>=int(r['expiry_ns']) or int(r['time_ns'])-int(r['source_ns'])>30_000_000) for r in echoes)
        c,z=summaries['central'],summaries['zone'];thread_ok=all(x['tasks'] and all(t['affinity']==[1] and t['policy']==0 and t['priority']==0 for t in x['tasks']) for x in setup)
        ok=thread_ok and codes==[0,0] and bad==0 and c['echo_mismatch']==0 and all(x['cpu']==1 and x['affinity_count']==1 and x['cpu1']==1 and x['policy']==0 for x in (c,z))
        if condition in ('normal','loaded'):ok=ok and z['accepted']==100 and z['rejected']==3 and c['received']==103 and not(c['channel_failures']+z['channel_failures'])
        elif condition=='overflow':ok=ok and c['channel_failures']+z['channel_failures']>0
        else:ok=ok and (z['accepted']<100 or c['received']<103 or z['rejected']>3 or expired_echoes>1)
        if load:
            data=json.loads((folder/'load.json').read_text());ok=ok and data['affinity']==[1] and data['policy']==0 and data['priority']==0 and data['cpu_ns']>100_000_000
        result={'verdict':'PASS' if ok else 'FAIL','invalid_accepted':bad,'expired_echoes':expired_echoes,'codes':codes,**summaries}
        (folder/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--child',nargs=3);p.add_argument('--output',type=Path);p.add_argument('--protocol',type=Path,default=ROOT/'docs/archive/protocols/m4-middleware-probe-protocol-v2.md');p.add_argument('--build',type=Path,default=ROOT/'build/m4-middleware-probes/tests/integration/middleware');a=p.parse_args()
    if a.child:
        folder=Path(a.child[0]);folder.mkdir(parents=True,exist_ok=True)
        try:
            original=child(*a.child)
            # Preserve the child's unvalidated result before writing the verdict.
            raw=folder/'result.json'
            if raw.exists():(folder/'result.original.json').write_bytes(raw.read_bytes())
            result=checked_result(folder,original)
        except Exception as error:result={'verdict':'FAIL','runner_exit':1,'diagnostic_errors':[f'{type(error).__name__}: {error}']}
        (folder/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        return 0 if result['verdict']=='PASS' else 1
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    meta={'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'source_digest':BASE['fingerprint'](),'kernel':platform.release(),'planned':36,'protocol_sha256':hashlib.sha256(a.protocol.read_bytes()).hexdigest()}
    (out/'metadata.json').write_text(json.dumps(meta,indent=2)+'\n');results=[]
    for rep in range(3):
        for candidate in (('dds','zenoh') if rep%2==0 else ('zenoh','dds')):
            for condition in ('normal','down-loss','up-loss','down-delay','overflow','loaded'):
                folder=out/f'{candidate}-{condition}-{rep}';folder.mkdir()
                command=['unshare','-Urnm',sys.executable,str(Path(__file__).resolve()),'--child',str(folder),str(a.build.resolve()/(candidate+'_candidate_probe')),condition]
                (folder/'command.json').write_text(json.dumps(command)+'\n')
                code,error=run_trial(command,folder)
                try:result=json.loads((folder/'result.json').read_text())
                except (OSError,ValueError) as missing:result={'verdict':'FAIL','missing_result':f'{type(missing).__name__}: {missing}'}
                result=checked_result(folder,result,code,error)
                row={'candidate':candidate,'condition':condition,'repetition':rep,**result};results.append(row)
                (out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
                print(json.dumps(row),flush=True)
    stable=BASE['fingerprint']()==meta['source_digest']
    if not stable:(out/'source-error.txt').write_text('sources changed during cohort\n')
    (out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    return 0 if stable and len(results)==36 and all(r['verdict']=='PASS' for r in results) else 1
if __name__=='__main__':raise SystemExit(main())

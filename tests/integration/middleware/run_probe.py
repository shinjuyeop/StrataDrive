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
    p=argparse.ArgumentParser();p.add_argument('--child',nargs=3);p.add_argument('--output',type=Path);p.add_argument('--protocol',type=Path,default=ROOT/'docs/test-plan/m4_middleware_probe_protocol_v2.md');p.add_argument('--build',type=Path,default=ROOT/'build/m4-middleware-probes/tests/integration/middleware');a=p.parse_args()
    if a.child:child(*a.child);return
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    meta={'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'source_digest':BASE['fingerprint'](),'kernel':platform.release(),'planned':36,'protocol_sha256':hashlib.sha256(a.protocol.read_bytes()).hexdigest()}
    (out/'metadata.json').write_text(json.dumps(meta,indent=2)+'\n');results=[]
    for rep in range(3):
        for candidate in (('dds','zenoh') if rep%2==0 else ('zenoh','dds')):
            for condition in ('normal','down-loss','up-loss','down-delay','overflow','loaded'):
                folder=out/f'{candidate}-{condition}-{rep}';folder.mkdir()
                command=['unshare','-Urnm',sys.executable,str(Path(__file__).resolve()),'--child',str(folder),str(a.build.resolve()/(candidate+'_candidate_probe')),condition]
                (folder/'command.json').write_text(json.dumps(command)+'\n')
                with (folder/'runner.log').open('w') as log:r=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
                result=json.loads((folder/'result.json').read_text()) if (folder/'result.json').exists() else {'verdict':'BLOCKED','exit':r.returncode}
                row={'candidate':candidate,'condition':condition,'repetition':rep,**result};results.append(row)
                print(json.dumps(row),flush=True)
    if BASE['fingerprint']()!=meta['source_digest']:raise RuntimeError('sources changed during cohort')
    (out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
if __name__=='__main__':main()

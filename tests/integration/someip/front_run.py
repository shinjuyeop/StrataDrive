#!/usr/bin/env python3
"""Real eight-participant Host adapter. Shared SIL IO is not network evidence."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from datetime import datetime
from sdk_outcomes import sdk_outcomes
import run as pilot

ROOT=pilot.ROOT
HERE=Path(__file__).resolve()
CASES=('normal','late','ready-timeout','invalid','delay','command-loss','result-loss','status-loss','lease-loss','overflow','close-full','restart-live','central-stop')

def config(role,generation=1):
    if not 1<=generation<=16:raise ValueError('Host test transport identity generation must be in 1..16; no client-ID reuse')
    c=pilot.config(role)
    base=0x5346 if role=='central' else 0x5344
    port=30503 if role=='central' else 30501
    if role=='front':c['applications'][0]['id']=hex(0x1421+generation)
    c['services']=[{'service':hex(base+i),'instance':'0x0001','reliable':{'port':port+i,'enable-magic-cookies':'false'}} for i in range(2)]
    return c

def inside(folder,binary,case):
    procs=[];streams=[];capture=None
    result={'case':case,'pass':False,'processes':[],'forced_cleanup':[],
            'clock_sample':{'monotonic_ns':time.monotonic_ns(),'wall_ns':time.time_ns(),'utc_offset_s':datetime.now().astimezone().utcoffset().total_seconds()}}
    def call(cmd):return subprocess.check_output(list(map(str,cmd)),stderr=subprocess.STDOUT,text=True)
    def launch(role,generation=1,test_override=None):
        prefix=folder/f'{role}-{generation}'
        env=dict(os.environ,LD_LIBRARY_PATH=os.environ.get('STRATADRIVE_SOMEIP_OBSERVATION_LIB',str(binary.parents[4]/'install/lib')),ASAN_OPTIONS='halt_on_error=1:detect_leaks=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1',TSAN_OPTIONS='halt_on_error=0:exitcode=66')
        if role=='plant':cmd=['taskset','-c','3',str(binary),role,str(folder)]
        else:
            cfg=folder/f'{role}.config.json';pilot.save(cfg,config(role,generation))
            env.update(VSOMEIP_CONFIGURATION=str(cfg),VSOMEIP_APPLICATION_NAME=role)
            cmd=['ip','netns','exec',role,'unshare','-m','taskset','-c','1' if role=='central' else '2',sys.executable,str(pilot.HERE),'--node',str(binary),role,str(folder),test_override or case,str(generation)]
        pilot.save(Path(str(prefix)+'.command.json'),{'argv':cmd,'env':{k:env[k] for k in env if k.startswith(('VSOMEIP','LD_LIBRARY','ASAN','UBSAN','TSAN'))}})
        out=open(str(prefix)+'.stdout','w');err=open(str(prefix)+'.stderr','w');streams.extend([out,err])
        p=subprocess.Popen(cmd,env=env,stdout=out,stderr=err);procs.append((role,generation,p));return p
    def snapshot(role,p):
        record={'pid':p.pid,'netns':os.readlink(f'/proc/{p.pid}/ns/net'),'threads':[]}
        for t in sorted(Path(f'/proc/{p.pid}/task').iterdir()):
            try:record['threads'].append({'tid':int(t.name),'name':(t/'comm').read_text().strip(),'affinity':sorted(os.sched_getaffinity(int(t.name))),'policy':os.sched_getscheduler(int(t.name)),'priority':os.sched_getparam(int(t.name)).sched_priority})
            except ProcessLookupError:pass
        pilot.save(folder/f'{role}.runtime.json',record)
        (folder/f'{role}.maps').write_text(Path(f'/proc/{p.pid}/maps').read_text())
        (folder/f'{role}.sockets.txt').write_text(call(['ip','netns','exec',role,'ss','-antup']))
    try:
        call(['mount','-t','tmpfs','tmpfs','/run'])
        (folder/'sil-io').mkdir()
        call(['mount','-t','tmpfs','-o','size=1m','tmpfs',folder/'sil-io'])
        for role in ('central','front'):call(['ip','netns','add',role])
        call(['ip','link','add','sdc','type','veth','peer','name','sdf'])
        for role,dev,address in [('central','sdc','10.88.0.1/30'),('front','sdf','10.88.0.2/30')]:
            call(['ip','link','set',dev,'netns',role])
            for args in (['link','set','lo','up'],['addr','add',address,'dev',dev],['link','set',dev,'up'],['route','add','224.0.0.0/4','dev',dev]):call(['ip','netns','exec',role,'ip',*args])
            (folder/f'{role}.network.txt').write_text(call(['ip','netns','exec',role,'ip','-details','addr']))
        caperr=(folder/'capture.stderr').open('w');streams.append(caperr)
        capture=subprocess.Popen(['ip','netns','exec','central',sys.executable,str(pilot.HERE),'--capture',str(folder)],stdout=subprocess.DEVNULL,stderr=caperr)
        pilot.wait_for(lambda:(folder/'capture.ready').exists())
        env=dict(os.environ,LD_LIBRARY_PATH=os.environ.get('STRATADRIVE_SOMEIP_OBSERVATION_LIB',str(binary.parents[4]/'install/lib')))
        with (folder/'bootstrap.txt').open('w') as log:subprocess.run([str(binary),'bootstrap',str(folder)],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
        plant=launch('plant');pilot.wait_for(lambda:(folder/'plant-ready').exists())
        central=launch('central')
        front=None
        if case!='ready-timeout':
            if case=='late':time.sleep(.5)
            front=launch('front')
            pilot.wait_for(lambda:(folder/'central-1.ready').exists() or central.poll() is not None)
            if central.poll() is not None:raise RuntimeError('Central failed before ready')
            snapshot('central',central);snapshot('front',front)
            if case not in ('normal','late'):
                pilot.wait_for(lambda:(folder/'control-established').exists() or central.poll() is not None)
                if central.poll() is not None:raise RuntimeError('Central failed before real control')
                (folder/'inject').write_text(str(time.monotonic_ns()))
                if case=='restart-live':
                    result['injected_crash']={'role':'front','generation':1,'pid':front.pid,'ns':time.monotonic_ns()}
                    front.kill();front.wait(timeout=2)
                    pilot.wait_for(lambda:(folder/'central-protected').exists() or central.poll() is not None,3)
                    if central.poll() is not None:raise RuntimeError('surviving Central failed')
                    front=launch('front',2)
                    pilot.wait_for(lambda:(folder/'front-2.started').exists() or front.poll() is not None,3)
                    (folder/'rejoin-request').write_text('trusted explicit operator startup request; EpochStore must issue the new epoch')
                    pilot.wait_for(lambda:(folder/'rejoined').exists() or central.poll() is not None,5)
                    if not (folder/'rejoined').exists():raise RuntimeError('new real session did not arm')
                    result['surviving_central_rejoined']=True
                elif case=='central-stop':
                    result['injected_crash']={'role':'central','generation':1,'pid':central.pid,'ns':time.monotonic_ns()}
                    central.kill();central.wait(timeout=2)
                    pilot.wait_for(lambda:(folder/'front-protected').exists() or front.poll() is not None,3)
                    if not (folder/'front-protected').exists():raise RuntimeError('Front independent protection missing')
                elif case=='close-full':
                    pilot.wait_for(lambda:(folder/'queue-full').exists() or central.poll() is not None,3)
                    if not (folder/'queue-full').exists():raise RuntimeError('queue never full')
                    result['sender_alive_at_front_close']=central.poll() is None
                    (folder/'stop-front').touch();front.wait(timeout=3)
                    result['sender_alive_after_front_close']=central.poll() is None
                elif case!='invalid':
                    pilot.wait_for(lambda:(folder/'front-protected').exists() or central.poll() is not None,3)
                    pilot.wait_for(lambda:(folder/'central-protected').exists() or central.poll() is not None,1)
                    pilot.wait_for(lambda:(folder/'diagnostics-settled').exists() or central.poll() is not None,1)
                    if case=='delay':pilot.wait_for(lambda:(folder/'delay-drained').exists() or front.poll() is not None,1)
                    (folder/'stop-central').touch()
        central.wait(timeout=8)
        if front:
            (folder/'stop-front').touch();front.wait(timeout=3)
        if case=='close-full':
            # Same netns/veth and physical model, after all first-generation SDK
            # threads returned. Fresh processes get distinct transport identities;
            # the existing durable store must issue the next application Epoch.
            for name in ('stop-front','stop-central','inject','armed','control-established'):
                (folder/name).unlink(missing_ok=True)
            central2=launch('central',2,'normal');front2=launch('front',2,'normal')
            central2.wait(timeout=6);(folder/'stop-front').touch();front2.wait(timeout=3)
            c2=json.loads((folder/'central-2.json').read_text());f2=json.loads((folder/'front-2.json').read_text())
            result['post_full_restart']=central2.returncode==0 and front2.returncode==0 and c2['epoch']==2 and c2['release_ack_mask']==255 and c2['armed_ns']>0 and f2['steering_applied']>=10 and f2['brake_applied']>=10
        (folder/'stop-plant').touch();plant.wait(timeout=3)
        result['pass']=True
    except Exception as e:result['error']=f'{type(e).__name__}: {e}'
    finally:
        # Failure stays failure. Request orderly cleanup first so failed-run evidence
        # is flushed; only an unresponsive process is killed and marked forced.
        for role in ('front','central','plant'):(folder/('stop-'+role)).touch()
        for role,generation,p in procs:
            if p.poll() is None:
                try:p.wait(timeout=2)
                except subprocess.TimeoutExpired:pass
            if p.poll() is None:p.kill();p.wait(timeout=2);result['forced_cleanup'].append(role)
            row={'role':role,'generation':generation,'exit':p.returncode}
            try:row['summary']=json.loads((folder/('plant.json' if role=='plant' else f'{role}-{generation}.json')).read_text())
            except (OSError,ValueError):row['summary_missing']=True
            crash=result.get('injected_crash',{})
            if crash.get('role')==role and crash.get('generation')==generation:row['expected_abrupt_stop']=p.returncode==-signal.SIGKILL
            result['processes'].append(row)
        if capture:
            capture.send_signal(signal.SIGINT)
            try:capture.wait(timeout=2)
            except subprocess.TimeoutExpired:capture.kill();capture.wait();result['capture_forced_cleanup']=True
        for s in streams:s.close()
        result['sanitizer_diagnostics']=any(pilot.sanitizer_errors(p.read_text(errors='replace')) for p in folder.glob('*.stderr'))
        result['expected_sdk_faults'],result['unexpected_sdk_errors']=sdk_outcomes(folder,result)
        result['sdk_errors']=bool(result['unexpected_sdk_errors'])
        result['pass']=result['pass'] and not result['forced_cleanup'] and not result['sanitizer_diagnostics'] and not result['sdk_errors'] and all(r.get('expected_abrupt_stop') or (r['exit']==0 and r.get('summary',{}).get('pass') is True and (r['role']=='plant' or r.get('summary',{}).get('orderly_stop') is True)) for r in result['processes'])
        try:
            result['ip_data_packets']=json.loads((folder/'capture.json').read_text())['ip_data_packets']
            if case!='ready-timeout' and result['ip_data_packets']<4:result['pass']=False
        except (OSError,ValueError):result['pass']=False
        summaries={r['role']:r.get('summary',{}) for r in result['processes'] if not r.get('expected_abrupt_stop') and (case!='close-full' or r['generation']==1)}
        f=summaries.get('front',{});c=summaries.get('central',{})
        if case in ('normal','late','invalid','restart-live'):result['pass']=result['pass'] and c.get('pre_shutdown_protection')==0 and c.get('pending_cancelled')==0 and c.get('release_ack_mask')==255 and f.get('pre_shutdown_protection',0)>=c.get('protected_ns',0) and f.get('steering_applied',0)>=10 and f.get('brake_applied',0)>=10
        if case=='close-full':result['pass']=result['pass'] and result.get('sender_alive_after_front_close',False) and result.get('post_full_restart',False) and f.get('rx_highwater')==8 and f.get('unprocessed_rejected')==8 and f.get('selected_ns',0)>0 and c.get('diagnostic_sent',0)>0 and c.get('diagnostic_sent')==c.get('diagnostic_rejected',0)+c.get('diagnostic_expired',0)
        if case=='overflow':result['pass']=result['pass'] and f.get('rx_highwater')==8 and f.get('pre_shutdown_protection',0)>0
        if case=='invalid':result['pass']=result['pass'] and f.get('pre_init_rejected',0)>=9 and f.get('state_violations')==0 and c.get('diagnostic_rejected')==2
        if case=='restart-live':result['pass']=result['pass'] and result.get('surviving_central_rejoined',False) and c.get('epoch',0)>1 and c.get('release_ack_mask')==255 and c.get('diagnostic_rejected')==1
        if case=='delay':result['pass']=result['pass'] and f.get('expired_rejected',0)>0
        if case=='central-stop':result['pass']=result['pass'] and f.get('pre_shutdown_protection',0)>0 and f.get('selected_ns',0)>0
        if (folder/'sil-io/plant.bin').exists():
            (folder/'plant-snapshot.bin').write_bytes((folder/'sil-io/plant.bin').read_bytes())
        pilot.save(folder/'result.json',result)
    return 0 if result['pass'] else 1

def main():
    p=argparse.ArgumentParser();p.add_argument('--inside',nargs=3)
    p.add_argument('--profile',choices=['normal','asan','tsan'],default='normal');p.add_argument('--fixed-layout',action='store_true')
    p.add_argument('--cases',nargs='+',choices=CASES,default=['normal']);p.add_argument('--normal-repeats',type=int,default=1);p.add_argument('output',nargs='?',type=Path);a=p.parse_args()
    if a.inside:return inside(Path(a.inside[0]),Path(a.inside[1]),a.inside[2])
    if a.fixed_layout and a.profile!='tsan':p.error('fixed-layout is TSan-only')
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    binary=ROOT/f'build/m5-someip-{a.profile}/project/tests/integration/someip/someip_front_adapter'
    rows=[]
    with pilot.open_lock() as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        pilot.save(out/'plan.json',{'profile':a.profile,'cases':a.cases,'normal_repeats':a.normal_repeats,'timeout_s':20,'fixed_layout':a.fixed_layout,'observation_library':os.environ.get('STRATADRIVE_SOMEIP_OBSERVATION_LIB'),'source':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'start_ns':time.time_ns(),'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(HERE.parent.iterdir()) if p.is_file()}})
        for case in a.cases:
            for repeat in range(a.normal_repeats if case=='normal' else 1):
                dest=out/f'{case}-{repeat+1}';dest.mkdir()
                cmd=['unshare','-Urnm',sys.executable,str(HERE),'--inside',str(dest),str(binary),case]
                if a.fixed_layout:cmd=['setarch','x86_64','-R',*cmd]
                code=pilot.supervise(cmd,dest,20);rows.append({'case':case,'repeat':repeat+1,'exit':code});pilot.save(out/'results.json',rows)
    return 0 if all(r['exit']==0 for r in rows) else 1
if __name__=='__main__':sys.exit(main())

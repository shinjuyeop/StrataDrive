#!/usr/bin/env python3
"""Real eight-participant Host adapter. Shared SIL IO is not network evidence."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import resource
import select
import struct
import subprocess
import sys
import time
from datetime import datetime
from sdk_outcomes import sdk_outcomes
from renewal_oracle import renewal_oracle
import run as pilot

ROOT=pilot.ROOT
HERE=Path(__file__).resolve()
CASES=('normal','late','ready-timeout','invalid','delay','command-loss','result-loss','status-loss','lease-loss','overflow','close-full','restart-live','central-stop','owner-pause','monitor-overrun','model-delay')

def config(role,generation=1,three=False):
    if not 1<=generation<=16:raise ValueError('Host test transport identity generation must be in 1..16; no client-ID reuse')
    c=pilot.config(role)
    base={"central":0x5346,"front":0x5344,"rear":0x5348}[role]
    port={'central':30503,'front':30501,'rear':30505}[role]
    if role=='front':c['applications'][0]['id']=hex(0x1421+generation)
    c['services']=[{'service':hex(base+i),'instance':'0x0001','reliable':{'port':port+i,'enable-magic-cookies':'false'}} for i in range(2)]
    if three:
        c['unicast']='10.88.0.'+{'central':'1','front':'2','rear':'3'}[role];c['netmask']='255.255.255.248'
        if role=='rear':c['applications'][0]['id']=hex(0x1521+generation);c['diagnosis']='0x15'
        if role=='central':
            c['services'] += [{'service':hex(0x534a+i),'instance':'0x0001','reliable':{'port':30507+i,'enable-magic-cookies':'false'}} for i in range(2)]
    return c

def normal_prerequisite(folder,central):
    """A fault campaign must first establish unprotected real normal control."""
    for role in ('central','front','rear'):
        if (folder/(role+'-protected')).exists():
            raise RuntimeError(role+' selected protection before declared injection')
    if central.poll() is not None:raise RuntimeError('Central exited before declared injection')
    return (folder/'control-established').exists()

def inside(folder,binary,case):
    procs=[];streams=[];capture=None;loads=[]
    three=bool(os.environ.get('STRATADRIVE_THREE_ECU'));target='rear' if os.environ.get('STRATADRIVE_FAULT_REAR') else 'front'
    peers={};peer_roles=('front','rear') if three else ('front',)
    result={'case':case,'three_ecu':three,'fault_target':target,'pass':False,'processes':[],'forced_cleanup':[],
            'clock_sample':{'monotonic_ns':time.monotonic_ns(),'wall_ns':time.time_ns(),'utc_offset_s':datetime.now().astimezone().utcoffset().total_seconds()}}
    def call(cmd):return subprocess.check_output(list(map(str,cmd)),stderr=subprocess.STDOUT,text=True)
    def launch(role,generation=1,test_override=None):
        prefix=folder/f'{role}-{generation}'
        env=dict(os.environ,LD_LIBRARY_PATH=os.environ.get('STRATADRIVE_SOMEIP_OBSERVATION_LIB',str(binary.parents[4]/'install/lib')),ASAN_OPTIONS='halt_on_error=1:detect_leaks=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1',TSAN_OPTIONS='halt_on_error=0:exitcode=66')
        if role=='plant':cmd=['taskset','-c',('14' if three else '6') if os.environ.get('STRATADRIVE_NATIVE_WATCH') else '3',str(binary),role,str(folder)]
        else:
            cfg=folder/f'{role}.config.json';pilot.save(cfg,config(role,generation,three))
            env.update(VSOMEIP_CONFIGURATION=str(cfg),VSOMEIP_APPLICATION_NAME=role)
            cmd=['ip','netns','exec',role,'unshare','-m','taskset','-c',({'central':'4','front':'5','rear':'6'}[role] if os.environ.get('STRATADRIVE_NATIVE_WATCH') else ('1' if role=='central' else '2')),sys.executable,str(pilot.HERE),'--node',str(binary),role,str(folder),test_override or case,str(generation)]
        pilot.save(Path(str(prefix)+'.command.json'),{'argv':cmd,'env':{k:env[k] for k in env if k.startswith(('VSOMEIP','LD_LIBRARY','ASAN','UBSAN','TSAN','STRATADRIVE_'))}})
        out=open(str(prefix)+'.stdout','w');err=open(str(prefix)+'.stderr','w');streams.extend([out,err])
        p=subprocess.Popen(cmd,env=env,stdout=out,stderr=err);procs.append((role,generation,p));return p
    def watch_snapshot(label):
        records={}
        for role in ('central',*peer_roles,'plant'):
            path=folder/'sil-io'/f'watch-{role}.bin'
            if not path.exists():continue
            before=time.monotonic_ns();data=path.read_bytes();after=time.monotonic_ns()
            (folder/f'{label}-{role}.watch.bin').write_bytes(data)
            if len(data)==160056:
                values=struct.unpack_from('<QQQQIIQQ',data)
                records[role]=dict(zip(('generation','enable','stop','quiesced','epoch','fault_epoch','fault_ns','fault_deadline'),values),snapshot_begin=before,snapshot_end=after)
        pilot.save(folder/f'{label}-watch-channels.json',records)
    def snapshot(role,p):
        record={'pid':p.pid,'netns':os.readlink(f'/proc/{p.pid}/ns/net'),'threads':[],'rtprio':list(resource.prlimit(p.pid,resource.RLIMIT_RTPRIO))}
        for t in sorted(Path(f'/proc/{p.pid}/task').iterdir()):
            try:record['threads'].append({'tid':int(t.name),'name':(t/'comm').read_text().strip(),'affinity':sorted(os.sched_getaffinity(int(t.name))),'policy':os.sched_getscheduler(int(t.name)),'priority':os.sched_getparam(int(t.name)).sched_priority})
            except ProcessLookupError:pass
        pilot.save(folder/f'{role}.runtime.json',record)
        (folder/f'{role}.maps').write_text(Path(f'/proc/{p.pid}/maps').read_text())
        if role!='plant':(folder/f'{role}.sockets.txt').write_text(call(['ip','netns','exec',role,'ss','-antup']))
    try:
        call(['mount','-t','tmpfs','tmpfs','/run'])
        (folder/'sil-io').mkdir()
        call(['mount','-t','tmpfs','-o','size=1m','tmpfs',folder/'sil-io'])
        ecus=('central',*peer_roles)
        for role in ecus:call(['ip','netns','add',role])
        if three:
            call(['ip','link','add','sdbr','type','bridge']);call(['ip','link','set','sdbr','up'])
            for role,dev,address in [('central','sdc','10.88.0.1/29'),('front','sdf','10.88.0.2/29'),('rear','sdr','10.88.0.3/29')]:
                call(['ip','link','add',dev,'type','veth','peer','name',dev+'b'])
                call(['ip','link','set',dev+'b','master','sdbr']);call(['ip','link','set',dev+'b','up']);call(['ip','link','set',dev,'netns',role])
                for args in (['link','set','lo','up'],['addr','add',address,'dev',dev],['link','set',dev,'up'],['route','add','224.0.0.0/4','dev',dev]):call(['ip','netns','exec',role,'ip',*args])
                (folder/f'{role}.network.txt').write_text(call(['ip','netns','exec',role,'ip','-details','addr']))
        else:
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
        if os.environ.get('STRATADRIVE_NATIVE_LOADED'):
            for cpu in ((1,2,7) if three else (1,2)):
                d=folder/f'load-{cpu}';d.mkdir();err=(d/'stderr').open('w');streams.append(err)
                load=subprocess.Popen([sys.executable,str(ROOT/'tests/integration/runtime/check_m4_faults.py'),'--load-child',str(d),'--cpu',str(cpu)],stdout=subprocess.PIPE,stderr=err,text=True)
                loads.append((cpu,load));ready,_,_=select.select([load.stdout],[],[],3)
                if not ready or load.stdout.readline().strip()!='LOAD_READY':raise RuntimeError('load startup failure')
        plant=launch('plant');pilot.wait_for(lambda:(folder/'plant-ready').exists())
        central=launch('central')
        front=None
        if case!='ready-timeout':
            if case=='late':time.sleep(.5)
            for peer_role in peer_roles:peers[peer_role]=launch(peer_role)
            front=peers['front']
            pilot.wait_for(lambda:(folder/'central-1.ready').exists() or central.poll() is not None)
            if central.poll() is not None:raise RuntimeError('Central failed before ready')
            snapshot('central',central);snapshot('plant',plant)
            for peer_role,peer in peers.items():snapshot(peer_role,peer)
            if case not in ('normal','late'):
                pilot.wait_for(lambda:normal_prerequisite(folder,central))
                if os.environ.get('STRATADRIVE_NATIVE_TIMING') and case in ('owner-pause','monitor-overrun'):
                    inject_at=int((folder/'central-1.ready').read_text())+1_200_000_000
                    while time.monotonic_ns()<inject_at:
                        normal_prerequisite(folder,central)
                        time.sleep(min(.002,(inject_at-time.monotonic_ns())/1e9))
                normal_prerequisite(folder,central)
                (folder/'inject').write_text(str(time.monotonic_ns()))
                if case=='model-delay':(folder/'inject-model-delay').touch()
                if case=='restart-live':
                    victim=peers[target]
                    result['injected_crash']={'role':target,'generation':1,'pid':victim.pid,'ns':time.monotonic_ns()}
                    result['survivor_pids_before']={'central':central.pid,**{r:p.pid for r,p in peers.items() if r!=target}}
                    victim.kill();victim.wait(timeout=2)
                    pilot.wait_for(lambda:(folder/'central-protected').exists() or central.poll() is not None,3)
                    if central.poll() is not None:raise RuntimeError('surviving Central failed')
                    for r,p in peers.items():
                        if r!=target:pilot.wait_for(lambda r=r:(folder/(r+'-protected')).exists(),3)
                    watch_snapshot('after-'+target+'-crash')
                    peers[target]=launch(target,2);front=peers['front']
                    pilot.wait_for(lambda:(folder/(target+'-2.started')).exists() or peers[target].poll() is not None,3)
                    (folder/'rejoin-request').write_text('trusted explicit operator startup request; EpochStore must issue the new epoch')
                    pilot.wait_for(lambda:(folder/'rejoined').exists() or central.poll() is not None,5)
                    if not (folder/'rejoined').exists():raise RuntimeError('new real session did not arm')
                    result['surviving_central_rejoined']=True
                    result['survivor_pids_after']={'central':central.pid,**{r:p.pid for r,p in peers.items() if r!=target}}
                    snapshot(target,peers[target])
                elif case=='central-stop':
                    result['injected_crash']={'role':'central','generation':1,'pid':central.pid,'ns':time.monotonic_ns()}
                    central.kill();central.wait(timeout=2)
                    for r,p in peers.items():
                        pilot.wait_for(lambda r=r,p=p:(folder/(r+'-protected')).exists() or p.poll() is not None,3)
                        if not (folder/(r+'-protected')).exists():raise RuntimeError(r+' independent protection missing')
                elif case=='close-full':
                    pilot.wait_for(lambda:(folder/'queue-full').exists() or central.poll() is not None,3)
                    if not (folder/'queue-full').exists():raise RuntimeError('queue never full')
                    result['sender_alive_at_front_close']=central.poll() is None
                    (folder/'stop-front').touch();front.wait(timeout=3)
                    result['sender_alive_after_front_close']=central.poll() is None
                elif case!='invalid':
                    pilot.wait_for(lambda:(folder/(target+'-protected')).exists() or central.poll() is not None,3)
                    pilot.wait_for(lambda:(folder/'central-protected').exists() or central.poll() is not None,1)
                    pilot.wait_for(lambda:(folder/'diagnostics-settled').exists() or central.poll() is not None,1)
                    if case=='delay':pilot.wait_for(lambda:(folder/'delay-drained').exists() or front.poll() is not None,1)
                    # Keep the Central receive endpoint alive while Front publishes
                    # final rejection/protection evidence and returns from SDK stop.
                    for r,p in peers.items():(folder/('stop-'+r)).touch();p.wait(timeout=3)
                    (folder/'stop-central').touch()
        if case in ('normal','late','invalid','restart-live'):
            pilot.wait_for(lambda:(folder/'central-1.quiesced').exists() or central.poll() is not None,8)
            if central.poll() is None:
                for r,p in peers.items():(folder/('stop-'+r)).touch();p.wait(timeout=3)
                (folder/'stop-central').touch()
        central.wait(timeout=8)
        for r,p in peers.items():(folder/('stop-'+r)).touch();p.wait(timeout=3)
        if case in ('close-full','overflow'):
            # Same netns/veth and physical model, after all first-generation SDK
            # threads returned. Fresh processes get distinct transport identities;
            # the existing durable store must issue the next application Epoch.
            for name in ('stop-front','stop-central','inject','armed','control-established'):
                (folder/name).unlink(missing_ok=True)
            central2=launch('central',2,'normal');front2=launch('front',2,'normal')
            pilot.wait_for(lambda:(folder/'central-2.quiesced').exists() or central2.poll() is not None,6)
            (folder/'stop-front').touch();front2.wait(timeout=3);(folder/'stop-central').touch();central2.wait(timeout=3)
            c2=json.loads((folder/'central-2.json').read_text());f2=json.loads((folder/'front-2.json').read_text())
            result['post_full_restart']=central2.returncode==0 and front2.returncode==0 and c2['epoch']==2 and c2['release_ack_mask']==255 and c2['armed_ns']>0 and f2['steering_applied']>=10 and f2['brake_applied']>=10
        (folder/'stop-plant').touch();plant.wait(timeout=3)
        result['pass']=True
    except Exception as e:result['error']=f'{type(e).__name__}: {e}'
    finally:
        # Failure stays failure. Request orderly cleanup first so failed-run evidence
        # is flushed; only an unresponsive process is killed and marked forced.
        for role in (*peer_roles,'central','plant'):(folder/('stop-'+role)).touch()
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
            if case=='model-delay' and role=='plant':
                try:
                    failure=json.loads((folder/'plant-failure.json').read_text())
                    injection=int((folder/'inject').read_text())
                    row['expected_model_failure']=p.returncode==1 and failure['model']=='energy' and failure['site']=='step' and failure['call_ns']>=injection and failure['dt_ns']>=61_000_000 and failure['input_ns']==failure['last_success_ns'] and failure['epoch']>0
                    row['model_failure']=failure
                except (OSError,ValueError,KeyError):row['expected_model_failure']=False
            result['processes'].append(row)
        if capture:
            capture.send_signal(signal.SIGINT)
            try:capture.wait(timeout=2)
            except subprocess.TimeoutExpired:capture.kill();capture.wait();result['capture_forced_cleanup']=True
        result['load_control']=True
        for cpu,load in loads:
            alive=load.poll() is None;load.terminate()
            try:load.wait(timeout=2)
            except subprocess.TimeoutExpired:load.kill();load.wait();alive=False
            try:
                measured=json.loads((folder/f'load-{cpu}/load.json').read_text())
                result['load_control']=result['load_control'] and alive and load.returncode==0 and measured['cpu_ns']>=100_000_000 and measured['affinity']==[cpu] and measured['policy']==0 and measured['priority']==0 and measured['windows']>0
            except (OSError,ValueError,KeyError):result['load_control']=False
        for s in streams:s.close()
        result['sanitizer_diagnostics']=any(pilot.sanitizer_errors(p.read_text(errors='replace')) for p in folder.glob('*.stderr'))
        result['expected_sdk_faults'],result['unexpected_sdk_errors']=sdk_outcomes(folder,result)
        result['sdk_errors']=bool(result['unexpected_sdk_errors'])
        result['pass']=result['pass'] and result['load_control'] and not result.get('capture_forced_cleanup') and not result['forced_cleanup'] and not result['sanitizer_diagnostics'] and not result['sdk_errors'] and all(r.get('expected_abrupt_stop') or r.get('expected_model_failure') or (r['exit']==0 and r.get('summary',{}).get('pass') is True and (r['role']=='plant' or r.get('summary',{}).get('orderly_stop') is True)) for r in result['processes'])
        try:
            result['ip_data_packets']=json.loads((folder/'capture.json').read_text())['ip_data_packets']
            if case!='ready-timeout' and result['ip_data_packets']<4:result['pass']=False
        except (OSError,ValueError):result['pass']=False
        summaries={r['role']:r.get('summary',{}) for r in result['processes'] if not r.get('expected_abrupt_stop') and (case not in ('close-full','overflow') or r['generation']==1)}
        f=summaries.get('front',{});c=summaries.get('central',{})
        if case in ('normal','late','invalid','restart-live'):result['pass']=result['pass'] and c.get('pre_shutdown_protection')==0 and c.get('pending_cancelled')==0 and c.get('release_ack_mask')==255 and f.get('pre_shutdown_protection',0)>=c.get('protected_ns',0) and f.get('steering_applied',0)>=10 and f.get('brake_applied',0)>=10
        if case=='close-full':result['pass']=result['pass'] and result.get('sender_alive_after_front_close',False) and result.get('post_full_restart',False) and f.get('rx_highwater')==8 and f.get('unprocessed_rejected')==8 and f.get('selected_ns',0)>0 and c.get('diagnostic_sent',0)>0 and c.get('diagnostic_sent')==c.get('diagnostic_rejected',0)+c.get('diagnostic_expired',0)
        if case=='overflow':
            from native_oracle import overflow_counters_ok
            result['pass']=result['pass'] and overflow_counters_ok(f,c,result.get('post_full_restart',False))
            import csv
            with (folder/'front-1.events.csv').open() as stream:events=list(csv.DictReader(stream))
            result['overflow_local_cause']=any(e['event']=='transport-overflow' and int(e['ns'])>=f.get('rx_overflow_ns',0) for e in events)
            with (folder/'central-1.events.csv').open() as stream:central_events=list(csv.DictReader(stream))
            result['no_prior_central_protection']=all(int(e['ns'])>f.get('pre_shutdown_protection',0) for e in central_events if e['event']=='protection-request')
            result['pass']=result['pass'] and result['overflow_local_cause'] and result['no_prior_central_protection']
        if case=='invalid':result['pass']=result['pass'] and f.get('pre_init_rejected',0)>=9 and f.get('state_violations')==0 and c.get('diagnostic_rejected')==2
        if case=='restart-live':result['pass']=result['pass'] and result.get('surviving_central_rejoined',False) and c.get('epoch',0)>1 and c.get('release_ack_mask')==255 and c.get('diagnostic_rejected')==1 and result.get('survivor_pids_before')==result.get('survivor_pids_after')
        if case=='delay':result['pass']=result['pass'] and f.get('expired_rejected',0)>0
        if case=='model-delay':result['pass']=result['pass'] and any(r.get('expected_model_failure') for r in result['processes']) and f.get('pre_shutdown_protection',0)>0 and c.get('pre_shutdown_protection',0)>0
        if case=='central-stop':result['pass']=result['pass'] and f.get('pre_shutdown_protection',0)>0 and f.get('selected_ns',0)>0
        watch_snapshot('final')
        if (folder/'sil-io/plant.bin').exists():
            (folder/'plant-snapshot.bin').write_bytes((folder/'sil-io/plant.bin').read_bytes())
        if os.environ.get('STRATADRIVE_NATIVE_WATCH'):
            from native_oracle import native_oracle
            result['native']=native_oracle(folder,case,result,os.environ.get('STRATADRIVE_NATIVE_FIFO') is not None)
            result['pass']=result['pass'] and result['native']['pass']
        if case=='normal':
            result['renewal']=renewal_oracle(folder,three=three)
            result['pass']=result['pass'] and result['renewal']['pass']
        if three:
            from rear_oracle import rear_oracle
            result['rear']=rear_oracle(folder,case,result)
            result['pass']=result['pass'] and result['rear']['pass']
        pilot.save(folder/'result.json',result)
    return 0 if result['pass'] else 1

def main():
    p=argparse.ArgumentParser();p.add_argument('--inside',nargs=3)
    p.add_argument('--three',action='store_true');p.add_argument('--fault-zone',choices=['front','rear'],default='front')
    p.add_argument('--native-watch',action='store_true');p.add_argument('--fifo',action='store_true');p.add_argument('--loaded',action='store_true');p.add_argument('--timing',action='store_true');p.add_argument('--duration-ms',type=int,default=2540)
    p.add_argument('--profile',choices=['normal','asan','tsan'],default='normal');p.add_argument('--fixed-layout',action='store_true')
    p.add_argument('--cases',nargs='+',choices=CASES,default=['normal']);p.add_argument('--normal-repeats',type=int,default=1);p.add_argument('output',nargs='?',type=Path);a=p.parse_args()
    if a.inside:return inside(Path(a.inside[0]),Path(a.inside[1]),a.inside[2])
    if a.fixed_layout and a.profile!='tsan':p.error('fixed-layout is TSan-only')
    if (a.fifo or a.loaded or a.timing) and not a.native_watch:p.error('native-watch required')
    if a.three:
        if any(c not in ('normal','command-loss','owner-pause','central-stop','restart-live') for c in a.cases):p.error('three-ECU protocol supports only its declared finite cases')
        os.environ['STRATADRIVE_THREE_ECU']='1'
    if a.fault_zone=='rear':
        if not a.three:p.error('Rear requires --three')
        os.environ['STRATADRIVE_FAULT_REAR']='1'
    if a.native_watch:
        os.environ['STRATADRIVE_NATIVE_WATCH']='1';os.environ['STRATADRIVE_NATIVE_DURATION_MS']=str(a.duration_ms)
        if a.fifo:os.environ['STRATADRIVE_NATIVE_FIFO']='1'
        if a.loaded:os.environ['STRATADRIVE_NATIVE_LOADED']='1'
        if a.timing:os.environ['STRATADRIVE_NATIVE_TIMING']='1'
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    binary=ROOT/f'build/m5-someip-{a.profile}/project/tests/integration/someip/someip_front_adapter'
    rows=[]
    with pilot.open_lock() as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        pilot.save(out/'plan.json',{'three_ecu':a.three,'fault_target':a.fault_zone,'shutdown_tail_ms':2500 if a.three else 0,'command_renewal':'host10-v1','allocation_period_ns':10_000_000,'permission_support_ns':18_000_000,'management_period_ns':10_000_000,'management_phase_ns':4_000_000,'native_watch':a.native_watch,'fifo':a.fifo,'loaded':a.loaded,'timing':a.timing,'duration_ms':a.duration_ms,'rtprio':list(resource.getrlimit(resource.RLIMIT_RTPRIO)),'allowed_cpus':sorted(os.sched_getaffinity(0)),'profile':a.profile,'cases':a.cases,'normal_repeats':a.normal_repeats,'timeout_s':20,'fixed_layout':a.fixed_layout,'observation_library':os.environ.get('STRATADRIVE_SOMEIP_OBSERVATION_LIB'),'source':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'start_ns':time.time_ns(),'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted([*HERE.parent.glob('*'),*(ROOT/'interfaces/someip').glob('*'),*(ROOT/'simulation/runtime').glob('*.hpp'),*(ROOT/'simulation/runtime').glob('*.cpp')]) if p.is_file()}})
        for case in a.cases:
            for repeat in range(a.normal_repeats if case=='normal' else 1):
                dest=out/f'{case}-{repeat+1}';dest.mkdir()
                cmd=['unshare','-Urnm',sys.executable,str(HERE),'--inside',str(dest),str(binary),case]
                if a.fixed_layout:cmd=['setarch','x86_64','-R',*cmd]
                code=pilot.supervise(cmd,dest,20);rows.append({'case':case,'repeat':repeat+1,'exit':code});pilot.save(out/'results.json',rows)
    return 0 if all(r['exit']==0 for r in rows) else 1
if __name__=='__main__':sys.exit(main())

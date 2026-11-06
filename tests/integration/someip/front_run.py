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
import shutil
import secrets
import tempfile
from datetime import datetime
from sdk_outcomes import sdk_outcomes
from fixture_placement import read_topology, auxiliary_placement
from renewal_oracle import renewal_oracle
import run as pilot

from physical_response import contract

ROOT=pilot.ROOT
HERE=Path(__file__).resolve()
CASES=('normal','late','ready-timeout','invalid','delay','command-loss','result-loss','status-loss','lease-loss','overflow','close-full','restart-live','central-rejoin','central-stop','owner-pause','monitor-overrun','model-delay')

def config(role,generation=1,three=False):
    if not 1<=generation<=16:raise ValueError('Host test transport identity generation must be in 1..16; no client-ID reuse')
    c=pilot.config(role)
    c['applications'][0]['threads']=int(os.environ.get('STRATADRIVE_SDK_IO_THREADS','2'))
    base={"central":0x5346,"front":0x5344,"rear":0x5348}[role]
    port={'central':30503,'front':30501,'rear':30505}[role]
    if role=='central':c['applications'][0]['id']=hex(0x1310+generation)
    if role=='front':c['applications'][0]['id']=hex(0x1421+generation)
    c['services']=[{'service':hex(base+i),'instance':'0x0001','reliable':{'port':port+i,'enable-magic-cookies':'false'}} for i in range(2)]
    if three:
        c['unicast']='10.88.0.'+{'central':'1','front':'2','rear':'3'}[role];c['netmask']='255.255.255.248'
        if role=='rear':c['applications'][0]['id']=hex(0x1521+generation);c['diagnosis']='0x15'
        if role=='central':
            c['services'] += [{'service':hex(0x534a+i),'instance':'0x0001','reliable':{'port':30507+i,'enable-magic-cookies':'false'}} for i in range(2)]
    if os.environ.get('STRATADRIVE_NATIVE_DIAGNOSTICS'):
        sources=[('front',20),('rear',21),('front',22),('front',23),('rear',24),('front',30),('rear',31),('rear',32),('rear',33)]
        services=[]
        for z,peer in enumerate(('front','rear')):
            if role=='central':services.append(0x5e00+2*z)
            elif role==peer:services.append(0x5e01+2*z)
        for i,(peer,_) in enumerate(sources):
            generations=range(2) if os.environ.get('STRATADRIVE_DIAGNOSTIC_PROCESS_RESTART') and not os.environ.get('STRATADRIVE_DIAGNOSTIC_CENTRAL_RESTART') else range(1)
            for incarnation in generations:
                if role!='central' and incarnation>=generation:continue
                base=0x5e10 if incarnation==0 else 0x5e40
                if role=='central':services.append(base+1+2*i)
                elif role==peer:services.append(base+2*i)
        diagnostic_port=31610+('central','front','rear').index(role)
        c['services'] += [{'service':hex(s),'instance':'0x0001','reliable':{'port':diagnostic_port,'enable-magic-cookies':'false'}} for s in services]
        # Diagnostic TCP endpoints need2048; shared SDK local envelope must be
        # at least that size. Control TCP512/wire512 and queues8192 are retained.
        c['max-payload-size-local']=2048
        c['payload-sizes']=[{'unicast':f'10.88.0.{i+1}','ports':[{'port':31610+i,'max-payload-size':2048}]} for i in range(3)]
    return c

def normal_prerequisite(folder,central):
    """A fault campaign must first establish unprotected real normal control."""
    for role in ('central','front','rear'):
        if (folder/(role+'-protected')).exists():
            raise RuntimeError(role+' selected protection before declared injection')
    if central.poll() is not None:raise RuntimeError('Central exited before declared injection')
    return (folder/'control-established').exists() and (not os.environ.get('STRATADRIVE_NATIVE_DIAGNOSTICS') or (folder/'diagnostic-physical-normal').exists())

def inside(folder,binary,case):
    procs=[];streams=[];capture=None;loads=[];observation_captures=[]
    observing=bool(os.environ.get('STRATADRIVE_SDK_OBSERVATION'))
    three=bool(os.environ.get('STRATADRIVE_THREE_ECU'));target='central' if case=='central-rejoin' else 'rear' if os.environ.get('STRATADRIVE_FAULT_REAR') else 'front'
    peers={};peer_roles=('front','rear') if three else ('front',)
    result={'case':case,'three_ecu':three,'fault_target':target,'pass':False,'processes':[],'forced_cleanup':[],
            'energy_cycle':os.environ.get('STRATADRIVE_ENERGY_CYCLE'),'clock_sample':{'monotonic_ns':time.monotonic_ns(),'wall_ns':time.time_ns(),'utc_offset_s':datetime.now().astimezone().utcoffset().total_seconds()}}
    service_profile=bool(os.environ.get('STRATADRIVE_DIAGNOSTIC_SERVICE'))
    if service_profile:
        os.environ.update(STRATADRIVE_SERVICE_PID=str(os.getpid()),STRATADRIVE_SERVICE_UID=str(os.getuid()),STRATADRIVE_SERVICE_CAPABILITY=secrets.token_hex(16))
    diagnostic_store=None
    # Separate durable local spool: it must survive diagnostic-store failure.
    bootstrap_parent=Path(tempfile.mkdtemp(prefix='stratadrive-bootstrap-',dir='/var/tmp'))
    bootstrap_store=bootstrap_parent/'incidents'
    os.environ['STRATADRIVE_BOOTSTRAP_STORE_ROOT']=str(bootstrap_store)
    result['bootstrap_storage']={'path':str(bootstrap_store),'retained':True}
    if os.environ.get('STRATADRIVE_NATIVE_DIAGNOSTICS'):
        # Real persistent local filesystem, outside per-process private /tmp and
        # /dev/shm. Preserve original stores as well as the post-join artifact copy.
        diagnostic_store=Path(tempfile.mkdtemp(prefix='stratadrive-native-diagnostics-',dir='/var/tmp'))
        os.environ['STRATADRIVE_DIAGNOSTIC_STORE_ROOT']=str(diagnostic_store)
        result['diagnostic_storage']={'path':str(diagnostic_store),'filesystem':json.loads(subprocess.check_output(['findmnt','-T',str(diagnostic_store),'-J'],text=True)),'retained':True}
    # Only the newly qualified M6 cases opt in; earlier M5/other fault profiles retain their verdicts.
    if case not in ('normal','command-loss'):
        for k in ('STRATADRIVE_M6_RESPONSE','STRATADRIVE_M6_BRAKE_FLOOR','STRATADRIVE_M6_TORQUE_TOLERANCE'):os.environ.pop(k,None)
    if os.environ.get('STRATADRIVE_M6_RESPONSE'):
        result['physical_response']=contract();pilot.save(folder/'physical-response-contract.json',result['physical_response'])
    def call(cmd):return subprocess.check_output(list(map(str,cmd)),stderr=subprocess.STDOUT,text=True)
    def launch(role,generation=1,test_override=None):
        prefix=folder/f'{role}-{generation}'
        env=dict(os.environ,LD_LIBRARY_PATH=os.environ.get('STRATADRIVE_SOMEIP_OBSERVATION_LIB',str(binary.parents[4]/'install/lib')),ASAN_OPTIONS='halt_on_error=1:detect_leaks=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1',TSAN_OPTIONS='halt_on_error=0:exitcode=66')
        if observing and role!='plant':env['STRATADRIVE_SDK_TRACE']=str(prefix)+'.sdk-internal.csv'
        if role=='plant':cmd=['taskset','-c',('14' if three else '6') if os.environ.get('STRATADRIVE_NATIVE_WATCH') else '3',str(binary),role,str(folder)]
        else:
            cfg=folder/f'{role}.config.json';pilot.save(cfg,config(role,generation,three))
            env.update(VSOMEIP_CONFIGURATION=str(cfg),VSOMEIP_APPLICATION_NAME=role)
            cpu=({'central':'4','front':'5','rear':'6'}[role] if os.environ.get('STRATADRIVE_NATIVE_WATCH') or os.environ.get('STRATADRIVE_SPLIT_OWNER_IO') else
                 {'central':'1','front':'2','rear':'7'}[role] if os.environ.get('STRATADRIVE_ISOLATED_ECUS') else ('1' if role=='central' else '2'))
            cmd=['ip','netns','exec',role,'unshare','-m','taskset','-c',cpu,sys.executable,str(pilot.HERE),'--node',str(binary),role,str(folder),test_override or case,str(generation)]
            # Apply before SDK init/start so SDK descendants and the sender
            # inherit FIFO1. Owners and auxiliary writers explicitly select
            # their own existing policies. chrt failure prevents ECU startup.
            if os.environ.get('STRATADRIVE_SDK_FIFO'):
                cmd=['chrt','--fifo','1',*cmd]
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
        if os.environ.get('STRATADRIVE_SPLIT_OWNER_IO'):
            record['cpu_topology']=read_topology({cpu for thread in record['threads'] for cpu in thread['affinity']})
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
        capture=subprocess.Popen(['ip','netns','exec','central',*(['taskset','-c','0'] if observing or service_profile else []),sys.executable,str(pilot.HERE),'--capture',str(folder),*(['--kernel-timestamps'] if observing else [])],stdout=subprocess.DEVNULL,stderr=caperr)
        pilot.wait_for(lambda:(folder/'capture.ready').exists())
        if observing:
            for peer_role in peer_roles:
                dest=folder/('capture-'+peer_role);dest.mkdir()
                err=(dest/'capture.stderr').open('w');streams.append(err)
                cap=subprocess.Popen(['ip','netns','exec',peer_role,'taskset','-c','0',sys.executable,str(pilot.HERE),
                                      '--capture',str(dest),'--kernel-timestamps','--capture-device',{'front':'sdf','rear':'sdr'}[peer_role]],stdout=subprocess.DEVNULL,stderr=err)
                observation_captures.append((dest,cap));pilot.wait_for(lambda:(dest/'capture.ready').exists())
        env=dict(os.environ,LD_LIBRARY_PATH=os.environ.get('STRATADRIVE_SOMEIP_OBSERVATION_LIB',str(binary.parents[4]/'install/lib')))
        with (folder/'bootstrap.txt').open('w') as log:
            subprocess.run([str(binary),'bootstrap-log-init',str(folder)],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
            subprocess.run([str(binary),'bootstrap',str(folder)],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
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
                if case=='central-rejoin':
                    pilot.wait_for(lambda:(diagnostic_store/'central/central-1.baseline-ready').exists(),3)
                    shutil.copyfile(folder/'central.runtime.json',folder/'central-1.runtime.json')
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
                    if three:pilot.wait_for(lambda:(folder/'physical-protected').exists(),1)
                    watch_snapshot('after-'+target+'-crash')
                    peers[target]=launch(target,2);front=peers['front']
                    pilot.wait_for(lambda:(folder/(target+'-2.started')).exists() or peers[target].poll() is not None,3)
                    (folder/'rejoin-request').write_text('trusted explicit operator startup request; EpochStore must issue the new epoch')
                    pilot.wait_for(lambda:(folder/'rejoined').exists() or central.poll() is not None,5)
                    if not (folder/'rejoined').exists():raise RuntimeError('new real session did not arm')
                    result['surviving_central_rejoined']=True
                    result['survivor_pids_after']={'central':central.pid,**{r:p.pid for r,p in peers.items() if r!=target}}
                    snapshot(target,peers[target])
                elif case=='central-rejoin':
                    result['injected_crash']={'role':'central','generation':1,'pid':central.pid,'ns':time.monotonic_ns()}
                    result['survivor_pids_before']={r:p.pid for r,p in peers.items()}
                    central.kill();central.wait(timeout=2)
                    for r,p in peers.items():
                        pilot.wait_for(lambda r=r:(folder/(r+'-protected')).exists(),3)
                        if p.poll() is not None:raise RuntimeError('surviving '+r+' failed')
                    pilot.wait_for(lambda:(folder/'physical-protected').exists(),1)
                    watch_snapshot('after-central-crash')
                    (folder/'rejoin-request').write_text('trusted explicit operator startup; new durable epoch required')
                    central=launch('central',2)
                    pilot.wait_for(lambda:(folder/'central-2-rejoined').exists() or central.poll() is not None,5)
                    if not (folder/'central-2-rejoined').exists():raise RuntimeError('new Central session did not arm')
                    result['central_rejoined']=True
                    result['survivor_pids_after']={r:p.pid for r,p in peers.items()}
                    snapshot('central',central)
                    if service_profile:
                        from native_service_client import run as run_service
                        result['service']=run_service(folder,central)
                elif case=='central-stop':
                    result['injected_crash']={'role':'central','generation':1,'pid':central.pid,'ns':time.monotonic_ns()}
                    central.kill();central.wait(timeout=2)
                    for r,p in peers.items():
                        pilot.wait_for(lambda r=r,p=p:(folder/(r+'-protected')).exists() or p.poll() is not None,3)
                        if not (folder/(r+'-protected')).exists():raise RuntimeError(r+' independent protection missing')
                    if three:pilot.wait_for(lambda:(folder/'physical-protected').exists(),1)
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
                    if three:pilot.wait_for(lambda:(folder/'physical-protected').exists(),1)
                    # Keep the Central receive endpoint alive while Front publishes
                    # final rejection/protection evidence and returns from SDK stop.
                    for r,p in peers.items():(folder/('stop-'+r)).touch();p.wait(timeout=3)
                    (folder/'stop-central').touch()
        if case in ('normal','late','invalid','restart-live','central-rejoin'):
            pilot.wait_for(lambda:(folder/('central-2.quiesced' if case=='central-rejoin' else 'central-1.quiesced')).exists() or central.poll() is not None,11 if os.environ.get('STRATADRIVE_ENERGY_CYCLE') else 8)
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
        for role in peer_roles:(folder/('stop-'+role)).touch()
        # Retain the failed Central's protected receive endpoint while remote
        # durable publishers finish their bounded final ACK drain.
        if service_profile:
            for p in peers.values():
                if p.poll() is None:
                    try:p.wait(timeout=3)
                    except subprocess.TimeoutExpired:pass
        for role in ('central','plant'):(folder/('stop-'+role)).touch()
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
            try:capture.wait(timeout=5 if service_profile else 2)
            except subprocess.TimeoutExpired:capture.kill();capture.wait();result['capture_forced_cleanup']=True
        if observing:
            for dest,cap in observation_captures:
                if cap.poll() is None:cap.send_signal(signal.SIGINT)
                try:cap.wait(timeout=2)
                except subprocess.TimeoutExpired:cap.kill();cap.wait();result['capture_forced_cleanup']=True
            try:
                traces=[json.loads((folder/f'{r["role"]}-{r["generation"]}.sdk-internal.csv.json').read_text())
                        for r in result['processes'] if r['role']!='plant' and not r.get('expected_abrupt_stop')]
                captures=[json.loads((dest/'capture.json').read_text()) for dest in [folder,*(d for d,_ in observation_captures)]]
                result['sdk_observation']={'traces':traces,'captures':captures,
                    'complete':bool(traces) and len(captures)==len(peer_roles)+1 and all(t['complete'] and t['rows']>0 for t in traces)
                               and all(c['normal_exit'] and c['socket_drops']==0 for c in captures)
                               and capture is not None and capture.returncode==0 and all(c.returncode==0 for _,c in observation_captures)}
            except (OSError,ValueError,KeyError) as exc:result['sdk_observation']={'complete':False,'error':str(exc)}
            result['pass']=result['pass'] and result['sdk_observation']['complete']
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
        if diagnostic_store is not None:
            shutil.copytree(diagnostic_store,folder/'native-diagnostics')
        if bootstrap_store.exists():
            shutil.copytree(bootstrap_store,folder/'bootstrap-incidents')
            audit=subprocess.run([sys.executable,str(HERE.parent.parent/'diagnostics/audit_bootstrap_incidents.py'),str(bootstrap_store)],capture_output=True,text=True)
            try:result['bootstrap_audit']=json.loads(audit.stdout)
            except ValueError:result['bootstrap_audit']={'integrity':False,'error':audit.stderr}
            result['pass']=result['pass'] and audit.returncode==0 and result['bootstrap_audit'].get('all_succeeded',False)
        result['sanitizer_diagnostics']=any(pilot.sanitizer_errors(p.read_text(errors='replace')) for p in folder.glob('*.stderr'))
        result['expected_sdk_faults'],result['unexpected_sdk_errors']=sdk_outcomes(folder,result)
        result['sdk_errors']=bool(result['unexpected_sdk_errors'])
        result['pass']=result['pass'] and result['load_control'] and not result.get('capture_forced_cleanup') and not result['forced_cleanup'] and not result['sanitizer_diagnostics'] and not result['sdk_errors'] and all(r.get('expected_abrupt_stop') or r.get('expected_model_failure') or (r['exit']==0 and r.get('summary',{}).get('pass') is True and (r['role']=='plant' or r.get('summary',{}).get('orderly_stop') is True)) for r in result['processes'])
        try:
            result['packet_capture']=json.loads((folder/'capture.json').read_text())
            result['ip_data_packets']=result['packet_capture']['ip_data_packets']
            result['pass']=result['pass'] and result['packet_capture']['normal_exit'] and result['packet_capture'].get('socket_drops',0)==0 and not result['packet_capture'].get('overflow',False)
            if case!='ready-timeout' and result['ip_data_packets']<4:result['pass']=False
        except (OSError,ValueError):result['pass']=False
        summaries={r['role']:r.get('summary',{}) for r in result['processes'] if not r.get('expected_abrupt_stop') and (case not in ('close-full','overflow') or r['generation']==1)}
        f=summaries.get('front',{});c=summaries.get('central',{})
        if case in ('normal','late','invalid','restart-live','central-rejoin'):result['pass']=result['pass'] and (c.get('pre_shutdown_protection',0)>=c.get('normal_stop_complete',0)>0 if service_profile else c.get('pre_shutdown_protection')==0) and c.get('pending_cancelled')==0 and c.get('release_ack_mask')==255 and f.get('pre_shutdown_protection',0)>=c.get('protected_ns',0) and f.get('steering_applied',0)>=10 and f.get('brake_applied',0)>=10
        if case=='close-full':
            from native_oracle import close_full_oracle
            result['close_full']=close_full_oracle(folder,f,c,result)
            result['pass']=result['pass'] and result['close_full']['pass']
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
        if case=='central-rejoin':result['pass']=result['pass'] and result.get('central_rejoined',False) and c.get('epoch')==(3 if service_profile else 2) and result.get('survivor_pids_before')==result.get('survivor_pids_after')
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
        if os.environ.get('STRATADRIVE_NATIVE_DIAGNOSTICS'):
            try:
                result['diagnostics']={r:json.loads((folder/'native-diagnostics'/r/(r+('-2.json' if case in ('restart-live','central-rejoin') and r==target else '-1.json'))).read_text()) for r in ('central','front','rear')}
                result['pass']=result['pass'] and all(r['pass'] for r in result['diagnostics'].values())
            except (OSError,ValueError,KeyError) as e:
                result['pass']=False;result['diagnostic_error']=str(e)
        if case=='normal':
            result['renewal']=renewal_oracle(folder,three=three)
            result['pass']=result['pass'] and result['renewal']['pass']
        if three:
            from rear_oracle import rear_oracle
            result['rear']=rear_oracle(folder,case,result)
            result['pass']=result['pass'] and result['rear']['pass']
        if os.environ.get('STRATADRIVE_SIMPLE_VEHICLE'):
            from vehicle_oracle import vehicle_oracle
            result['vehicle']=vehicle_oracle(folder,case)
            result['pass']=result['pass'] and result['vehicle']['pass']
        if os.environ.get('STRATADRIVE_ENERGY_CYCLE'):
            from energy_oracle import energy_oracle
            result['energy']=energy_oracle(folder,case,os.environ['STRATADRIVE_ENERGY_CYCLE'])
            result['pass']=result['pass'] and result['energy']['pass']
        pilot.save(folder/'result.json',result)
    return 0 if result['pass'] else 1

def main():
    p=argparse.ArgumentParser();p.add_argument('--inside',nargs=3)
    p.add_argument('--sdk-observation',action='store_true',help='isolated observation SDK plus three kernel packet captures')
    p.add_argument('--sdk-io-threads',type=int,choices=(1,2),default=2,help='declared SDK IO threads on each existing SDK CPU')
    p.add_argument('--energy-cycle',choices=['nominal','no-charge']);p.add_argument('--simple-vehicle',action='store_true');p.add_argument('--three',action='store_true');p.add_argument('--fault-zone',choices=['front','rear'],default='front')
    p.add_argument('--isolated-ecus',action='store_true',help='functional profile: separate Central/Front/Rear on CPU1/2/7; plant3 and diagnostic writer15')
    p.add_argument('--split-owner-io',action='store_true',help='functional profile: SDK CPU4/5/6 and original owners1/2/7; SCHED_OTHER without native-watch')
    p.add_argument('--separate-aux-io',action='store_true',help='split profile: put all auxiliary IO on a physical core separate from owners, plant and SDK')
    p.add_argument('--owner-fifo',action='store_true',help='split functional profile with Central FIFO11 and Zone FIFO18; SDK/IO remain SCHED_OTHER')
    p.add_argument('--sdk-fifo',action='store_true',help='opt-in finite normal service profile: SDK/sender FIFO1 on dedicated CPU4/5/6')
    p.add_argument('--service-fault',choices=['ack-loss','actual-loss','stop-request-loss','stop-ack-loss'])
    p.add_argument('--signal-write-delay-ms',type=int,default=0,help='declared fixture-only armed marker write delay on the IO thread')
    p.add_argument('--native-watch',action='store_true');p.add_argument('--fifo',action='store_true');p.add_argument('--loaded',action='store_true');p.add_argument('--timing',action='store_true');p.add_argument('--duration-ms',type=int,default=2540)
    p.add_argument('--profile',choices=['normal','asan','tsan'],default='normal');p.add_argument('--fixed-layout',action='store_true')
    p.add_argument('--service-hold-ms',type=int,default=500,help='terminal service observation per normal epoch, 500..60000ms; original control budgets stay fixed')
    p.add_argument('--diagnostic-service',action='store_true');p.add_argument('--diagnostics',action='store_true');p.add_argument('--diagnostic-drop-ack',action='store_true');p.add_argument('--diagnostic-context-delay-ms',type=int,default=0);p.add_argument('--diagnostic-restart',choices=['central','front','rear','all'])
    p.add_argument('--cases',nargs='+',choices=CASES,default=['normal']);p.add_argument('--normal-repeats',type=int,default=1);p.add_argument('output',nargs='?',type=Path);a=p.parse_args()
    if a.inside:return inside(Path(a.inside[0]),Path(a.inside[1]),a.inside[2])
    os.environ.pop('STRATADRIVE_SDK_FIFO',None)
    if a.sdk_fifo:
        if not (a.owner_fifo and a.split_owner_io and a.separate_aux_io and a.diagnostic_service and a.profile=='normal') or a.sdk_observation:
            p.error('sdk-fifo requires noninstrumented terminal service with split owner/FIFO/separate auxiliary placement')
        os.environ['STRATADRIVE_SDK_FIFO']='1'
    if a.sdk_io_threads!=2 and not a.split_owner_io:p.error('sdk-io-threads=1 requires split-owner-io')
    os.environ['STRATADRIVE_SDK_IO_THREADS']=str(a.sdk_io_threads)
    if a.sdk_observation:
        if not a.split_owner_io or not os.environ.get('STRATADRIVE_SOMEIP_OBSERVATION_LIB'):
            p.error('sdk-observation requires split-owner-io and an isolated observation library path')
        os.environ['STRATADRIVE_SDK_OBSERVATION']='1'
    if a.fixed_layout and a.profile!='tsan':p.error('fixed-layout is TSan-only')
    if a.isolated_ecus:
        if not a.three or a.native_watch:p.error('isolated-ecus requires three ECUs without native-watch')
        required={1,2,3,7} | (set() if a.separate_aux_io else {15})
        if not required.issubset(os.sched_getaffinity(0)):p.error('isolated-ecus CPU placement unavailable')
        os.environ['STRATADRIVE_ISOLATED_ECUS']='1'
    if a.split_owner_io:
        if not a.isolated_ecus or not a.diagnostic_service:p.error('split-owner-io requires isolated terminal service')
        if not {1,2,3,4,5,6,7}.issubset(os.sched_getaffinity(0)):p.error('split owner/SDK CPU placement unavailable')
        os.environ['STRATADRIVE_SPLIT_OWNER_IO']='1'
    placement=None
    os.environ.pop('STRATADRIVE_AUX_IO_CPU',None)
    if a.separate_aux_io and not a.split_owner_io:p.error('separate-aux-io requires split-owner-io')
    if a.split_owner_io:
        try:
            allowed=os.sched_getaffinity(0)
            placement=auxiliary_placement(allowed,read_topology(allowed),a.separate_aux_io)
        except (OSError,ValueError,KeyError) as error:p.error(str(error))
        os.environ['STRATADRIVE_AUX_IO_CPU']=str(placement['cpu'])
    if a.owner_fifo:
        if not a.split_owner_io:p.error('owner-fifo requires split-owner-io')
        os.environ['STRATADRIVE_OWNER_FIFO']='1'
    if 'central-rejoin' in a.cases and not a.diagnostics:p.error('central-rejoin requires the declared diagnostics fixture')
    if a.diagnostic_service:
        if not a.diagnostics or a.cases!=['central-rejoin'] or a.native_watch or not a.simple_vehicle:p.error('terminal service requires isolated diagnostics central-rejoin with simple-vehicle and without native-watch')
        os.environ['STRATADRIVE_DIAGNOSTIC_SERVICE']='1'
    if not 500<=a.service_hold_ms<=60000 or (a.service_hold_ms!=500 and not a.diagnostic_service):p.error('service-hold-ms requires terminal service and 500..60000ms')
    if a.diagnostic_service:os.environ['STRATADRIVE_SERVICE_HOLD_MS']=str(a.service_hold_ms)
    if a.service_fault:
        if not a.diagnostic_service:p.error('service-fault requires diagnostic-service')
        os.environ['STRATADRIVE_SERVICE_FAULT']=a.service_fault
    if a.signal_write_delay_ms:
        if not a.diagnostic_service or not 1<=a.signal_write_delay_ms<=1000:p.error('signal delay requires terminal service and 1..1000ms')
        os.environ['STRATADRIVE_SIGNAL_WRITE_DELAY_MS']=str(a.signal_write_delay_ms)
    if a.diagnostics:
        if not a.three or any(c not in ('normal','command-loss','restart-live','central-rejoin') for c in a.cases):p.error('native diagnostics requires three ECUs and normal/command-loss/restart-live')
        if not 0<=a.diagnostic_context_delay_ms<=1500:p.error('diagnostic context delay must be in0..1500ms')
        os.environ['STRATADRIVE_NATIVE_DIAGNOSTICS']='1';os.environ['STRATADRIVE_DIAGNOSTIC_CONTEXT_DELAY_MS']=str(a.diagnostic_context_delay_ms)
        if any(c in ('restart-live','central-rejoin') for c in a.cases):
            if len(a.cases)!=1 or a.diagnostic_restart:p.error('process restart must be an isolated case')
            os.environ['STRATADRIVE_DIAGNOSTIC_PROCESS_RESTART']='1'
            if a.cases==['central-rejoin']:os.environ['STRATADRIVE_DIAGNOSTIC_CENTRAL_RESTART']='1'
        if a.diagnostic_restart:os.environ['STRATADRIVE_DIAGNOSTIC_RESTART']=a.diagnostic_restart
        if a.diagnostic_drop_ack:os.environ['STRATADRIVE_DIAGNOSTIC_DROP_ACK']='1'
    elif a.diagnostic_drop_ack or a.diagnostic_context_delay_ms or a.diagnostic_restart:p.error('diagnostics required')
    if (a.fifo or a.timing or (a.loaded and not a.diagnostic_service)) and not a.native_watch:p.error('native-watch required')
    if a.loaded and a.diagnostic_service:
        if not a.owner_fifo or a.profile!='normal':p.error('loaded terminal service requires normal profile and owner-fifo')
        os.environ['STRATADRIVE_NATIVE_LOADED']='1'
    if a.energy_cycle:
        if not (a.three and a.simple_vehicle and a.native_watch):p.error('energy-cycle requires three/simple-vehicle/native-watch')
        if a.duration_ms not in (2540,8000):p.error('energy-cycle-v1 has a fixed 8000ms observation')
        a.duration_ms=8000;os.environ['STRATADRIVE_ENERGY_CYCLE']=a.energy_cycle
        response=contract();os.environ.update(STRATADRIVE_M6_RESPONSE=response['revision'],STRATADRIVE_M6_BRAKE_FLOOR=str(response['brake_floor_pa']),STRATADRIVE_M6_TORQUE_TOLERANCE=str(response['torque_tolerance_nm']))
    if a.simple_vehicle:
        if not a.three:p.error('simple-vehicle requires three ECUs')
        os.environ['STRATADRIVE_SIMPLE_VEHICLE']='1'
    if a.three:
        if any(c not in ('normal','command-loss','owner-pause','central-stop','restart-live','central-rejoin') for c in a.cases):p.error('three-ECU protocol supports only its declared finite cases')
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
    if a.sdk_observation:
        libraries={}
        for directory in os.environ['STRATADRIVE_SOMEIP_OBSERVATION_LIB'].split(':'):
            for library in sorted(Path(directory).glob('*.so*')):
                if library.is_file() and library.name not in libraries:
                    libraries[library.name]={'path':str(library.resolve()),'sha256':hashlib.sha256(library.read_bytes()).hexdigest()}
        pilot.save(out/'observation-plan.json',{'mode':'sdk-stages-v1','libraries':libraries,
            'capture_cpu':0,'timestamp':'SO_TIMESTAMPNS_NEW','per_frame_clock_bracket':True,
            'complete_traces_exclude_only_declared_SIGKILL':True})
    binary=ROOT/f'build/m5-someip-{a.profile}/project/tests/integration/someip/someip_front_adapter'
    rows=[]
    with pilot.open_lock() as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        pilot.save(out/'plan.json',{'physical_response_cases':['normal','command-loss'] if a.energy_cycle else [],'physical_response':contract() if a.energy_cycle else None,'energy_cycle':a.energy_cycle,'simple_vehicle':a.simple_vehicle,'three_ecu':a.three,'diagnostics':a.diagnostics,'diagnostic_service':a.diagnostic_service,'isolated_ecus':a.isolated_ecus,'split_owner_io':a.split_owner_io,'auxiliary_placement':placement,'owner_fifo':a.owner_fifo,'sdk_fifo':a.sdk_fifo,'service_fault':a.service_fault,'service_hold_ms':a.service_hold_ms,'signal_write_delay_ms':a.signal_write_delay_ms,'fixture_signal_poll_ns':1000000,'fixture_signal_observation':'role-subscriptions-v1','functional_owner_idle_wait_us':1000,'sender_wakeup':'enqueue-notification','diagnostic_central_restart':'central-rejoin' in a.cases and a.diagnostics,'diagnostic_process_restart':any(c in ('restart-live','central-rejoin') for c in a.cases) and a.diagnostics,'diagnostic_drop_ack':a.diagnostic_drop_ack,'diagnostic_restart':a.diagnostic_restart,'diagnostic_context_delay_ms':a.diagnostic_context_delay_ms,'fault_target':'central' if 'central-rejoin' in a.cases else a.fault_zone,'shutdown_tail_ms':2500 if a.three else 0,'command_renewal':'host10-v1','allocation_period_ns':10_000_000,'permission_support_ns':18_000_000,'management_period_ns':10_000_000,'management_phase_ns':4_000_000,'native_watch':a.native_watch,'fifo':a.fifo,'loaded':a.loaded,'timing':a.timing,'duration_ms':a.duration_ms,'rtprio':list(resource.getrlimit(resource.RLIMIT_RTPRIO)),'allowed_cpus':sorted(os.sched_getaffinity(0)),'profile':a.profile,'cases':a.cases,'normal_repeats':a.normal_repeats,'timeout_s':(25 if a.energy_cycle else 20)+2*(a.service_hold_ms-500)/1000,'fixed_layout':a.fixed_layout,'sdk_io_threads':a.sdk_io_threads,'observation_library':os.environ.get('STRATADRIVE_SOMEIP_OBSERVATION_LIB'),'source':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'start_ns':time.time_ns(),'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted([*HERE.parent.glob('*'),*(ROOT/'central/diagnostics').glob('*'),*(ROOT/'central/coordinator').glob('*'),*(ROOT/'tests/integration/diagnostics').glob('*.py'),*(ROOT/'interfaces/someip').glob('*'),*(ROOT/'simulation/runtime').glob('*.hpp'),*(ROOT/'simulation/runtime').glob('*.cpp'),*(ROOT/'simulation/vehicle').glob('*'),*(ROOT/'simulation/power').glob('*'),*(ROOT/'central/control_allocation').glob('*')]) if p.is_file()}})
        for case in a.cases:
            for repeat in range(a.normal_repeats if case=='normal' else 1):
                dest=out/f'{case}-{repeat+1}';dest.mkdir()
                cmd=['unshare','-Urnm',sys.executable,str(HERE),'--inside',str(dest),str(binary),case]
                if a.fixed_layout:cmd=['setarch','x86_64','-R',*cmd]
                code=pilot.supervise(cmd,dest,(25 if a.energy_cycle else 20)+2*(a.service_hold_ms-500)/1000);rows.append({'case':case,'repeat':repeat+1,'exit':code});pilot.save(out/'results.json',rows)
    return 0 if all(r['exit']==0 for r in rows) else 1
if __name__=='__main__':sys.exit(main())

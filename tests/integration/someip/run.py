#!/usr/bin/env python3
"""Fixed netns/veth campaign. Every failed attempt is retained, exit status is 1."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import socket
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve()
CASES = ('normal','late','ready-timeout','invalid','delay','overflow','close-busy','restart','restart-live')

def save(path, value):
    path.write_text(json.dumps(value,indent=2)+'\n')

def open_lock(root=ROOT):
    path=root/'build/.m4-exclusive.lock'
    path.parent.mkdir(parents=True,exist_ok=True)
    return path.open('a')

def config(role):
    return {'unicast':'10.88.0.'+('1' if role=='central' else '2'),
        'netmask':'255.255.255.252','network':'sd-'+role,'routing':role,
        'applications':[{'name':role,'id':'0x1311' if role=='central' else '0x1422',
                         'threads':2,'max_dispatchers':1,'max_dispatch_time':100}],
        'logging':{'level':'warning','console':'true','dlt':'false'},
        'max-payload-size-reliable':512,'max-payload-size-local':1024,
        'endpoint-queue-limit-external':8192,'endpoint-queue-limit-local':8192,
        'diagnosis':'0x13' if role=='central' else '0x14',
        'npdu-default-timings':{'debounce-time-request':0,'debounce-time-response':0,
                              'max-retention-time-request':0,'max-retention-time-response':0},
        'services':([{'service':'0x5344','instance':'0x0001','reliable':{'port':30501,'enable-magic-cookies':'false'}}] if role=='front' else []),
        'service-discovery':{'enable':'true','multicast':'239.255.1.1','port':30490,
            'protocol':'udp','initial_delay_min':10,'initial_delay_max':50,
            'repetitions_base_delay':100,'repetitions_max':3,'ttl':3,'cyclic_offer_delay':500}}

def wait_for(predicate, seconds=5):
    end=time.monotonic()+seconds
    while not predicate():
        if time.monotonic()>=end: raise TimeoutError('expected transition not observed')
        time.sleep(.002)

def summary_ok(row):
    s=row.get('summary',{})
    return row.get('exit')==0 and s.get('pass') is True and s.get('orderly_stop') is True and s.get('control_gate_open') is False

def sanitizer_errors(text):
    return bool(re.search(r'ThreadSanitizer|AddressSanitizer|LeakSanitizer|runtime error:',text))

def supervise(cmd, dest, seconds):
    with (dest/'supervisor.txt').open('w') as log:
        child=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:return child.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid,signal.SIGKILL);child.wait()
            save(dest/'supervisor-timeout.json',{'timeout_s':seconds,'forced_cleanup':True,'child_exit':child.returncode})
            return 1

def capture_packets(folder):
    """AF_PACKET in caller-owned netns; no tcpdump setgroups/root drop required."""
    active=True; count=0
    def stop(*_):
        nonlocal active
        active=False
    signal.signal(signal.SIGINT,stop)
    sock=socket.socket(socket.AF_PACKET,socket.SOCK_RAW,socket.htons(3))
    sock.bind(('sdc',0));sock.settimeout(.1)
    with (folder/'traffic.pcap').open('wb') as output:
        output.write(struct.pack('<IHHIIII',0xa1b2c3d4,2,4,0,0,65535,1))
        (folder/'capture.ready').touch()
        while active:
            try: frame=sock.recv(65535)
            except socket.timeout:continue
            if len(frame)<34 or frame[12:14]!=b'\x08\x00':continue
            stamp=time.time_ns();output.write(struct.pack('<IIII',stamp//10**9,(stamp//1000)%10**6,len(frame),len(frame)));output.write(frame)
            iplen=(frame[14]&15)*4
            if frame[23]==6 and len(frame)>=14+iplen+20:
                tcp=14+iplen;ports=struct.unpack('!HH',frame[tcp:tcp+4])
                size=struct.unpack('!H',frame[16:18])[0]-iplen-((frame[tcp+12]>>4)*4)
                if 30501 in ports and size>0:count+=1
    sock.close();save(folder/'capture.json',{'ip_data_packets':count,'interface':'sdc','normal_exit':True})

def inside(folder, binary, case):
    folder=folder.resolve(); processes=[]; streams=[]; capture=None
    result={'case':case,'processes':[],'pass':False,'forced_cleanup':[]}
    def call(cmd): return subprocess.check_output(cmd,stderr=subprocess.STDOUT,text=True)
    def launch(role,epoch):
        prefix=folder/f'{role}-{epoch}'; cfg=folder/f'{role}.config.json';save(cfg,config(role))
        env=dict(os.environ,VSOMEIP_CONFIGURATION=str(cfg),VSOMEIP_APPLICATION_NAME=role,
                 LD_LIBRARY_PATH=str(binary.parents[4]/'install/lib'),
                 ASAN_OPTIONS='halt_on_error=1:detect_leaks=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1',
                 TSAN_OPTIONS='halt_on_error=0:exitcode=66')
        # Separate mount namespaces prevent /tmp UDS and /dev/shm shortcuts.
        cmd=['ip','netns','exec',role,'unshare','-m','taskset','-c','1' if role=='central' else '2',
             sys.executable,str(HERE),'--node',str(binary),role,str(folder),case,str(epoch)]
        save(Path(str(prefix)+'.command.json'),{'argv':cmd,'env':{k:env[k] for k in ('VSOMEIP_CONFIGURATION','VSOMEIP_APPLICATION_NAME','LD_LIBRARY_PATH','ASAN_OPTIONS','UBSAN_OPTIONS','TSAN_OPTIONS')}})
        out=open(str(prefix)+'.stdout','w');err=open(str(prefix)+'.stderr','w');streams.extend([out,err])
        p=subprocess.Popen(cmd,stdout=out,stderr=err,env=env);processes.append((role,epoch,p));return p
    def snapshot(role,epoch,p):
        record={'pid':p.pid,'netns':os.readlink(f'/proc/{p.pid}/ns/net'),'threads':[]}
        for t in sorted(Path(f'/proc/{p.pid}/task').iterdir()):
            try: record['threads'].append({'tid':int(t.name),'name':(t/'comm').read_text().strip(),
                    'affinity':sorted(os.sched_getaffinity(int(t.name))), 'policy':os.sched_getscheduler(int(t.name)),
                    'priority':os.sched_getparam(int(t.name)).sched_priority})
            except ProcessLookupError: pass
        save(folder/f'{role}-{epoch}.runtime.json',record)
        (folder/f'{role}-{epoch}.maps').write_text(Path(f'/proc/{p.pid}/maps').read_text())
        (folder/f'{role}-{epoch}.sockets.txt').write_text(call(['ip','netns','exec',role,'ss','-antup']))
    try:
        call(['mount','-t','tmpfs','tmpfs','/run'])
        for role in ('central','front'): call(['ip','netns','add',role])
        call(['ip','link','add','sdc','type','veth','peer','name','sdf'])
        for role,dev,address in [('central','sdc','10.88.0.1/30'),('front','sdf','10.88.0.2/30')]:
            call(['ip','link','set',dev,'netns',role])
            for args in (['link','set','lo','up'],['addr','add',address,'dev',dev],['link','set',dev,'up'],['route','add','224.0.0.0/4','dev',dev]):
                call(['ip','netns','exec',role,'ip',*args])
            (folder/f'{role}.network.txt').write_text(call(['ip','netns','exec',role,'ip','-details','addr']))
        caperr=(folder/'capture.stderr').open('w');streams.append(caperr)
        capture=subprocess.Popen(['ip','netns','exec','central',sys.executable,str(HERE),'--capture',str(folder)],stdout=subprocess.DEVNULL,stderr=caperr)
        wait_for(lambda:(folder/'capture.ready').exists())
        epochs=(42,43) if case=='restart' else (42,)
        for epoch in epochs:
            central=launch('central',epoch)
            if case=='ready-timeout': central.wait(timeout=5);continue
            if case=='late': time.sleep(.5) # intentional fault, never readiness proof
            front=launch('front',epoch)
            wait_for(lambda:(folder/f'central-{epoch}.ready').exists() or central.poll() is not None)
            if central.poll() is not None: raise RuntimeError('Central failed before readiness')
            snapshot('central',epoch,central);snapshot('front',epoch,front)
            (folder/f'grant-{epoch}').write_text('trusted component fixture only; no global Release/RunLease\n')
            if case=='restart-live':
                wait_for(lambda:(folder/'restart-request').exists() or central.poll() is not None)
                if not (folder/'restart-request').exists():raise RuntimeError('live restart phase not reached')
                result['injected_peer_kill']={'pid':front.pid,'time_ns':time.monotonic_ns()}
                front.kill();front.wait(timeout=2)
                wait_for(lambda:(folder/'central-observed-down').exists() or central.poll() is not None)
                if central.poll() is not None:raise RuntimeError('surviving Central failed')
                (folder/'rejoin-43').write_text('explicit trusted local new Epoch; not learned from network\n')
                front=launch('front',43)
                wait_for(lambda:(folder/'central-43.ready').exists() or central.poll() is not None)
                if central.poll() is not None:raise RuntimeError('new peer readiness failed')
                snapshot('front',43,front)
                (folder/'grant-43').write_text('new local component fixture grant\n')
                central.wait(timeout=5)
                (folder/'stop-43').touch();front.wait(timeout=3)
                result['surviving_central_rejoined']=(folder/'live-rejoined').exists()
                continue
            if case=='close-busy':
                wait_for(lambda:(folder/'busy').exists() or central.poll() is not None)
                if not (folder/'busy').exists(): raise RuntimeError('busy sender not reached')
                result['sender_alive_at_front_close']=central.poll() is None
                (folder/f'stop-{epoch}').touch(); front.wait(timeout=3)
                result['sender_alive_after_front_close']=central.poll() is None
            central.wait(timeout=5)
            if case=='restart' and epoch==42:
                result['injected_peer_kill']={'pid':front.pid,'time_ns':time.monotonic_ns()}
                front.kill();front.wait(timeout=2)
            elif front.poll() is None:
                (folder/f'stop-{epoch}').touch();front.wait(timeout=3)
        result['pass']=True
    except Exception as e: result['error']=f'{type(e).__name__}: {e}'
    finally:
        for role,epoch,p in processes:
            if p.poll() is None:
                p.kill();p.wait(timeout=2);result['forced_cleanup'].append([role,epoch])
            row={'role':role,'epoch':epoch,'exit':p.returncode}
            try:row['summary']=json.loads((folder/f'{role}-{epoch}.json').read_text())
            except (OSError,ValueError):row['summary_missing']=True
            if case in ('restart','restart-live') and role=='front' and epoch==42 and result.get('injected_peer_kill'):
                row['expected_abrupt_stop']=p.returncode==-signal.SIGKILL
            result['processes'].append(row)
        if capture:
            capture.send_signal(signal.SIGINT)
            try: capture.wait(timeout=2)
            except subprocess.TimeoutExpired: capture.kill();capture.wait();result['capture_forced_cleanup']=True
        for s in streams:s.close()
        result['sanitizer_diagnostics']=any(sanitizer_errors(p.read_text(errors='replace')) for p in folder.glob('*.stderr'))
        result['sdk_errors']=any('[error]' in p.read_text(errors='replace') for p in folder.glob('*.stdout'))
        result['pass']=result['pass'] and not result['forced_cleanup'] and not result['sanitizer_diagnostics'] and all(
            r.get('expected_abrupt_stop') or summary_ok(r) for r in result['processes'])
        result['pass']=result['pass'] and not result['sdk_errors']
        try:
            result['ip_data_packets']=json.loads((folder/'capture.json').read_text())['ip_data_packets']
            if case!='ready-timeout' and result['ip_data_packets']<4:result['pass']=False
        except Exception as e: result['capture_error']=str(e);result['pass']=False
        if case=='overflow':
            rows=[r.get('summary',{}) for r in result['processes'] if r['role']=='front']
            result['pass']=result['pass'] and bool(rows) and all(r.get('overflow') and r.get('highwater')==8 and r.get('frames')==0 and r.get('fault_protection_calls',0)>0 for r in rows)
        if case=='delay':
            result['pass']=result['pass'] and all(r.get('summary',{}).get('frames')==0 and r.get('summary',{}).get('fault_protection_calls',0)>0 for r in result['processes'] if r['role']=='front')
        if case=='close-busy':
            clients=[r.get('summary',{}) for r in result['processes'] if r['role']=='central']
            result['pass']=result['pass'] and result.get('sender_alive_after_front_close',False) and bool(clients) and all(
                0<r.get('busy_peak',0)<=8 and r.get('busy_sent')==r.get('busy_rejected',0)+r.get('busy_expired',0)
                and r.get('busy_rejected',0)>0 for r in clients)
        if case=='restart-live':result['pass']=result['pass'] and result.get('surviving_central_rejoined',False)
        save(folder/'result.json',result)
    return 0 if result['pass'] else 1

def main():
    p=argparse.ArgumentParser();p.add_argument('--inside',nargs=3);p.add_argument('--node',nargs=5);p.add_argument('--capture',type=Path)
    p.add_argument('--profile',choices=['normal','asan','tsan'],default='normal');p.add_argument('--cases',nargs='+',choices=CASES,default=list(CASES))
    p.add_argument('--fixed-layout',action='store_true',help='TSan only: process-local setarch -R, no kernel setting changes')
    p.add_argument('--normal-repeats',type=int,default=1);p.add_argument('output',nargs='?',type=Path);a=p.parse_args()
    if a.capture:return capture_packets(a.capture)
    if a.node:
        subprocess.run(['mount','-t','tmpfs','tmpfs','/tmp'],check=True)
        subprocess.run(['mount','-t','tmpfs','tmpfs','/dev/shm'],check=True)
        os.execv(a.node[0],a.node)
    if a.inside:return inside(Path(a.inside[0]),Path(a.inside[1]),a.inside[2])
    if a.fixed_layout and a.profile!='tsan':p.error('--fixed-layout is a TSan diagnostic launch option')
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    binary=ROOT/f'build/m5-someip-{a.profile}/project/tests/integration/someip/someip_pilot'
    save(out/'plan.json',{'profile':a.profile,'cases':a.cases,'normal_repeats':a.normal_repeats,'timeout_s':15,'fixed_layout':a.fixed_layout,
         'source':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'binary':str(binary),'start_ns':time.time_ns(),
         'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
         'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted(HERE.parent.iterdir()) if p.is_file()}})
    rows=[]
    with open_lock() as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for case in a.cases:
            for repeat in range(a.normal_repeats if case=='normal' else 1):
                dest=out/f'{case}-{repeat+1}';dest.mkdir()
                cmd=['unshare','-Urnm',sys.executable,str(HERE),'--inside',str(dest),str(binary),case]
                if a.fixed_layout:cmd=['setarch','x86_64','-R',*cmd]
                code=supervise(cmd,dest,15)
                rows.append({'case':case,'repeat':repeat+1,'exit':code})
                save(out/'results.json',rows)
    return 0 if all(r['exit']==0 for r in rows) else 1

if __name__=='__main__':sys.exit(main())

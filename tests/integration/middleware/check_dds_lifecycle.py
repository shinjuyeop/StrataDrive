#!/usr/bin/env python3
"""Fixed gate-closed SDK diagnostics. No SDK fetch, suppression or production build.
Normal/ASan/TSan are separate runs. Expected peer SIGKILL is never sanitizer PASS.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
CASES = ('normal', 'peer-stop', 'peer-kill', 'restart', 'callback-delete', 'overflow', 'partial')
PROFILES = {
    'normal': ('build/m4-communication-research/install', 'build/m4-readiness', ''),
    'asan-ubsan': ('build/m4-dds-lifetime/asan-install', 'build/m1-angle-sanitized', 'address,undefined'),
    'tsan': ('build/m4-sdk-followup/dds-official/install', 'build/m4-tsan', 'thread'),
}
SRC = ROOT/'build/m4-communication-research/deps/cyclonedds-src/eclipse-cyclonedds-cyclonedds-e54e991'
LIBS = ('owner_wire','zone_feedback_contract','steering_frame_codec','steering_angle_codec',
        'brake_codec','drive_codec','bms_receiver','bms_codec','actuator_receiver_state','actuator_payload_codec','e2e_profile5')

def save(path, value): path.write_text(json.dumps(value, indent=2)+'\n')
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def lifetime_result(text):
    # Sanitizer stderr can precede stdout in the combined preserved log.
    result={}
    for line in text.splitlines():
        if not line.startswith('{'):continue
        try:value=json.loads(line)
        except ValueError:continue
        if isinstance(value,dict):result=value
    return result

def wait_for(predicate, seconds=12):
    end=time.monotonic()+seconds
    while not predicate():
        if time.monotonic()>=end: raise TimeoutError('readiness/transition not observed')
        time.sleep(.005)

def inside(folder, binary, case):
    folder=folder.resolve(); processes=[]; streams=[]; result={'case':case,'control_gate_open':False,'processes':[]}
    def call(cmd): subprocess.run(cmd,check=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    try:
        call(['mount','-t','tmpfs','tmpfs','/run'])
        for role in ('central','zone'): call(['ip','netns','add',role])
        call(['ip','link','add','sdc','type','veth','peer','name','sdz'])
        for role,dev,ip in [('central','sdc','10.88.0.1/30'),('zone','sdz','10.88.0.2/30')]:
            call(['ip','link','set',dev,'netns',role])
            for args in (['link','set','lo','up'],['addr','add',ip,'dev',dev],['link','set',dev,'up']):call(['ip','netns','exec',role,'ip',*args])
        def launch(role,epoch):
            prefix=folder/f'{role}-{epoch}'
            verbosity='warning' if os.environ.get('SD_LIFETIME_TRACE')=='off' else 'finest'
            env=dict(os.environ,CYCLONEDDS_URI=f'<CycloneDDS><Domain Id="37"><General><AllowMulticast>false</AllowMulticast></General><Discovery><ParticipantIndex>auto</ParticipantIndex><Peers><Peer Address="10.88.0.1"/><Peer Address="10.88.0.2"/></Peers></Discovery><Tracing><Verbosity>{verbosity}</Verbosity><OutputFile>{prefix}.trace</OutputFile></Tracing></Domain></CycloneDDS>')
            out=open(str(prefix)+'.json','w');err=open(str(prefix)+'.stderr','w');streams.extend((out,err))
            cmd=['ip','netns','exec',role,'taskset','-c','1',str(binary),role,str(folder),case,str(epoch)]
            if os.environ.get('SD_GDB_ZONE')=='1' and role=='zone' and epoch==42:
                cmd=cmd[:7]+['timeout','--signal=INT','--kill-after=2s','6s','gdb','--batch','-ex','set pagination off','-ex','run','-ex','thread apply all bt','--args']+cmd[7:]
            save(Path(str(prefix)+'.command.json'),{'argv':cmd,'CYCLONEDDS_URI':env['CYCLONEDDS_URI']})
            process=subprocess.Popen(cmd,stdout=out,stderr=err,env=env);processes.append((role,epoch,process));return process
        central=launch('central',42);zone=launch('zone',42)
        wait_for(lambda: all((folder/f'{r}-42.matched').exists() for r in ('central','zone')))
        (folder/'go').write_text(str(time.monotonic_ns()))
        if case=='peer-kill':
            wait_for(lambda:(folder/'zone-42.progress').exists());result['kill_ns']=time.monotonic_ns();zone.kill();zone.wait(timeout=3)
        elif case=='restart':
            if os.environ.get('SD_COORDINATED_RESTART'):
                wait_for(lambda:(folder/'zone-42.progress').exists())
                result['quiesce_ns']=time.monotonic_ns();(folder/'quiesce').write_text('explicit sender pause')
                time.sleep(.15)  # drain grace, never renews any original20ms envelope
                result['close42_ns']=time.monotonic_ns();(folder/'close42').write_text('close after draining')
            zone.wait(timeout=10);result['old_peer_exit']=zone.returncode
            new=launch('zone',43)
            wait_for(lambda:(folder/'zone-43.matched').exists())
            result['explicit_epoch43_ns']=time.monotonic_ns();(folder/'epoch43').write_text('43');(folder/'go43').write_text(str(time.monotonic_ns()))
        for role,epoch,process in processes:
            code=process.wait(timeout=15)
            row={'role':role,'epoch':epoch,'exit':code}
            if case=='peer-kill' and role=='zone':row['expected_kill']=code==-signal.SIGKILL
            else:
                try: row['summary']=json.loads((folder/f'{role}-{epoch}.json').read_text())
                except (ValueError,OSError) as error:row['summary_error']=str(error)
            result['processes'].append(row)
        valid=all((r.get('expected_kill') or r.get('summary',{}).get('functional') is True) for r in result['processes'])
        valid=valid and all(not r.get('summary',{}).get('control_gate_open',True) for r in result['processes'] if not r.get('expected_kill'))
        result['functional']='PASS' if valid else 'FAIL'
        result['process_exit_ok']=all(r.get('expected_kill') or r['exit']==0 for r in result['processes'])
    except Exception as error:result.update(functional='FAIL',error=f'{type(error).__name__}: {error}')
    finally:
        for _,_,p in processes:
            if p.poll() is None:p.kill();p.wait()
        for stream in streams:stream.close()
        # Preserve every process even if readiness/transition/wait failed first.
        recorded={(r['role'],r['epoch']) for r in result['processes']}
        for role,epoch,process in processes:
            if (role,epoch) in recorded:continue
            row={'role':role,'epoch':epoch,'exit':process.returncode,'cleanup_after_error':True}
            try:row['summary']=json.loads((folder/f'{role}-{epoch}.json').read_text())
            except (ValueError,OSError) as error:row['summary_error']=str(error)
            result['processes'].append(row)
        save(folder/'result.json',result)
    return 0 if result.get('functional')=='PASS' and result.get('process_exit_ok') else 1

def main():
    p=argparse.ArgumentParser();p.add_argument('output',type=Path,nargs='?');p.add_argument('--inside',nargs=3);p.add_argument('--followup',action='store_true');p.add_argument('--lifetimes',action='store_true');a=p.parse_args()
    if a.inside:return inside(Path(a.inside[0]),Path(a.inside[1]),a.inside[2])
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    cases=('lifetime',) if a.lifetimes else (('normal','restart') if a.followup else CASES)
    plan={'base':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'sdk':'11.0.1 e54e991 unchanged',
          'scope':'gate-closed functional/lifetime diagnostics, not production timing or controller',
          'profiles':list(PROFILES),'cases':list(cases),'repetitions':1,'lifecycle_runs':3*len(cases),'bucket_runs':0 if a.followup or a.lifetimes else 3,'whc_runs':3 if a.lifetimes else 0,
          'case_timeout_s':35,'bucket_timeout_s':15,'campaign_timeout_s':600,'storage_limit_bytes':536870912,
          'criteria':{'normal':'60 current exact identity requests accepted and echoed; no control authority',
              'peer-stop/kill':'traffic before peer exit; original last valid deadline expires; no synthesized ACK',
              'restart':'explicit local epoch43 only; old42 unchanged bytes rejected as old/expired; fresh43 accepted; gate closed',
              'callback-delete':'delete starts with callback active; API returns after callback ended; context outlives participant',
              'overflow':'SDK KEEP_ALL/resource8 queues stall400ms; expired data rejected; queues bounded8',
              'partial':'delete reply writer during traffic; real next dds_write fails; link latch blocks further sends',
              'bucket':'actual original bucket retained under awake scope across real entity index resize; free after final access and quiescence',
              'sanitizer':'any unexplained warning, timeout, missing output or nonzero process exit FAIL; deliberate peer SIGKILL separately labelled'},
          'sanitizers':{'TSAN_OPTIONS':'halt_on_error=0:exitcode=66:history_size=7','ASAN_OPTIONS':'detect_leaks=1:exitcode=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'}}
    plan['followup']=a.followup
    if a.followup:plan['hypothesis']='Full allocation unwind+finest SDK observer perturbs20ms delivery; compare disabled intrusive observer with unchanged source/deadline/CPU. Separately quiesce sender and drain before old peer delete to break full-RHC/GC wait. Original raw deletion timeout remains OPEN.'
    if a.lifetimes:plan['hypothesis']='Real proxy GUID/participant/lease/mutex lookup via unchanged pinned hopscotch source, per-object access/quiescence/free recording; real WHC object held through SDK Writer removal. Not normal delivery timing acceptance, prior failures unchanged.'
    save(out/'plan.json',plan)
    files=['run_probe.py','dds_bucket_lifetime.c','dds_lifecycle_probe.cpp','dds_lifecycle_inspect.c','dds_writer_lifetime.c','dds_allocation_trace.hpp','check_dds_lifecycle.py']
    save(out/'metadata.json',{'sources':{f:sha(HERE/f) for f in files},'kernel':platform.release(),'uid':os.getuid(),'python':platform.python_version(),
        'sdk_libraries':{k:sha(ROOT/v[0]/'lib/libddsc.so.11') for k,v in PROFILES.items()}})
    case_order=(('whc',*cases) if a.lifetimes else ((*cases,) if a.followup else ('bucket',*cases)))
    rows=[{'profile':profile,'case':case,'verdict':'NOT RUN','reason':'build or previous stage not completed'} for profile in PROFILES for case in case_order]
    save(out/'results.json',rows)
    with (ROOT/'build/.m4-exclusive.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        commands=[]
        includes=['-I'+str(ROOT/d) for d in ['interfaces/remote','interfaces/zone','interfaces/central','interfaces/steering','interfaces/common','interfaces/brake','interfaces/drive','interfaces/bms','interfaces/session','build/m4-probe-tsan/tests/integration/middleware']]
        for profile,(sdk,libs,sanitizer) in PROFILES.items():
            dest=out/profile;dest.mkdir();prefix=ROOT/sdk
            flags=['-O1','-g','-fno-omit-frame-pointer','-Wall','-Wextra','-Werror','-pthread']+(['-fsanitize='+sanitizer] if sanitizer else [])
            inc=includes+['-I'+str(prefix/'include'),'-I'+str(SRC/'src/core/ddsc/src')]
            packet=ROOT/'build/m4-probe-tsan/tests/integration/middleware/packet.c'
            commands.append(['gcc','-std=c11',*flags,*inc,'-c',str(packet),'-o',str(dest/'packet.o')])
            commands.append(['gcc','-std=c11',*flags,*inc,str(HERE/'dds_bucket_lifetime.c'),str(dest/'packet.o'),'-L'+str(prefix/'lib'),'-Wl,-rpath,'+str(prefix/'lib'),'-lddsc','-o',str(dest/'bucket-probe')])
            commands.append(['gcc','-std=c11',*flags,*inc,'-c',str(HERE/'dds_lifecycle_inspect.c'),'-o',str(dest/'inspect.o')])
            commands.append(['gcc','-std=c11','-D_POSIX_C_SOURCE=200809L','-ffunction-sections','-fdata-sections',*flags,*inc,'-c',str(SRC/'src/ddsrt/src/hopscotch.c'),'-o',str(dest/'hopscotch.o')])
            commands.append(['gcc','-std=c11',*flags,*inc,str(HERE/'dds_writer_lifetime.c'),str(dest/'packet.o'),'-L'+str(prefix/'lib'),'-Wl,-rpath,'+str(prefix/'lib'),'-lddsc','-o',str(dest/'whc-probe')])
            commands.append(['g++','-std=c++17',*flags,*inc,'-Wl,--gc-sections',str(HERE/'dds_lifecycle_probe.cpp'),str(dest/'packet.o'),str(dest/'inspect.o'),str(dest/'hopscotch.o'),*[str(ROOT/libs/('lib'+lib+'.a')) for lib in LIBS],'-L'+str(prefix/'lib'),'-Wl,-rpath,'+str(prefix/'lib'),'-lddsc','-o',str(dest/'lifecycle-probe')])
        save(out/'build-commands.json',commands)
        for i,cmd in enumerate(commands):
            with (out/f'build-{i}.log').open('w') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=90)
            if r.returncode:return r.returncode
        began=time.monotonic()
        for profile,(_,_,san) in PROFILES.items():
            env={**os.environ,**plan['sanitizers']};dest=out/profile
            if a.followup:env.update(SD_LIFETIME_TRACE='off',SD_COORDINATED_RESTART='1')
            for case in case_order:
                folder=dest/case;folder.mkdir()
                cmd=([str(dest/'bucket-probe')] if case=='bucket' else ([str(dest/'whc-probe'),'--whc'] if case=='whc' else ['unshare','-Urnm',sys.executable,str(Path(__file__).resolve()),'--inside',str(folder),str(dest/'lifecycle-probe'),case]))
                if san=='thread':cmd=['setarch','x86_64','-R',*cmd]
                save(folder/'command.json',{'argv':cmd,'sanitizers':plan['sanitizers'],'observer':'off' if a.followup else 'full','coordinated_restart':a.followup})
                cap=15 if case in ('bucket','whc') else 35
                with (folder/'run.log').open('w') as log:
                    try:
                        with subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True) as process:
                            try:code=process.wait(timeout=cap)
                            except subprocess.TimeoutExpired:
                                try:os.killpg(process.pid,signal.SIGKILL)
                                except ProcessLookupError:pass
                                process.wait();code=124
                    except OSError as error:code=127;(folder/'launch-error.txt').write_text(str(error))
                logs=[folder/'run.log',*folder.glob('*.stderr')];text='\n'.join(f.read_text(errors='replace') for f in logs)
                warnings=text.count('WARNING: ThreadSanitizer')
                bad=any(x in text for x in ('WARNING: ThreadSanitizer','FATAL: ThreadSanitizer','ERROR: AddressSanitizer','ERROR: LeakSanitizer','runtime error:'))
                detail=json.loads((folder/'result.json').read_text()) if (folder/'result.json').exists() else {}
                if case in ('bucket','whc'):
                    detail=lifetime_result((folder/'run.log').read_text())
                    functional='PASS' if detail.get('free_held')==0 and detail.get('last_access_ns',1)<=detail.get('scope_end_ns',0)<=detail.get('free_ns',0) else 'FAIL'
                else:functional=detail.get('functional','FAIL')
                row={'profile':profile,'case':case,'exit':code,'functional':functional,'tsan_warnings':warnings,'sanitizer_clean':not bad,'verdict':'PASS' if code==0 and not bad and functional=='PASS' else 'FAIL','result':detail}
                index=next(i for i,r in enumerate(rows) if r['profile']==profile and r['case']==case);rows[index]=row
                save(out/'results.json',rows);print(json.dumps({k:v for k,v in row.items() if k!='result'}),flush=True)
                if time.monotonic()-began>600 or sum(f.stat().st_size for f in out.rglob('*') if f.is_file())>536870912:
                    (out/'limit-stop.txt').write_text('campaign time/storage cap reached; remaining NOT RUN\n');return 2
        before=json.loads((out/'metadata.json').read_text())['sources']
        stable=all(sha(HERE/f)==h for f,h in before.items())
        save(out/'source-stability.json',{'unchanged':stable})
        return 0 if stable and len(rows)==plan['lifecycle_runs']+plan['bucket_runs']+plan['whc_runs'] and all(r['verdict']=='PASS' for r in rows) else 1
if __name__=='__main__':raise SystemExit(main())

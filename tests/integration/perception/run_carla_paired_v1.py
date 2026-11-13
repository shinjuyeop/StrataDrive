#!/usr/bin/env python3
"""Two runner-owned servers, one original native physical owner, finite paired case."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import secrets
import signal
import socket
import subprocess
import time
import traceback

from run_carla_control_shadow_v1 import verify,sha,original_owner_runtime
from renderer_shutdown_v1 import allow_shutdown_tracer,shutdown,capture
from carla_readiness_v1 import wait_ready


def main(a):
    root=Path(__file__).resolve().parents[3];a.output.mkdir(parents=True,exist_ok=False)
    report=dict(schema='m10-paired-server-v1',status='FAIL',condition=a.condition,attempts=1,
                started_utc=datetime.now(timezone.utc).isoformat(),export_hz=a.export_hz,
                control_authority='unchanged native owner; perception diagnostic only')
    processes={};logs=[];client=None;first_interrupt=first_crash=None;ini=a.source/'Unreal/CarlaUE4/Saved/Config/Linux/GameUserSettings.ini'
    original=ini.read_bytes();report['original_ini_sha256']=hashlib.sha256(original).hexdigest()
    def hook():resource.setrlimit(resource.RLIMIT_CORE,(0,0));allow_shutdown_tracer()
    try:
        report['freeze_sha256']=verify(a.freeze)
        profile=json.loads((root/'profiles/perception-source-compare-server-v2.json').read_text())
        expected=original_owner_runtime(a.freeze,a.source,a.engine,profile)
        for path,digest in expected.items():
            if sha(a.source/path)!=digest:raise ValueError('original runtime identity '+path)
        for path in ('/d','/tmp'):
            v=os.statvfs(path);free=v.f_bavail*v.f_frsize;report.setdefault('free_bytes',{})[path]=free
            if free<4*1024**3:raise ValueError('insufficient paired evidence space: '+path)
        guards=[]
        try:
            for port in (2200,2201,2202,2300,2301,2302):
                s=socket.socket();guards.append(s);s.bind(('127.0.0.1',port))
        finally:
            for s in guards:s.close()
        base=[str(a.engine/'Engine/Binaries/Linux/UE4Editor'),str(a.source/'Unreal/CarlaUE4/CarlaUE4.uproject'),
            '/Game/Carla/Maps/Town03_Opt','-game','-FixedSeed','-RenderOffScreen','-nosound','-unattended','-nosplash',
            '-carla-server','-quality-level=Epic',
            '-ExecCmds=r.SceneRenderTargetResizeMethod 2,r.SceneRenderTargetResizeMethodForceOverride 1',
            '-ini:EditorSettings:[/Script/UnrealEd.CrashReportsPrivacySettings]:bSendUnattendedBugReports=False',
            '-ini:Engine:[CrashReportClient]:bAgreeToCrashUpload=False,[CrashReportClient]:bImplicitSend=False',
            '-log','-stdout','-FullStdOutLogOutput']
        common=dict(os.environ,OMP_WAIT_POLICY='PASSIVE');common.pop('STRATADRIVE_M7_OWNER_KEY',None)
        if common.get('LD_PRELOAD'):raise ValueError('unexpected preload')
        owner_env=dict(common,STRATADRIVE_M7_OWNER_KEY=secrets.token_hex(32))
        commands=dict(renderer=base+['-carla-rpc-port=2300'],owner=base+['-carla-rpc-port=2200',
            '-StrataM7NativeProbe','-StrataM7V1Substeps320','-StrataM7SolverWork','-StrataM7CompactWork',
            '-StrataM7WallNative','-StrataM7HeldSteerSleep','-StrataM7Wall5ms','-nullrhi','-norenderthread'])
        report['argv']=commands
        for role in ('renderer','owner'):
            log=(a.output/f'{role}.log').open('w');logs.append(log)
            processes[role]=subprocess.Popen(commands[role],env=owner_env if role=='owner' else common,
                stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=hook)
        report['pids']={k:p.pid for k,p in processes.items()}
        for port in (2200,2300):
            report.setdefault('readiness',{})[str(port)]=wait_ready(
                a.python,port,a.output/f'readiness-{port}.log',common)
        command=[str(a.python),str(Path(__file__).with_name('carla_control_shadow_v1.py')),
            '--output',str(a.output/'capture'),'--native',str(a.native),'--model',str(root/'tools/carla/m7_nodrive/virtual_ev_v1.json'),
            '--scenario',str(root/'tests/integration/carla/scenarios/m7_integrated_v1.txt'),
            '--ticks','400','--warmup-ticks','150','--step-ms','5','--execution-profile','owner5ms','--camera-absent-control',
            '--wall-clock',str(secrets.randbits(63) or 1),'--detector',str(a.detector),'--models',str(a.models),
            '--library',str(a.library),'--paired-renderer-port','2300','--paired-renderer-pid',str(processes['renderer'].pid),
            '--paired-condition',a.condition,'--paired-export-hz',str(a.export_hz)]
        report['client_argv']=command
        log=(a.output/'client.log').open('w');logs.append(log)
        client=subprocess.Popen(command,env=owner_env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        deadline=time.monotonic()+900;diagnosed=False;first_interrupt=None
        while client.poll() is None or (first_interrupt and processes['renderer'].poll() is None):
            now=time.monotonic_ns();renderer=processes['renderer']
            if renderer.poll() is not None and 'renderer_exit_observed_ns' not in report:
                report['renderer_exit_observed_ns']=now;report['renderer_injected_exit_code']=renderer.returncode
            control=a.output/'capture/paired/control.json'
            if control.exists():
                events=json.loads(control.read_text())
                for event in events:
                    if event['action']=='SIGINT':first_interrupt=event['wall_ns']
                    if event['action']=='SIGKILL':first_crash=event['wall_ns'];report['renderer_injected_crash_ns']=first_crash
                report['fault_events']=events
            if first_interrupt:
                report['renderer_first_sigint_ns']=first_interrupt
                elapsed=(now-first_interrupt)/1e9
                if renderer.poll() is None and elapsed>=10 and not diagnosed:
                    report['injected_shutdown_diagnostic']=capture(renderer,a.output/'injected-shutdown',min(8,max(.001,30-elapsed)))
                    diagnosed=True
                if renderer.poll() is None and elapsed>=30:
                    os.killpg(renderer.pid,signal.SIGKILL);renderer.wait(timeout=10)
                    report['renderer_injected_forced_stop']=True
            if time.monotonic()>deadline:raise TimeoutError('finite paired client horizon')
            time.sleep(.05)
        report['client_exit']=client.returncode
        if verify(a.freeze)!=report['freeze_sha256']:raise ValueError('frozen input changed during live')
        if client.returncode:raise RuntimeError('paired physical client failed; original failure retained')
        report['status']='EXECUTED_REQUIRES_AUDIT'
    except Exception:report['error']=traceback.format_exc()
    finally:
        if client is not None and client.poll() is None:
            os.killpg(client.pid,signal.SIGTERM)
            try:client.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(client.pid,signal.SIGKILL);client.wait()
            report['client_forced_stop']=True
        for role in ('renderer','owner'):
            process=processes.get(role)
            if process:
                if role=='renderer':
                    try:os.kill(process.pid,signal.SIGCONT)
                    except ProcessLookupError:pass
                if role=='renderer' and first_interrupt:
                    # The injected exit owns its deadline, including exceptional
                    # client exits. Cleanup must never begin a fresh 30s allowance.
                    remaining=max(0,30-(time.monotonic_ns()-first_interrupt)/1e9)
                    forced=False
                    try:process.wait(timeout=remaining)
                    except subprocess.TimeoutExpired:
                        forced=True;os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=10)
                    result=dict(begin_wall_ns=first_interrupt,end_wall_ns=time.monotonic_ns(),
                                limit_seconds=30,server_exit=process.returncode,forced_stop=forced)
                elif role=='renderer' and first_crash and process.poll() is not None:
                    result=dict(begin_wall_ns=first_crash,end_wall_ns=time.monotonic_ns(),
                                server_exit=process.returncode,forced_stop=False,injected_crash=True)
                else:result=shutdown(process,a.output/role,diagnostics=True)
                report.setdefault('shutdown',{})[role]=result
                expected_exit=-9 if role=='renderer' and a.condition=='stall-crash' and first_crash else 130
                if result['server_exit']!=expected_exit or result.get('forced_stop'):report['status']='FAIL'
        if report.get('renderer_injected_forced_stop') or report.get('client_forced_stop'):report['status']='FAIL'
        ini.write_bytes(original);report['restored_ini_sha256']=sha(ini)
        for log in logs:log.close()
        (a.output/'server.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('status','error') if k in report}))
    return 0 if report['status']=='EXECUTED_REQUIRES_AUDIT' else 1


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('engine','source','python','native','detector','models','library','freeze','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--condition',choices=('normal','stall-exit','stall-crash'),required=True)
    p.add_argument('--export-hz',type=int,choices=(20,50),default=20)
    raise SystemExit(main(p.parse_args()))

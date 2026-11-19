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
from endurance_profile_v1 import limits,camera_pacing
from endurance_resources_v1 import resources,endurance_runtime
from endurance_host_v1 import load_profile,command as placed_command,owner_command,check_owner,ENV
from owner_split_profile_v1 import WALL_PROFILES


def main(a):
    bounds=limits(a.endurance_seconds)
    if a.endurance_seconds and (a.condition!='normal' or a.export_hz!=20 or a.endurance_build is None):
        raise ValueError('declared normal20Hz endurance build required')
    wall_profile=getattr(a,'wall_profile','wall5-hv30-v1')
    if wall_profile not in WALL_PROFILES or (wall_profile=='wall5-hv50-v1' and not a.endurance_seconds):
        raise ValueError('explicit bounded owner5ms HV policy')
    if getattr(a,'release_recording_cache',False) and not (a.endurance_seconds and a.raw_recording):
        raise ValueError('closed raw endurance shards only')
    if getattr(a,'native_service_us',1000)!=1000 and not (a.endurance_seconds and a.profile_state_path):
        raise ValueError('profiled endurance native service cadence')
    if getattr(a,'cuda_resize_library',None) and not (a.endurance_seconds and a.tensor_workspace and a.resize_threads==0):
        raise ValueError('explicit endurance CUDA resize with tensor workspace and zero CPU resize threads')
    root=Path(__file__).resolve().parents[3];a.output.mkdir(parents=True,exist_ok=False)
    report=dict(schema='m10-paired-server-v1',status='FAIL',condition=a.condition,attempts=1,
                started_utc=datetime.now(timezone.utc).isoformat(),export_hz=a.export_hz,endurance_seconds=a.endurance_seconds,
                requested_intervals=bounds['frames'],resources=[],
                control_authority='unchanged native owner; perception diagnostic only')
    processes={};logs=[];client=None;first_interrupt=first_crash=None;ini=a.source/'Unreal/CarlaUE4/Saved/Config/Linux/GameUserSettings.ini'
    original=ini.read_bytes();report['original_ini_sha256']=hashlib.sha256(original).hexdigest()
    stock_ini=None;stock_original=None
    def hook():resource.setrlimit(resource.RLIMIT_CORE,(0,0));allow_shutdown_tracer()
    try:
        report['freeze_sha256']=verify(a.freeze)
        if getattr(a,'resource_profile',None):
            if not a.endurance_seconds:raise ValueError('explicit endurance host scope')
            frozen=json.loads(a.freeze.read_text())
            relative=str(a.resource_profile.resolve().relative_to(root))
            if frozen['files'].get(relative,{}).get('sha256')!=sha(a.resource_profile):raise ValueError('unfrozen resource profile')
            report['host_resources']=load_profile(a.resource_profile,a.output)
            report['resource_profile_sha256']=sha(a.resource_profile)
            os.environ[ENV]=json.dumps(report['host_resources']['cpus'])
        elif os.environ.get(ENV):raise ValueError('undeclared host CPU plan')
        profile=json.loads((root/'profiles/perception-source-compare-server-v2.json').read_text())
        expected=endurance_runtime(a.freeze,a.endurance_build,a.source,a.engine,profile) if a.endurance_seconds else original_owner_runtime(a.freeze,a.source,a.engine,profile)
        for path,digest in expected.items():
            if sha(a.source/path)!=digest:raise ValueError('original runtime identity '+path)
        for path in ('/d','/tmp',str(a.output.resolve())):
            v=os.statvfs(path);free=v.f_bavail*v.f_frsize;report.setdefault('free_bytes',{})[path]=free
            budget=(bounds['stored_bytes']+4*1024**3) if a.endurance_seconds and path!='/tmp' else 4*1024**3
            if free<budget:raise ValueError('insufficient paired evidence space: '+path)
        guards=[]
        try:
            for port in (2200,2201,2202,2300,2301,2302):
                s=socket.socket();guards.append(s);s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
                s.bind(('127.0.0.1',port));s.listen(1)
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
        cuda_library=getattr(a,'cuda_resize_library',None)
        if cuda_library:
            path=cuda_library.resolve();digest=sha(path)
            if json.loads(a.freeze.read_text())['external'].get(str(path))!=digest:
                raise ValueError('CUDA resize library must be frozen before execution')
            common.update(STRATADRIVE_M10_CUDA_RESIZE_LIBRARY=str(path),STRATADRIVE_M10_CUDA_RESIZE_SHA256=digest)
            report['cuda_resize']=dict(library=str(path),sha256=digest)
        elif any(key in common for key in ('STRATADRIVE_M10_CUDA_RESIZE_LIBRARY','STRATADRIVE_M10_CUDA_RESIZE_SHA256')):
            raise ValueError('undeclared CUDA resize environment')
        indices=getattr(a,'quality_views',None)
        fitted=getattr(a,'fitted_views',False)
        if fitted and indices is None:
            raise ValueError('fitted verifier requires explicit view schedule')
        if 'STRATADRIVE_M10_QUALITY_VIEWS' in common or 'STRATADRIVE_M10_FITTED_VIEWS' in common:
            raise ValueError('undeclared renderer view schedule environment')
        if indices is not None and not getattr(a,'quality_shadow',False):
            raise ValueError('renderer views require quality shadow')
        if getattr(a,'quality_shadow',False):
            candidate=json.loads(a.freeze.read_text())['candidate']
            if candidate.get('view_indices')!=indices or ('view_verifier_sha256' in candidate)!=fitted:
                raise ValueError('renderer view schedule must match the frozen candidate')
        if fitted:
            common['STRATADRIVE_M10_FITTED_VIEWS']='1'
            report['fitted_views']=True
        if indices is not None:
            common['STRATADRIVE_M10_QUALITY_VIEWS']=json.dumps(indices)
            report['quality_views']=indices
        if getattr(a,'quality_shadow',False):
            if a.endurance_seconds!=30 or a.condition!='normal' or not a.raw_recording:
                raise ValueError('quality shadow requires the recorded 30s normal case')
            common['STRATADRIVE_M10_QUALITY_SHADOW']='1'
            report['quality_shadow']=True
        elif 'STRATADRIVE_M10_QUALITY_SHADOW' in common:
            raise ValueError('undeclared quality shadow')
        camera_period=getattr(a,'camera_period_ms',50)
        camera_pacing(a.renderer_wall_hz,camera_period,getattr(a,'raw_recording',False))
        if (getattr(a,'raw_recording',False) or camera_period!=50) and not a.endurance_seconds:
            raise ValueError('explicit endurance recording/pacing')
        if camera_period!=50:
            common['STRATADRIVE_M10_CAMERA_PERIOD_MS']=str(camera_period)
        elif common.get('STRATADRIVE_M10_CAMERA_PERIOD_MS'):raise ValueError('undeclared camera cadence')
        report['camera_period_ms']=camera_period
        for option,key in [('profile_host','STRATADRIVE_M10_PROFILE'),('cuda_blocking','STRATADRIVE_CUDA_BLOCKING_SYNC'),('raw_recording','STRATADRIVE_M10_RAW_RECORDING'),
                           ('preprocess_cv_threads','STRATADRIVE_M10_CV_THREADS'),('resize_threads','STRATADRIVE_M10_RESIZE_THREADS'),
                           ('tensor_workspace','STRATADRIVE_M10_TENSOR_WORKSPACE'),
                           ('release_recording_cache','STRATADRIVE_M10_RELEASE_RECORDING_CACHE'),
                           ('prefetch_inference_libraries','STRATADRIVE_M10_PREFETCH_LIBRARIES')]:
            value=getattr(a,option,0)
            if value:
                if not a.endurance_seconds:raise ValueError('explicit endurance host profiling option')
                common[key]=str(int(value));report[option]=value
            elif common.get(key):raise ValueError('undeclared profiling option '+key)
        if getattr(a,'passive_ort',False):
            if not a.endurance_seconds:raise ValueError('explicit endurance passive ORT')
            common['STRATADRIVE_ORT_PASSIVE_THREADS']='1';report['ort_passive_threads']=True
        elif common.get('STRATADRIVE_ORT_PASSIVE_THREADS'):raise ValueError('undeclared ORT thread policy')
        if getattr(a,'renderer_wall_hz',0):
            if not a.endurance_seconds:raise ValueError('explicit endurance renderer pacing')
            common['STRATADRIVE_RENDERER_WALL_HZ']=str(a.renderer_wall_hz)
            report['renderer_wall_hz']=a.renderer_wall_hz
        elif common.get('STRATADRIVE_RENDERER_WALL_HZ'):raise ValueError('undeclared renderer pacing')
        if common.get('LD_PRELOAD'):raise ValueError('unexpected preload')
        owner_env=dict(common,STRATADRIVE_M7_OWNER_KEY=secrets.token_hex(32))
        commands=dict(renderer=base+['-carla-rpc-port=2300'],owner=base+['-carla-rpc-port=2200',
            '-StrataM7NativeProbe','-StrataM7V1Substeps320','-StrataM7SolverWork','-StrataM7CompactWork',
            '-StrataM7WallNative','-StrataM7HeldSteerSleep','-StrataM7Wall5ms','-nullrhi','-norenderthread'])
        if a.endurance_seconds:commands['owner'].append('-StrataM10EnduranceFrames='+str(bounds['frames']))
        if getattr(a,'renderer_max_fps',0):
            if not a.endurance_seconds:raise ValueError('explicit renderer preparation cap')
            commands['renderer']=[x+f',t.MaxFPS {a.renderer_max_fps}' if x.startswith('-ExecCmds=') else x for x in commands['renderer']]
        if getattr(a,'idle_wait',False):
            if not a.endurance_seconds:raise ValueError('explicit endurance idle wait')
            for argv in commands.values():argv.append('-StrataM10IdleWait')
        report['argv']=commands
        if getattr(a,'profile_state_path',False):
            if not a.endurance_seconds:raise ValueError('explicit endurance state path profiling')
            commands['owner'].append('-StrataM10StatePathProfile')
            report['profile_state_path']=True
        if getattr(a,'profile_owner_gc',False):
            if not a.endurance_seconds or not a.profile_state_path:
                raise ValueError('owner GC profiling requires endurance state path')
            commands['owner'].append('-StrataM10GcProfile')
            report['profile_owner_gc']=True
        if getattr(a,'owner_serial_gc',False):
            if not a.profile_owner_gc:raise ValueError('serial GC requires explicit GC profiling')
            commands['owner']=[x+',gc.AllowParallelGC 0' if x.startswith('-ExecCmds=') else x for x in commands['owner']]
            report['owner_serial_gc']=True
        if getattr(a,'owner_purge_slice',False):
            if not a.profile_owner_gc or not a.structured_state or a.owner_serial_gc:
                raise ValueError('purge slice requires profiled parallel GC and structured state')
            commands['owner'].append('-StrataM10PurgeSlice')
            report['owner_purge_slice']=True
        if getattr(a,'owner_recovery_preview',False):
            if not a.owner_purge_slice:
                raise ValueError('recovery preview requires explicit incremental purge candidate')
            commands['owner'].append('-StrataM10RecoveryPreview')
            report['owner_recovery_preview']=True
        if getattr(a,'owner_no_visual_tags',False):
            if not a.owner_recovery_preview:
                raise ValueError('visual tag omission requires the explicit profiled recovery candidate')
            commands['owner'].append('-StrataM10NoVisualTags')
            report['owner_no_visual_tags']=True
        if getattr(a,'structured_state',False):
            if not a.endurance_seconds:raise ValueError('explicit endurance structured state')
            commands['owner'].append('-StrataM10StructuredState')
            report['structured_state']=True
        if getattr(a,'packaged_renderer',None):
            if not a.endurance_seconds or a.renderer_max_fps or not a.park_preparation or a.condition!='normal':
                raise ValueError('packaged renderer requires declared endurance, parking and no editor FPS claim')
            from packaged_renderer_v1 import command as stock_command
            commands['renderer'],report['packaged_renderer']=stock_command(
                commands['renderer'],a.packaged_renderer,json.loads(a.freeze.read_text()))
            if getattr(a,'packaged_target_map',False):
                config=a.packaged_renderer.resolve().parents[2]/'Config/DefaultEngine.ini'
                frozen=json.loads(a.freeze.read_text())
                if frozen['external'].get(str(config))!=sha(config):raise ValueError('frozen stock default map config')
                report['packaged_target_map']=dict(config=str(config),sha256=sha(config))
            stock_ini=a.packaged_renderer.resolve().parents[2]/'Saved/Config/Linux/GameUserSettings.ini'
            stock_original=stock_ini.read_bytes() if stock_ini.exists() else None
            report['packaged_renderer']['original_ini_sha256']=hashlib.sha256(stock_original).hexdigest() if stock_original is not None else None
        if getattr(a,'park_preparation',False) and not a.endurance_seconds:raise ValueError('explicit preparation parking')
        def ready_and_park(role,port):
            report.setdefault('readiness',{})[str(port)]=wait_ready(a.python,port,a.output/f'readiness-{port}.log',common)
            if role=='renderer' and getattr(a,'packaged_renderer',None):
                from packaged_renderer_v1 import prepare
                ready=prepare(a.python,report['process_started_ns'][role],common)
                if getattr(a,'packaged_target_map',False) and ready['initial_map']!='Carla/Maps/Town03_Opt':
                    raise ValueError('stock renderer must start in Town03 without a second map load')
                report['packaged_renderer']['preparation']=ready
                report.setdefault('parked',{})[role]=dict(world=ready['world'],synchronous=True,wall_ns=ready['completed_ns'])
                return
            if getattr(a,'park_preparation',False):
                # No native bind/session or camera exists. Park the empty world
                # before launching the next server; clients later configure and
                # explicitly tick their own worlds using unchanged model steps.
                script=("import carla,json;c=carla.Client('127.0.0.1',"+str(port)+");c.set_timeout(10);w=c.get_world();s=w.get_settings();s.synchronous_mode=True;w.apply_settings(s);print(json.dumps(dict(world=w.id,synchronous=w.get_settings().synchronous_mode)))")
                state=json.loads(subprocess.check_output([str(a.python),'-c',script],env=common,text=True,timeout=15))
                if not state['synchronous']:raise ValueError('preparation world not parked')
                report.setdefault('parked',{})[role]=dict(state,wall_ns=time.monotonic_ns())
        for role in ('renderer','owner'):
            log=(a.output/f'{role}.log').open('w');logs.append(log)
            launched=owner_command(report.get('host_resources',{}),commands[role]) if role=='owner' else commands[role]
            report.setdefault('process_started_ns',{})[role]=time.monotonic_ns()
            processes[role]=subprocess.Popen(placed_command(role,launched),env=owner_env if role=='owner' else common,
                stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=hook)
            if getattr(a,'park_preparation',False):ready_and_park(role,2300 if role=='renderer' else 2200)
        report['pids']={k:p.pid for k,p in processes.items()}
        if not getattr(a,'park_preparation',False):
            for port in (2200,2300):ready_and_park('owner' if port==2200 else 'renderer',port)
        command=[str(a.python),str(Path(__file__).with_name('carla_control_shadow_v1.py')),
            '--output',str(a.output/'capture'),'--native',str(a.native),'--model',str(root/'tools/carla/m7_nodrive/virtual_ev_v1.json'),
            '--scenario',str(root/('tests/integration/carla/scenarios/m10_endurance_hold_v1.txt' if a.endurance_seconds else 'tests/integration/carla/scenarios/m7_integrated_v1.txt')),
            '--ticks',str(bounds['frames']),'--warmup-ticks','150','--step-ms','5','--execution-profile','owner5ms','--camera-absent-control',
            '--wall-clock',str(secrets.randbits(63) or 1),'--detector',str(a.detector),'--models',str(a.models),
            '--library',str(a.library),'--paired-renderer-port','2300','--paired-renderer-pid',str(processes['renderer'].pid),
            '--paired-condition',a.condition,'--paired-export-hz',str(a.export_hz),'--endurance-seconds',str(a.endurance_seconds)]
        command+=['--wall-profile',wall_profile,'--hv-dependency-ms',str(WALL_PROFILES[wall_profile])]
        report['wall_profile']=wall_profile
        check_owner(report.get('host_resources',{}),processes['owner'].pid)
        if getattr(a,'profile_state_path',False):command.append('--profile-state-path')
        if getattr(a,'native_service_us',1000)!=1000:
            if not a.endurance_seconds or not a.profile_state_path:raise ValueError('profiled endurance native service cadence')
            command+=['--native-service-us',str(a.native_service_us)]
            report['native_service_us']=a.native_service_us
        if getattr(a,'profile_owner_gc',False):command.append('--profile-owner-gc')
        if getattr(a,'structured_state',False):command.append('--structured-state')
        if getattr(a,'packaged_renderer',None):
            command+=['--paired-renderer-executable',str(a.packaged_renderer.resolve())]
        if getattr(a,'prefetch_owner_code',False):
            if not a.endurance_seconds or not a.park_preparation:
                raise ValueError('owner code preparation requires parked endurance')
            command+=['--prefetch-owner-pid',str(processes['owner'].pid)]
            report['prefetch_owner_code']=True
        report['client_argv']=command
        log=(a.output/'client.log').open('w');logs.append(log)
        client=subprocess.Popen(placed_command('observer',command),env=owner_env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        deadline=time.monotonic()+900+a.endurance_seconds*3;diagnosed=False;first_interrupt=None;last_resource=0
        while client.poll() is None or (first_interrupt and processes['renderer'].poll() is None):
            now=time.monotonic_ns();renderer=processes['renderer']
            if a.endurance_seconds and now-last_resource>=1_000_000_000:
                sample=resources({**report['pids'],'client':client.pid});report['resources'].append(sample);last_resource=now
                disk=os.statvfs(a.output);sample['spool_free_bytes']=disk.f_bavail*disk.f_frsize
                if sample['available_ram_bytes']<2*1024**3 or min(sample['free_bytes']['/d'],sample['spool_free_bytes'])<2*1024**3:
                    raise RuntimeError('declared resource reserve reached')
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
        report['client_completed_ns']=time.monotonic_ns()
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
                elif role=='renderer' and getattr(a,'packaged_renderer',None):
                    from packaged_renderer_v1 import stop
                    result=stop(process,a.python,common)
                    if result.get('unpark_error'):report['status']='FAIL'
                else:result=shutdown(process,a.output/role,diagnostics=True)
                report.setdefault('shutdown',{})[role]=result
                expected_exit=-9 if role=='renderer' and a.condition=='stall-crash' and first_crash else 130
                if result['server_exit']!=expected_exit or result.get('forced_stop'):report['status']='FAIL'
        if report.get('renderer_injected_forced_stop') or report.get('client_forced_stop'):report['status']='FAIL'
        ini.write_bytes(original);report['restored_ini_sha256']=sha(ini)
        if stock_ini is not None:
            if stock_original is None:stock_ini.unlink(missing_ok=True)
            else:stock_ini.write_bytes(stock_original)
            after=stock_ini.read_bytes() if stock_ini.exists() else None
            report['packaged_renderer']['restored_ini_sha256']=hashlib.sha256(after).hexdigest() if after is not None else None
            if after!=stock_original:report['status']='FAIL'
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
    p.add_argument('--endurance-seconds',type=int,choices=(0,30,300),default=0)
    p.add_argument('--endurance-build',type=Path)
    p.add_argument('--resource-profile',type=Path)
    p.add_argument('--packaged-renderer',type=Path)
    p.add_argument('--prefetch-owner-code',action='store_true')
    p.add_argument('--idle-wait',action='store_true')
    p.add_argument('--passive-ort',action='store_true')
    p.add_argument('--renderer-wall-hz',type=int,choices=(0,10,20),default=0)
    p.add_argument('--camera-period-ms',type=int,choices=(50,100),default=50)
    p.add_argument('--profile-host',action='store_true')
    p.add_argument('--profile-state-path',action='store_true')
    p.add_argument('--structured-state',action='store_true')
    p.add_argument('--park-preparation',action='store_true')
    p.add_argument('--cuda-blocking',action='store_true')
    p.add_argument('--raw-recording',action='store_true')
    p.add_argument('--release-recording-cache',action='store_true')
    p.add_argument('--wall-profile',choices=tuple(WALL_PROFILES),default='wall5-hv30-v1')
    p.add_argument('--packaged-target-map',action='store_true')
    p.add_argument('--native-service-us',type=int,choices=(500,1000),default=1000)
    p.add_argument('--cuda-resize-library',type=Path)
    p.add_argument('--quality-shadow',action='store_true')
    p.add_argument('--quality-views',nargs='+',type=int)
    p.add_argument('--fitted-views',action='store_true')
    p.add_argument('--tensor-workspace',action='store_true')
    p.add_argument('--profile-owner-gc',action='store_true')
    p.add_argument('--owner-no-visual-tags',action='store_true')
    p.add_argument('--owner-serial-gc',action='store_true')
    p.add_argument('--owner-purge-slice',action='store_true')
    p.add_argument('--owner-recovery-preview',action='store_true')
    p.add_argument('--prefetch-inference-libraries',action='store_true')
    p.add_argument('--renderer-max-fps',type=int,choices=(0,20,60),default=0)
    p.add_argument('--preprocess-cv-threads',type=int,choices=(0,1,2,4),default=0)
    p.add_argument('--resize-threads',type=int,choices=(0,1,2,4),default=0)
    raise SystemExit(main(p.parse_args()))

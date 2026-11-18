#!/usr/bin/env python3
"""Prepare the declared empty owner and renderer before the host lease."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import secrets
import signal
import socket
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests/integration/perception'))
from carla_readiness_v1 import PROBE
from packaged_renderer_v1 import prepare as stock_prepare,stop as stock_stop
from renderer_shutdown_v1 import shutdown,allow_shutdown_tracer
from run_carla_control_shadow_v1 import sha


def main(series):
    sys.path.insert(0,str(series))
    from runtime_restore import restore
    name='launch-'+str(time.monotonic_ns());work=ROOT/'build'/series.name.replace('_','-')/'preparations'/name
    bundle=series/'preparations'/name
    work.mkdir(parents=True);bundle.mkdir(parents=True)
    config=json.loads((series/'preparation-argv.json').read_text())
    renderer_kind=config.get('renderer_kind','packaged')
    if renderer_kind not in ('packaged','editor'):raise ValueError('declared renderer kind')
    python=ROOT/'build/m10-perception/cuda-venv/bin/python'
    source=Path('/d/shin/stratadrive-tools/m7-source/carla-0.9.16')
    ini=source/'Unreal/CarlaUE4/Saved/Config/Linux/GameUserSettings.ini'
    stock_ini=(Path(config['renderer'][0]).parents[2]/'Saved/Config/Linux/GameUserSettings.ini'
               if renderer_kind=='packaged' else ini)
    originals={p:p.read_bytes() if p.exists() else None for p in (ini,stock_ini)}
    policy={n:Path('/sys/devices/system/cpu/intel_pstate',n).read_text().strip() for n in ('min_perf_pct','max_perf_pct','no_turbo')}
    assert policy==dict(min_perf_pct='16',max_perf_pct='100',no_turbo='0')
    assert not any(n.startswith(('UE4Editor','CarlaUE4-Linux')) for n in subprocess.check_output(['ps','-eo','comm='],text=True).splitlines())
    guards=[]
    try:
        for port in (2200,2201,2202,2300,2301,2302):
            s=socket.socket();guards.append(s);s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('127.0.0.1',port));s.listen(1)
    finally:
        for s in guards:s.close()
    report=dict(status='FAIL',validation_only=False,host_policy=policy,stages={},
        scope='empty processes at100%; no native START, camera, detector or forced GC',script_sha256=sha(Path(__file__)))
    stopped=[]
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stopped.append(True))
    env=dict(os.environ,OMP_WAIT_POLICY='PASSIVE',STRATADRIVE_M7_OWNER_KEY=secrets.token_hex(32))
    def hook():resource.setrlimit(resource.RLIMIT_CORE,(0,0));allow_shutdown_tracer()
    def call(argv,name):
        with (work/name).open('x') as out:subprocess.run(list(map(str,argv)),stdout=out,stderr=subprocess.STDOUT,check=True)
    try:
        restore(ROOT,series,work,bundle/'pre-restoration.json')
        engine='/d/shin/stratadrive-tools/UnrealEngine_4.26'
        call(['python3',ROOT/'tools/carla/m7_nodrive/build_endurance.py','--engine',engine,'--source',source,
            '--output',ROOT/'build/m10-gc-feedback-v1/visual-tags-build-01','--install'],'install-module.log')
        call(['python3',ROOT/'tools/carla/m7_nodrive/build_dxc_lifetime.py','--engine',engine,
            '--output',ROOT/'build/m10-dxc-lifetime-v1','--install'],'install-dxc.log')
        for role,port,cpus,budget in (('owner',2200,'2-5,10-13',600),('renderer',2300,'6-7,14-15',180 if renderer_kind=='packaged' else 600)):
            stage=dict(argv=config[role],startup_budget_seconds=budget);report['stages'][role]=stage
            process=None
            try:
                print('PREPARE '+role,flush=True)
                with (work/(role+'.log')).open('x') as log,(work/(role+'-readiness.jsonl')).open('x') as history:
                    start=time.monotonic_ns();deadline=time.monotonic()+budget
                    process=subprocess.Popen(['taskset','-c',cpus,*config[role]],env=env,
                        stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=hook)
                    while time.monotonic()<deadline:
                        if stopped:raise InterruptedError('preparation cancelled')
                        if process.poll() is not None:raise RuntimeError('empty server exited before readiness')
                        row=dict(begin_ns=time.monotonic_ns())
                        try:
                            probe=subprocess.run([str(python),'-c',PROBE,str(port)],env=env,capture_output=True,text=True,
                                timeout=min(5,max(.001,deadline-time.monotonic())))
                            row.update(exit=probe.returncode,stdout=probe.stdout,stderr=probe.stderr)
                        except subprocess.TimeoutExpired:row['timeout']=True
                        row['end_ns']=time.monotonic_ns();history.write(json.dumps(row)+'\n');history.flush()
                        if row.get('exit')==0:break
                        time.sleep(.1)
                    else:raise TimeoutError('declared empty preparation budget exhausted')
                    stage['ready_seconds']=(time.monotonic_ns()-start)/1e9
                    if role=='renderer' and renderer_kind=='packaged':
                        stage['prepared']=stock_prepare(python,start,env)
                        if (series/'map-config.json').exists():
                            assert stage['prepared']['initial_map']=='Carla/Maps/Town03_Opt','initial target map, no implicit second load'
                    else:
                        script=f"import carla,json;c=carla.Client('127.0.0.1',{port});c.set_timeout(5);w=c.get_world();counts={{k:len(w.get_actors().filter(k)) for k in ('vehicle.*','walker.*','sensor.*')}};assert not any(counts.values());s=w.get_settings();s.synchronous_mode=True;w.apply_settings(s);print(json.dumps(dict(world=w.id,map=w.get_map().name,counts=counts,parked=w.get_settings().synchronous_mode)))"
                        stage['prepared']=json.loads(subprocess.check_output([str(python),'-c',script],env=env,text=True,timeout=10))
            finally:
                if process:
                    stage['shutdown']=stock_stop(process,python,env) if role=='renderer' and renderer_kind=='packaged' else shutdown(process,work/(role+'-stop'),diagnostics=True)
            exit=stage['shutdown']
            if exit['server_exit']!=130 or exit.get('forced_stop') or exit.get('unpark_error'):
                raise RuntimeError('empty preparation normal shutdown required')
        report['status']='PREPARED_NOT_PHYSICAL_ACCEPTANCE'
    except Exception as error:report['error']=repr(error)
    finally:
        for path,data in originals.items():
            if data is None:path.unlink(missing_ok=True)
            else:path.write_bytes(data)
        report['restoration']=restore(ROOT,series,work,bundle/'restoration.json',raise_on_failure=False)
        report['stock_ini_restored']=(stock_ini.read_bytes() if stock_ini.exists() else None)==originals[stock_ini]
        if report['restoration']['status']!='PASS' or not report['stock_ini_restored']:report['status']='FAIL'
        report['completed_wall_ns']=time.monotonic_ns()
        report['files']={str(p.relative_to(work)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in work.rglob('*') if p.is_file()}
        (bundle/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        (series/'asset-preparation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],error=report.get('error'))),flush=True)
    if report['status']!='PREPARED_NOT_PHYSICAL_ACCEPTANCE':raise SystemExit(1)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--series',type=Path,required=True);main(p.parse_args().series.resolve())

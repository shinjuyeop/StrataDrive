"""Prepare an empty renderer immediately before authentication; no control trial."""
from datetime import datetime, timezone
import argparse
import json
import os
from pathlib import Path
import resource
import signal
import socket
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[4]; SERIES=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tests/integration/perception'))
from carla_readiness_v1 import PROBE
from renderer_shutdown_v1 import shutdown,allow_shutdown_tracer
from run_carla_control_shadow_v1 import sha
from runtime_restore import restore

p=argparse.ArgumentParser();p.add_argument('--validation',action='store_true');a=p.parse_args()
name=('validation-' if a.validation else 'launch-')+str(time.monotonic_ns())
work=ROOT/'build/m10-parallel-gc-v1/preparations'/name;work.mkdir(parents=True,exist_ok=False)
bundle=SERIES/'preparations'/name;bundle.mkdir(parents=True,exist_ok=False)
engine=Path('/d/shin/stratadrive-tools/UnrealEngine_4.26')
carla=Path('/d/shin/stratadrive-tools/m7-source/carla-0.9.16')
py=ROOT/'build/m10-perception/cuda-venv/bin/python'
ini=carla/'Unreal/CarlaUE4/Saved/Config/Linux/GameUserSettings.ini'
original=ini.read_bytes();argv=['taskset','-c','4-7,12-15',*json.loads((SERIES/'renderer-argv.json').read_text())]
report=dict(status='FAIL',scope='empty renderer cache preparation only; no native, camera, inference or GC intervention',
    validation_only=a.validation,declared_utc=datetime.now(timezone.utc).isoformat(),readiness_limit_seconds=600,
    argv=argv,script_sha256=sha(Path(__file__)),module_sha256=json.loads((ROOT/'build/m10-admission-window-v1/server-build-01/manifest.json').read_text())['module_sha256'],
    physical_trial_startup_limit_unchanged_seconds=180,work=str(work.relative_to(ROOT)))
policy={n:Path('/sys/devices/system/cpu/intel_pstate',n).read_text().strip() for n in ('min_perf_pct','max_perf_pct','no_turbo')}
assert policy==dict(min_perf_pct='16',max_perf_pct='100',no_turbo='0'),'preparation outside host lease'
report['host_policy']=policy
assert not any(n.strip()=='UE4Editor' for n in subprocess.check_output(['ps','-eo','comm='],text=True).splitlines())
guards=[]
try:
    for port in (2300,2301,2302):
        guard=socket.socket();guards.append(guard);guard.bind(('127.0.0.1',port))
finally:
    for guard in guards:guard.close()
restore(ROOT,SERIES,work,bundle/'pre-restoration.json')
process=None;stopped=[]
for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda *_:stopped.append(True))
def call(argv,name):
    with (work/name).open('w') as out:subprocess.run(list(map(str,argv)),stdout=out,stderr=subprocess.STDOUT,check=True)
def hook():resource.setrlimit(resource.RLIMIT_CORE,(0,0));allow_shutdown_tracer()
env=dict(os.environ,OMP_WAIT_POLICY='PASSIVE');env.pop('STRATADRIVE_M7_OWNER_KEY',None)
try:
    call(['python3',ROOT/'tools/carla/m7_nodrive/build_endurance.py','--engine',engine,'--source',carla,
        '--output',ROOT/'build/m10-admission-window-v1/server-build-01','--install'],'install-module.log')
    call(['python3',ROOT/'tools/carla/m7_nodrive/build_dxc_lifetime.py','--engine',engine,
        '--output',ROOT/'build/m10-dxc-lifetime-v1','--install'],'install-dxc.log')
    (bundle/'declared.json').write_text(json.dumps(report,indent=2)+'\n')
    print('빈 영상 서버의 자산을 준비합니다. 제한 600초; 제어 시험은 아직 시작하지 않습니다.',flush=True)
    with (work/'renderer.log').open('w') as log,(work/'readiness.jsonl').open('w') as history:
        process=subprocess.Popen(argv,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=hook)
        begin=time.monotonic();deadline=begin+600
        while time.monotonic()<deadline:
            if stopped:raise InterruptedError('preparation cancelled')
            if process.poll() is not None:raise RuntimeError('renderer exited before preparation readiness')
            item=dict(begin_ns=time.monotonic_ns())
            try:
                probe=subprocess.run([str(py),'-c',PROBE,'2300'],env=env,capture_output=True,text=True,
                    timeout=min(5,max(.01,deadline-time.monotonic())))
                item.update(exit=probe.returncode,stdout=probe.stdout,stderr=probe.stderr)
            except subprocess.TimeoutExpired:item['timeout']=True
            item['end_ns']=time.monotonic_ns();history.write(json.dumps(item)+'\n');history.flush()
            if item.get('exit')==0:break
            time.sleep(min(.1,max(0,deadline-time.monotonic())))
        else:raise TimeoutError('separate 600s preparation horizon exhausted')
        report['ready_after_seconds']=time.monotonic()-begin
        script="import carla,json;c=carla.Client('127.0.0.1',2300);c.set_timeout(10);w=c.get_world();a=w.get_actors();counts={k:len(a.filter(k)) for k in ('vehicle.*','sensor.*','walker.*')};assert not any(counts.values());s=w.get_settings();s.synchronous_mode=True;w.apply_settings(s);print(json.dumps(dict(counts=counts,parked=w.get_settings().synchronous_mode)))"
        report['empty_world']=json.loads(subprocess.check_output([str(py),'-c',script],env=env,text=True,timeout=15))
        report['status']='PREPARED_NOT_PHYSICAL_ACCEPTANCE'
except Exception as error:report['error']=repr(error)
finally:
    if process is not None:
        report['shutdown']=shutdown(process,work/'shutdown',diagnostics=True)
        if report['shutdown']['server_exit']!=130 or report['shutdown'].get('forced_stop'):report['status']='FAIL'
    ini.write_bytes(original)
    report['restoration']=restore(ROOT,SERIES,work,bundle/'restoration.json',raise_on_failure=False)
    if report['restoration']['status']!='PASS':report['status']='FAIL'
    report['completed_wall_ns']=time.monotonic_ns()
    report['files']={str(path.relative_to(work)):dict(bytes=path.stat().st_size,sha256=sha(path)) for path in work.rglob('*') if path.is_file()}
    (bundle/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    if not a.validation:
        # The latest preparation is an index only; each immutable attempt stays above.
        (SERIES/'asset-preparation.json').write_text(json.dumps(dict(report,attempt=name),indent=2)+'\n')
print(json.dumps(dict(status=report['status'],ready_after_seconds=report.get('ready_after_seconds'),record=str(bundle/'result.json'))),flush=True)
raise SystemExit(0 if report['status']=='PREPARED_NOT_PHYSICAL_ACCEPTANCE' else 1)

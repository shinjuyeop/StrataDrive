"""One empty-renderer cache preparation, separate from physical acceptance."""
from datetime import datetime,timezone
import hashlib,json,os,resource,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];SERIES=Path(__file__).resolve().parent
WORK=ROOT/'build/m10-state-path-v2/preparation';WORK.mkdir(parents=True,exist_ok=False)
sys.path.insert(0,str(ROOT/'tests/integration/perception'))
from carla_readiness_v1 import PROBE
from renderer_shutdown_v1 import shutdown,allow_shutdown_tracer
from run_carla_control_shadow_v1 import sha

engine=Path('/d/shin/stratadrive-tools/UnrealEngine_4.26')
source=Path('/d/shin/stratadrive-tools/m7-source/carla-0.9.16')
py=ROOT/'build/m10-perception/cuda-venv/bin/python'
old=json.loads((ROOT/'build/m10-state-path-v1/normal-30s-01/archive-check/run/server.json').read_text())
argv=['taskset','-c','4-7,12-15',*old['argv']['renderer']]
ini=source/'Unreal/CarlaUE4/Saved/Config/Linux/GameUserSettings.ini';original=ini.read_bytes()
report=dict(status='FAIL',scope='empty-renderer asset preparation only; no native, inference or camera',
    declared_utc=datetime.now(timezone.utc).isoformat(),readiness_limit_seconds=600,
    argv=argv,script_sha256=sha(Path(__file__)),protocol_sha256=sha(ROOT/'docs/test-plan/perception-state-path-v2-protocol.md'))
candidate=json.loads((ROOT/'build/m10-state-path-v1/server-build-01/manifest.json').read_text())
dxc=json.loads((ROOT/'build/m10-dxc-lifetime-v1/manifest.json').read_text())
assert sha(candidate['module_path'])==candidate['module_sha256']
assert sha(dxc['installed_path'])==dxc['candidate_sha256']
report['candidate_sha256']=candidate['module_sha256'];report['dxc_sha256']=dxc['candidate_sha256']
def hook():resource.setrlimit(resource.RLIMIT_CORE,(0,0));allow_shutdown_tracer()
env=dict(os.environ,OMP_WAIT_POLICY='PASSIVE');env.pop('STRATADRIVE_M7_OWNER_KEY',None)
process=None
try:
    (WORK/'declared.json').write_text(json.dumps(report,indent=2)+'\n')
    with (WORK/'renderer.log').open('w') as log,(WORK/'readiness.jsonl').open('w') as history:
        process=subprocess.Popen(argv,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=hook)
        begin=time.monotonic();deadline=begin+600
        while time.monotonic()<deadline:
            if process.poll() is not None:raise RuntimeError('preparation renderer exited before readiness')
            item=dict(begin_ns=time.monotonic_ns())
            try:
                p=subprocess.run([str(py),'-c',PROBE,'2300'],env=env,capture_output=True,text=True,timeout=min(5,max(.01,deadline-time.monotonic())))
                item.update(exit=p.returncode,stdout=p.stdout,stderr=p.stderr)
            except subprocess.TimeoutExpired:item['timeout']=True
            item['end_ns']=time.monotonic_ns();history.write(json.dumps(item)+'\n');history.flush()
            if item.get('exit')==0:break
            time.sleep(min(.1,max(0,deadline-time.monotonic())))
        else:raise TimeoutError('separate600s asset preparation limit')
        report['ready_after_seconds']=time.monotonic()-begin
        script="import carla,json;c=carla.Client('127.0.0.1',2300);c.set_timeout(10);w=c.get_world();a=w.get_actors();counts={k:len(a.filter(k)) for k in ('vehicle.*','sensor.*','walker.*')};assert not any(counts.values());s=w.get_settings();s.synchronous_mode=True;w.apply_settings(s);print(json.dumps(dict(counts=counts,parked=w.get_settings().synchronous_mode)))"
        report['empty_world']=json.loads(subprocess.check_output([str(py),'-c',script],env=env,text=True,timeout=15))
        report['status']='PREPARED_NOT_PHYSICAL_ACCEPTANCE'
except Exception as error:report['error']=repr(error)
finally:
    if process is not None:
        report['shutdown']=shutdown(process,WORK/'shutdown',diagnostics=True)
        if report['shutdown']['server_exit']!=130 or report['shutdown'].get('forced_stop'):report['status']='FAIL'
    ini.write_bytes(original);report['ini_sha256']=sha(ini)
    codes=[]
    for command in [
        ['python3',ROOT/'tools/carla/m7_nodrive/build_dxc_lifetime.py','--engine',engine,'--output',ROOT/'build/m10-dxc-lifetime-v1','--restore'],
        ['python3',ROOT/'tools/carla/m7_nodrive/build_endurance.py','--engine',engine,'--source',source,'--output',ROOT/'build/m10-state-path-v1/server-build-01','--restore']]:
        with (WORK/f'restore-{len(codes)}.log').open('w') as out:codes.append(subprocess.run(list(map(str,command)),stdout=out,stderr=subprocess.STDOUT).returncode)
    report['restore_exits']=codes
    originals=json.loads((SERIES/'pre-install.json').read_text())['files']
    report['original_hashes_restored']=all(sha(item['path'])==item['sha256'] for item in originals.values())
    if codes!=[0,0] or not report['original_hashes_restored']:report['status']='FAIL'
    (SERIES/'asset-preparation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report));raise SystemExit(0 if report['status']=='PREPARED_NOT_PHYSICAL_ACCEPTANCE' else 1)

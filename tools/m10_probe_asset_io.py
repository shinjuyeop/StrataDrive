#!/usr/bin/env python3
"""Record actual source-owner file opens; isolated preparation, no native START."""
import argparse
import json
import os
from pathlib import Path
import resource
import secrets
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests/integration/perception'))
from carla_readiness_v1 import PROBE
from renderer_shutdown_v1 import shutdown,allow_shutdown_tracer
from run_carla_control_shadow_v1 import sha


def main(out):
    import carla
    out.mkdir(parents=True,exist_ok=False)
    series=ROOT/'docs/test-plan/evidence/m10_packaged_renderer_v1'
    sys.path.insert(0,str(series));from runtime_restore import restore
    argv=json.loads((series/'preparation-argv.json').read_text())['owner']+['-FileOpenLog']
    project=Path(argv[1]).parent;engine=Path(argv[0]).parents[3]
    ini=project/'Saved/Config/Linux/GameUserSettings.ini'
    order=project/'Build/LinuxNoEditor/FileOpenOrder/EditorOpenOrder.log'
    # FPlatformProperties::PlatformName() is Linux in this editor build. Preserve
    # both potential existing destinations; only one may be produced.
    orders=[order,project/'Build/Linux/FileOpenOrder/EditorOpenOrder.log']
    originals={p:p.read_bytes() if p.exists() else None for p in [ini,*orders]}
    assert Path('/sys/devices/system/cpu/intel_pstate/max_perf_pct').read_text().strip()=='100'
    assert not any(n.startswith(('UE4Editor','CarlaUE4-Linux')) for n in subprocess.check_output(['ps','-eo','comm='],text=True).splitlines())
    report=dict(status='FAIL',argv=argv,startup_limit_seconds=600,native_started=False,images=0,
        host_max_perf_pct=100,script_sha256=sha(Path(__file__)),scope=__doc__)
    (out/'source.py').write_bytes(Path(__file__).read_bytes())
    stopped=[];process=None
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stopped.append(True))
    def hook():resource.setrlimit(resource.RLIMIT_CORE,(0,0));allow_shutdown_tracer()
    def call(argv,name):
        with (out/name).open('x') as log:subprocess.run(list(map(str,argv)),stdout=log,stderr=subprocess.STDOUT,check=True)
    try:
        restore(ROOT,series,out,out/'pre-restoration.json')
        call(['python3',ROOT/'tools/carla/m7_nodrive/build_endurance.py','--engine',engine,
            '--source',project.parents[1],'--output',ROOT/'build/m10-gc-feedback-v1/visual-tags-build-01','--install'],'install.log')
        env=dict(os.environ,OMP_WAIT_POLICY='PASSIVE',STRATADRIVE_M7_OWNER_KEY=secrets.token_hex(32))
        with (out/'owner.log').open('x') as log,(out/'readiness.jsonl').open('x') as history:
            start=time.monotonic_ns();deadline=time.monotonic()+600
            process=subprocess.Popen(['taskset','-c','2-5,10-13',*argv],env=env,stdout=log,
                stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=hook)
            while time.monotonic()<deadline:
                if stopped or process.poll() is not None:raise RuntimeError('file-open preparation stopped')
                row=dict(begin_ns=time.monotonic_ns())
                try:
                    probe=subprocess.run([sys.executable,'-c',PROBE,'2200'],capture_output=True,text=True,env=env,
                        timeout=min(5,max(.001,deadline-time.monotonic())))
                    row.update(exit=probe.returncode,stdout=probe.stdout,stderr=probe.stderr)
                except subprocess.TimeoutExpired:row['timeout']=True
                row['end_ns']=time.monotonic_ns();history.write(json.dumps(row)+'\n');history.flush()
                if row.get('exit')==0:break
                time.sleep(.1)
            else:raise TimeoutError('600s asset inventory preparation')
            report['ready_seconds']=(time.monotonic_ns()-start)/1e9
            c=carla.Client('127.0.0.1',2200);c.set_timeout(10);w=c.get_world()
            assert w.get_map().name=='Carla/Maps/Town03_Opt'
            s=w.get_settings();s.synchronous_mode=True;w.apply_settings(s)
            report['map']=w.get_map().name;report['world']=w.id
            report['empty']={k:len(w.get_actors().filter(k)) for k in ('vehicle.*','walker.*','sensor.*')}
            assert not any(report['empty'].values())
            report['status']='EMPTY_OWNER_FILE_INVENTORY_ONLY'
    except Exception as error:report['error']=repr(error)
    finally:
        if process:
            report['shutdown']=shutdown(process,out/'shutdown',diagnostics=True)
            if report['shutdown']['server_exit']!=130 or report['shutdown'].get('forced_stop'):report['status']='FAIL'
        produced=[]
        for i,path in enumerate(orders):
            if path.exists() and path.read_bytes()!=originals[path]:
                retained=out/f'open-order-{i}.log';retained.write_bytes(path.read_bytes())
                produced.append(dict(path=str(path),retained=retained.name,sha256=sha(retained)))
        report['open_order_logs']=produced
        if report['status']=='EMPTY_OWNER_FILE_INVENTORY_ONLY' and not produced:report['status']='FAIL'
        for path,data in originals.items():
            if data is None:path.unlink(missing_ok=True)
            else:path.write_bytes(data)
        report['restoration']=restore(ROOT,series,out,out/'restoration.json',raise_on_failure=False)
        if report['restoration']['status']!='PASS':report['status']='FAIL'
        report['original_logs_restored']=all((p.read_bytes() if p.exists() else None)==v for p,v in originals.items())
        (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
    return 0 if report['status']=='EMPTY_OWNER_FILE_INVENTORY_ONLY' else 1


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    raise SystemExit(main(p.parse_args().output.resolve()))

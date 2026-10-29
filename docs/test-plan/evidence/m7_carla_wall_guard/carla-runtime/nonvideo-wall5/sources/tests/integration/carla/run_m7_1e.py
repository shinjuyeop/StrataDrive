#!/usr/bin/env python3
"""Bounded dedicated-server diagnostic runner. Preserve every exit/ready failure."""
import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
import carla


def save(p,r):p.write_text(json.dumps(r,indent=2)+'\n')

def no_core():resource.setrlimit(resource.RLIMIT_CORE,(0,0))

def descendants(pid):
    result=[]
    p=Path(f'/proc/{pid}/task/{pid}/children')
    if p.exists():
        for child in p.read_text().split():result.append(int(child));result.extend(descendants(int(child)))
    return result


def run(server,out,name,shutdown,matrix):
    folder=out/name;folder.mkdir()
    env=dict(os.environ,VK_ICD_FILENAMES='/usr/share/vulkan/icd.d/nvidia_icd.json')
    argv=['./CarlaUE4.sh','-RenderOffScreen','-quality-level=Low','-nosound','-carla-rpc-port=2000','-vulkan','-stdout','-FullStdOutLogOutput','-log']
    record={'argv':argv,'cwd':str(server),'signal':shutdown.name,'core_limit':0,'readiness':[],'matrix':matrix}
    with (folder/'server.log').open('wb') as log:
        proc=subprocess.Popen(argv,cwd=server,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=no_core)
        record['launcher_pid']=proc.pid;save(folder/'process.json',record)
        try:
            deadline=time.monotonic()+120
            ready=False
            while time.monotonic()<deadline and proc.poll() is None:
                try:
                    c=carla.Client('127.0.0.1',2000);c.set_timeout(5);w=c.get_world()
                    record['versions']=[c.get_client_version(),c.get_server_version()]
                    record['ready_episode']=w.id;ready=True;break
                except Exception as e:record['readiness'].append(str(e));save(folder/'process.json',record);time.sleep(1)
            if not ready:raise RuntimeError('server not ready')
            record['shipping_pids']=[pid for pid in descendants(proc.pid) if b'CarlaUE4-Linux-Shipping' in Path(f'/proc/{pid}/cmdline').read_bytes()]
            if len(record['shipping_pids'])!=1:raise RuntimeError('shipping process identity')
            if matrix:
                del w,c;gc.collect()
                cmd=[sys.executable,'-I',str(Path(__file__).with_name('m7_1e_diagnose.py').resolve()),'--output',str(folder/'attempt')]
                record['client_command']=cmd;save(folder/'process.json',record)
                with (folder/'client.log').open('wb') as clientlog:
                    client=subprocess.Popen(cmd,stdout=clientlog,stderr=subprocess.STDOUT)
                    try:record['client_exit']=client.wait(timeout=240)
                    except subprocess.TimeoutExpired:client.terminate();record['client_exit']=client.wait(timeout=10);record['client_timeout']=True
                c=carla.Client('127.0.0.1',2000);c.set_timeout(10);w=c.get_world()
            record['final']={'vehicles':[a.id for a in w.get_actors().filter('vehicle.*')],
                             'sensors':[a.id for a in w.get_actors().filter('sensor.*')],
                             'synchronous':w.get_settings().synchronous_mode,'fixed_delta':w.get_settings().fixed_delta_seconds}
            del w,c;gc.collect();time.sleep(.2)
            record['status']='OBSERVED'
        except Exception as e:record['error']=str(e);record['status']='FAIL'
        finally:
            owned=record.get('shipping_pids',[])
            if proc.poll() is None:
                if len(owned)==1 and Path(f'/proc/{owned[0]}').exists():os.kill(owned[0],shutdown)
                else:os.killpg(proc.pid,shutdown)
                try:record['launcher_exit']=proc.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    record['forced_kill']=True;os.killpg(proc.pid,signal.SIGKILL);record['launcher_exit']=proc.wait(timeout=5)
            else:record['launcher_exit']=proc.returncode
            record['listeners']=subprocess.check_output(['ss','-ltnp','sport = :2000 or sport = :2001 or sport = :2002'],text=True)
            save(folder/'process.json',record)
    return record


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--server',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    listeners=subprocess.check_output(['ss','-H','-ltn','sport = :2000 or sport = :2001 or sport = :2002'],text=True)
    if listeners:raise RuntimeError('ports already in use; no server touched')
    save(a.output/'runner.json',{'sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'profile':['empty_TERM','empty_INT','matrix_TERM'],'python':sys.executable})
    result=[]
    for name,sig,matrix in [('empty_TERM',signal.SIGTERM,False),('empty_INT',signal.SIGINT,False),('matrix_TERM',signal.SIGTERM,True)]:
        result.append(run(a.server,a.output,name,sig,matrix));save(a.output/'processes.json',result)
    return 0 if all(r['status']=='OBSERVED' for r in result) else 1

if __name__=='__main__':raise SystemExit(main())

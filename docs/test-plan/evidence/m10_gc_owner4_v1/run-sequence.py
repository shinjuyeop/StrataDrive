"""Unprivileged prospective sequence; wait for the explicit bounded host lease."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from runtime_restore import restore as restore_runtime

ROOT=Path(__file__).resolve().parents[4]
SERIES=Path(__file__).resolve().parent
WORK=ROOT/'build/m10-gc-owner4-v1'
ENGINE=Path('/d/shin/stratadrive-tools/UnrealEngine_4.26')
CARLA=Path('/d/shin/stratadrive-tools/m7-source/carla-0.9.16')
CAP=Path('/sys/devices/system/cpu/intel_pstate/max_perf_pct')
LOG=WORK/'power-lease.jsonl'


def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')


def command(which,action):
    if which=='module':return ['python3',str(ROOT/'tools/carla/m7_nodrive/build_endurance.py'),
        '--engine',str(ENGINE),'--source',str(CARLA),'--output',str(ROOT/'build/m10-gc-recovery-v1/server-build-02'),'--'+action]
    return ['python3',str(ROOT/'tools/carla/m7_nodrive/build_dxc_lifetime.py'),
        '--engine',str(ENGINE),'--output',str(ROOT/'build/m10-dxc-lifetime-v1'),'--'+action]


def call(argv,log):
    with log.open('w') as stream:return subprocess.run(argv,stdout=stream,stderr=subprocess.STDOUT).returncode


def main():
    assert os.geteuid()!=0,'only the narrow lease helper runs as root'
    assert json.loads((SERIES/'prepared.json').read_text())['status']=='READY_FOR_EXPLICIT_HOST_LEASE'
    owner=WORK/'experiment-owner.json';assert not owner.exists(),'one declared sequence, do not overwrite'
    fields=Path(f'/proc/{os.getpid()}/stat').read_text().rsplit(')',1)[1].split()
    identity=dict(pid=os.getpid(),uid=os.getuid(),start_ticks=int(fields[19]))
    write(owner,dict(**identity,status='WAITING_FOR_EXPLICIT_HOST_LEASE',created_wall_ns=time.monotonic_ns()))
    print(json.dumps(identity),flush=True)
    stopped=[]
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda *_:stopped.append(True))
    until=time.monotonic()+1800;events=[]
    while time.monotonic()<until and not stopped:
        if LOG.exists():
            events=[]
            for line in LOG.read_text().splitlines():
                try:events.append(json.loads(line))
                except json.JSONDecodeError:break # the final line may still be being written
            owners=[r for r in events if r.get('event')=='OWNER']
            applied=[r for r in events if r.get('event')=='APPLIED']
            if owners and applied and CAP.read_text().strip()=='70':
                assert all(owners[0][k]==identity[k] for k in identity),'lease belongs to another process'
                assert applied[0]['maximum_percent']==70 and applied[0]['seconds']==1800
                break
        time.sleep(1)
    else:
        write(SERIES/'sequence-disposition.json',dict(status='NOT_RUN_NO_PRIVILEGED_LEASE',cases={},reason='cancelled' if stopped else 'wait expired'))
        return
    write(SERIES/'lease-activation.json',dict(status='OBSERVED',owner=identity,events=events,observed_wall_ns=time.monotonic_ns()))
    cases={};current=None
    try:
        for name in ('normal-30s-01','normal-30s-02','normal-300s-01'):
            if stopped:cases[name]='NOT_RUN_OPERATOR_STOP';break
            if CAP.read_text().strip()!='70':cases[name]='NOT_RUN_LEASE_NOT_ACTIVE';break
            print('INSTALL '+name,flush=True)
            for which in ('module','dxc'):
                assert call(command(which,'install'),WORK/f'{name}-install-{which}.log')==0
            with (WORK/f'{name}-sequence.log').open('w') as stream:
                current=subprocess.Popen([sys.executable,str(SERIES/'prospective-runner.py'),name],stdout=stream,stderr=subprocess.STDOUT)
                # The finite runner owns normal shutdown/restoration. An operator
                # stop prevents subsequent cases; do not kill away current evidence.
                code=current.wait();current=None
            disposition=SERIES/name/'disposition.json'
            cases[name]=json.loads(disposition.read_text()) if disposition.exists() else dict(runner_exit=code,finite_diagnostic_pass=False)
            print('FINISHED '+name+' '+str(cases[name]['finite_diagnostic_pass']),flush=True)
            if code!=0 or not cases[name]['finite_diagnostic_pass']:break
    finally:
        restoration=restore_runtime(ROOT,SERIES,WORK,SERIES/'sequence-restoration.json',raise_on_failure=False)
        for name in ('normal-30s-01','normal-30s-02','normal-300s-01'):
            if name not in cases:cases[name]='NOT_RUN_STOP_ON_FIRST_FAILURE_OR_LEASE_END'
        write(SERIES/'sequence-disposition.json',dict(status='RECORDED',cases=cases,runtime_restoration=restoration,
            host_restoration='VERIFY_AFTER_OWNER_EXIT',native_perception_accepted=False,milestone_closed=False))
        if restoration['status']!='PASS':raise RuntimeError('runtime restoration failed')


if __name__=='__main__':main()

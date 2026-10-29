#!/usr/bin/env python3
"""Build the pinned RPC header and verify cancellation without an engine."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/carla/m7_nodrive'))
from install import PIN,replace
from rpc_shutdown_patch import apply

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--carla',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--patched',action='store_true')
    p.add_argument('--sanitize',action='store_true')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    assert subprocess.check_output(['git','-C',str(a.carla),'rev-parse','HEAD'],text=True).strip()==PIN
    def base(path):return subprocess.check_output(['git','-C',str(a.carla),'show',f'{PIN}:{path}'],text=True)
    relative='LibCarla/source/carla/rpc/Server.h'
    data=apply(base,replace)[relative] if a.patched else base(relative).encode()
    header=a.output/relative;header.parent.mkdir(parents=True);header.write_bytes(data)
    harness=a.output/'probe.cpp';harness.write_bytes(Path(__file__).with_suffix('.cpp').read_bytes())
    rpc=a.carla/'Build/rpclib-v2.2.1_c5-c10-libstdcxx-install'
    cmd=['clang++-14','-std=c++14','-pthread','-O1','-g','-fno-omit-frame-pointer','-DBOOST_ERROR_CODE_HEADER_ONLY',
         '-I'+str(a.output/'LibCarla/source'),'-I'+str(a.carla/'LibCarla/source'),
         '-isystem',str(rpc/'include'),'-isystem',str(a.carla/'Build/boost-1.84.0-c10-install/include'),
         str(harness),str(rpc/'lib/librpc.a'),'-o',str(a.output/'probe')]
    if a.patched:cmd.append('-DPATCHED')
    if a.sanitize:cmd+=['-fsanitize=address,undefined','-fno-pie','-no-pie']
    report=dict(pin=PIN,patched=a.patched,sanitized=a.sanitize,build_argv=cmd,
                header_sha256=hashlib.sha256(data).hexdigest(),harness_sha256=hashlib.sha256(harness.read_bytes()).hexdigest(),cases=[])
    with (a.output/'build.log').open('w') as log:
        report['build_exit']=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT).returncode
    if report['build_exit']==0:
        env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:abort_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
        for case in ('normal','queued','ignored','late','network'):
            with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
            argv=[str(a.output/'probe'),case,str(port)]
            with (a.output/(case+'.log')).open('w') as log:
                try:code=subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,env=env,timeout=5).returncode
                except subprocess.TimeoutExpired:code='TIMEOUT'
            report['cases'].append(dict(case=case,exit=code))
    (a.output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
    return int(report['build_exit']!=0 or any(c['exit']!=0 for c in report['cases']))

if __name__=='__main__':sys.exit(main())

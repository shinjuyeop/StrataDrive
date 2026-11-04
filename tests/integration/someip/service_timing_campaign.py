#!/usr/bin/env python3
"""Fixed, serial native service matrix. Retain runtime failures and audit separately."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    parser.add_argument('--split-owner-io',action='store_true')
    parser.add_argument('--owner-fifo',action='store_true')
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    cases=[(p,f,0) for p in ('normal','asan','tsan') for f in ('normal','ack-loss','actual-loss','stop-request-loss','stop-ack-loss')]
    cases += [(p,'normal',250) for p in ('normal','asan','tsan')]
    files=[HERE/'front_adapter.cpp',HERE/'fixture_signals.hpp',HERE/'front_run.py',Path(__file__),
           ROOT/'central/coordinator/async_coordinator_port.cpp',ROOT/'central/coordinator/async_coordinator_port.hpp',
           ROOT/'tests/unit/async_owner_test.cpp',ROOT/'tests/unit/fixture_signals_test.cpp',
           ROOT/'docs/test-plan/service-timing-protocol.md',
           HERE.parent/'diagnostics/audit_service_ordering.py',
           HERE.parent/'diagnostics/audit_service_timing.py',
           HERE.parent/'diagnostics/audit_native_service.py',HERE.parent/'diagnostics/audit_native_service_faults.py']
    manifest={'base':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'cases':cases,'sources':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
              'binaries':{p:hashlib.sha256((ROOT/f'build/m5-someip-{p}/project/tests/integration/someip/someip_front_adapter').read_bytes()).hexdigest() for p in ('normal','asan','tsan')}}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    results=[]
    for profile,fault,delay in cases:
        binary=ROOT/f'build/m5-someip-{profile}/project/tests/integration/someip/someip_front_adapter'
        if hashlib.sha256(binary.read_bytes()).hexdigest()!=manifest['binaries'][profile]:
            raise RuntimeError('binary changed during fixed campaign: '+profile)
        name=f'{profile}-{fault}'+('-slow-signals' if delay else '')
        directory=out/name
        command=[sys.executable,str(HERE/'front_run.py'),str(directory),'--profile',profile,
                 '--three','--simple-vehicle','--diagnostics','--diagnostic-service','--isolated-ecus',
                 '--cases','central-rejoin']
        if profile=='tsan':command+=['--fixed-layout']
        if args.split_owner_io:command+=['--split-owner-io']
        if args.owner_fifo:command+=['--owner-fifo']
        if fault!='normal':command+=['--service-fault',fault]
        if delay:command+=['--signal-write-delay-ms',str(delay)]
        with (out/(name+'.runtime.log')).open('w') as log:
            runtime=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=False).returncode
        audit=HERE.parent/'diagnostics'/('audit_native_service.py' if fault=='normal' else 'audit_native_service_faults.py')
        with (out/(name+'.audit.log')).open('w') as log:
            qualified=subprocess.run([sys.executable,str(audit),str(directory/'central-rejoin-1'),'--mutations'],stdout=log,stderr=subprocess.STDOUT,check=False).returncode
        with (out/(name+'.ordering.log')).open('w') as log:
            ordering=subprocess.run([sys.executable,str(HERE.parent/'diagnostics/audit_service_ordering.py'),str(directory/'central-rejoin-1'),'--mutations'],stdout=log,stderr=subprocess.STDOUT,check=False).returncode
        timing=0
        if args.split_owner_io:
            with (out/(name+'.timing.log')).open('w') as log:
                timing=subprocess.run([sys.executable,str(HERE.parent/'diagnostics/audit_service_timing.py'),str(directory/'central-rejoin-1'),'--mutations'],stdout=log,stderr=subprocess.STDOUT,check=False).returncode
        results.append({'name':name,'command':command,'runtime_exit':runtime,'audit_exit':qualified,'ordering_exit':ordering,'timing_exit':timing})
        (out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
        print(json.dumps(results[-1]),flush=True)
    return int(any(r['audit_exit'] or r['ordering_exit'] or r['timing_exit'] for r in results))


if __name__=='__main__':sys.exit(main())

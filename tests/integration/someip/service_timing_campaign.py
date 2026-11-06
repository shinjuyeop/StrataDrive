#!/usr/bin/env python3
"""Fixed, serial native service matrix. Retain runtime failures and audit separately."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def validate_native_build(cache):
    values=dict(line.split('=',1) for line in cache.splitlines() if '=' in line and not line.startswith(('//','#')))
    if (values.get('CMAKE_BUILD_TYPE:STRING')!='RelWithDebInfo' or
        values.get('STRATADRIVE_SANITIZERS:BOOL')!='OFF' or values.get('STRATADRIVE_TSAN:BOOL')!='OFF' or
        any('-fsanitize' in v for k,v in values.items() if k.startswith('CMAKE_CXX_FLAGS'))):
        raise ValueError('split-v1 requires the noninstrumented RelWithDebInfo build')


def case_matrix(validation_profile, tsan_repeats=1):
    faults=('normal','ack-loss','actual-loss','stop-request-loss','stop-ack-loss')
    if validation_profile=='split-v1':
        if tsan_repeats!=1:raise ValueError('split-v1 has no instrumented native repeat gate')
        return [('normal',f,d,r) for r in (1,2,3)
                for f,d in [*((f,0) for f in faults),('normal',250)]]
    if validation_profile!='legacy-mixed' or tsan_repeats not in (1,3):
        raise ValueError('unknown validation profile/repeat count')
    cases=[(p,f,0,1) for p in ('normal','asan','tsan') for f in faults]
    cases += [(p,'normal',250,1) for p in ('normal','asan','tsan')]
    for repeat in range(2,tsan_repeats+1):cases += [('tsan',f,0,repeat) for f in faults]+[('tsan','normal',250,repeat)]
    return cases


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    parser.add_argument('--split-owner-io',action='store_true')
    parser.add_argument('--separate-aux-io',action='store_true')
    parser.add_argument('--owner-fifo',action='store_true')
    parser.add_argument('--sdk-fifo',action='store_true')
    parser.add_argument('--sdk-io-threads',type=int,choices=(1,2),default=2)
    parser.add_argument('--tsan-repeats',type=int,choices=(1,3),default=1)
    parser.add_argument('--response-audit',action='store_true')
    parser.add_argument('--defer-audits',action='store_true',help='finish every fixed runtime before CPU-intensive offline readers')
    parser.add_argument('--validation-profile',choices=('legacy-mixed','split-v1'),default='legacy-mixed',
                        help='split-v1: 18 noninstrumented service runs; sanitizer component suite is a separate required gate')
    args=parser.parse_args()
    if args.sdk_fifo and args.validation_profile!='split-v1':parser.error('sdk-fifo requires the split-v1 native-only gate')
    if args.separate_aux_io and not args.split_owner_io:parser.error('separate-aux-io requires split-owner-io')
    if args.validation_profile=='split-v1' and (args.tsan_repeats!=1 or args.sdk_io_threads!=2 or not all((args.split_owner_io,args.separate_aux_io,args.owner_fifo,args.response_audit,args.defer_audits))):
        parser.error('split-v1 requires fixed split/FIFO/aux placement, response/deferred audits and no tsan-repeats')
    if args.validation_profile=='split-v1':validate_native_build((ROOT/'build/m5-someip-normal/project/CMakeCache.txt').read_text())
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    cases=case_matrix(args.validation_profile,args.tsan_repeats)
    files=[ROOT/'docs/test-plan/service-validation-protocol.md',ROOT/'tests/unit/service_validation_test.py',
           ROOT/'central/diagnostics/bootstrap_journal.hpp',ROOT/'central/diagnostics/bootstrap_journal.cpp',
           HERE.parent/'diagnostics/audit_bootstrap_incidents.py',
           HERE.parent/'diagnostics/service_sanitizer_suite.py',ROOT/'interfaces/someip/owner_credit_retirement.hpp',ROOT/'interfaces/someip/owner_message_binding.hpp',
           ROOT/'tests/unit/remote_contract_test.cpp',ROOT/'docs/test-plan/egress-availability-protocol.md',ROOT/'simulation/runtime/plant_io.hpp',HERE/'plant_io.hpp',ROOT/'tests/unit/plant_io_test.cpp',
           ROOT/'docs/test-plan/plant-field-io-protocol.md',HERE/'front_adapter.cpp',HERE/'fixture_signals.hpp',HERE/'front_run.py',HERE/'run.py',Path(__file__),
           HERE/'owner_schedule.hpp',ROOT/'tests/unit/owner_schedule_test.cpp',ROOT/'docs/test-plan/owner-input-phase-protocol.md',
           ROOT/'central/coordinator/vehicle_coordinator.cpp',ROOT/'central/coordinator/vehicle_coordinator.hpp',
           ROOT/'tests/unit/vehicle_coordinator_test.cpp',ROOT/'docs/test-plan/allocation-release-protocol.md',
           ROOT/'central/vehicle_management/normal_stop.hpp',ROOT/'tests/unit/normal_stop_test.cpp',
           ROOT/'docs/test-plan/stop-deadline-poll-protocol.md',
           ROOT/'docs/test-plan/deferred-grant-protocol.md',ROOT/'tests/unit/async_owner_test.cpp',
           ROOT/'docs/test-plan/deferred-grant-confirmation-protocol.md',
           HERE/'kernel_capture.py',ROOT/'docs/test-plan/sdk-io-threads-protocol.md',ROOT/'tests/unit/sdk_stages_test.py',
           HERE/'sdk_outcomes.py',HERE/'native_oracle.py',HERE/'fixture_placement.hpp',HERE/'fixture_placement.py',
           HERE/'native_diagnostic_routes.cpp',HERE/'native_continuity_service.cpp',
           HERE.parent/'diagnostics/audit_central_restart.py',ROOT/'tests/unit/someip_pilot_test.py',
           ROOT/'central/coordinator/async_coordinator_port.cpp',ROOT/'central/coordinator/async_coordinator_port.hpp',
           ROOT/'tests/unit/async_owner_test.cpp',ROOT/'tests/unit/fixture_signals_test.cpp',
           ROOT/'interfaces/someip/owner_transport.hpp',ROOT/'interfaces/common/monotonic_condition.hpp',
           ROOT/'interfaces/common/concurrent_trace_buffer.hpp',ROOT/'tests/unit/concurrent_trace_buffer_test.cpp',
           ROOT/'tests/unit/monotonic_condition_test.cpp',ROOT/'cmake/CoreTests.cmake',
           ROOT/'docs/test-plan/service-response-protocol.md',ROOT/'docs/test-plan/auxiliary-io-protocol.md',
           ROOT/'docs/test-plan/service-timing-protocol.md',ROOT/'docs/test-plan/feedback-order-protocol.md',ROOT/'docs/test-plan/timing-trace-protocol.md',
           HERE.parent/'diagnostics/audit_service_ordering.py',
           HERE.parent/'diagnostics/audit_service_timing.py',
           HERE.parent/'diagnostics/audit_service_response.py',
           HERE.parent/'diagnostics/audit_native_service.py',HERE.parent/'diagnostics/audit_native_service_faults.py']
    manifest={'base':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'sdk_io_threads':args.sdk_io_threads,'sdk_fifo':args.sdk_fifo,
              'validation_profile':args.validation_profile,'scope':'native service; separate sanitizer gate required' if args.validation_profile=='split-v1' else 'legacy mixed instrumentation',
              'audit_phase':'after-all-runtimes' if args.defer_audits else 'interleaved',
              'cases':cases,'sources':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
              'binaries':{p:hashlib.sha256((ROOT/f'build/m5-someip-{p}/project/tests/integration/someip/someip_front_adapter').read_bytes()).hexdigest() for p in sorted({c[0] for c in cases})}}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    results=[]
    def audit_result(row):
        directory=out/row['name'];fault=row['fault']
        readers=[('audit_exit','audit','audit_native_service.py' if fault=='normal' else 'audit_native_service_faults.py'),
                 ('ordering_exit','ordering','audit_service_ordering.py')]
        if args.split_owner_io:readers.append(('timing_exit','timing','audit_service_timing.py'))
        if args.response_audit:readers.append(('response_exit','response','audit_service_response.py'))
        row.update(timing_exit=0,response_exit=0)
        for field,tag,script in readers:
            with (out/(row['name']+'.'+tag+'.log')).open('w') as log:
                row[field]=subprocess.run([sys.executable,str(HERE.parent/'diagnostics'/script),str(directory/'central-rejoin-1'),'--mutations'],stdout=log,stderr=subprocess.STDOUT,check=False).returncode
        (out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
        print(json.dumps(row),flush=True)
    for profile,fault,delay,repeat in cases:
        binary=ROOT/f'build/m5-someip-{profile}/project/tests/integration/someip/someip_front_adapter'
        if hashlib.sha256(binary.read_bytes()).hexdigest()!=manifest['binaries'][profile]:
            raise RuntimeError('binary changed during fixed campaign: '+profile)
        for source,digest in manifest['sources'].items():
            if hashlib.sha256((ROOT/source).read_bytes()).hexdigest()!=digest:raise RuntimeError('source changed during fixed campaign: '+source)
        name=f'{profile}-{fault}'+('-slow-signals' if delay else '')+(f'-r{repeat}' if repeat>1 else '')
        directory=out/name
        command=[sys.executable,str(HERE/'front_run.py'),str(directory),'--profile',profile,
                 '--three','--simple-vehicle','--diagnostics','--diagnostic-service','--isolated-ecus',
                 '--cases','central-rejoin']
        if profile=='tsan':command+=['--fixed-layout']
        if args.split_owner_io:command+=['--split-owner-io']
        if args.separate_aux_io:command+=['--separate-aux-io']
        if args.owner_fifo:command+=['--owner-fifo']
        if args.sdk_fifo:command+=['--sdk-fifo']
        command+=['--sdk-io-threads',str(args.sdk_io_threads)]
        if fault!='normal':command+=['--service-fault',fault]
        if delay:command+=['--signal-write-delay-ms',str(delay)]
        with (out/(name+'.runtime.log')).open('w') as log:
            runtime=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=False).returncode
        results.append({'name':name,'fault':fault,'command':command,'runtime_exit':runtime,'audit_exit':None,'ordering_exit':None,'timing_exit':None,'response_exit':None})
        (out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
        if not args.defer_audits:audit_result(results[-1])
        else:print(json.dumps(results[-1]),flush=True)
    (out/'runtime-complete.json').write_text(json.dumps({'monotonic_ns':time.monotonic_ns(),'runtimes':len(results)})+'\n')
    if args.defer_audits:
        for row in results:audit_result(row)
    return int(any(r['audit_exit'] or r['ordering_exit'] or r['timing_exit'] or r['response_exit'] for r in results))


if __name__=='__main__':sys.exit(main())

#!/usr/bin/env python3
"""Fixed six-run diagnostic cohort, followed by all offline audits. No retry."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from run import ROOT


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('sdk_build',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--compare-io-threads',action='store_true');a=p.parse_args()
    sdk=a.sdk_build.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    manifest=json.loads((sdk/'manifest.json').read_text());assert manifest['profile']=='tsan'
    files=[Path(__file__),*Path(__file__).parent.glob('*.py'),Path(__file__).with_name('sdk_observation.hpp'),
           ROOT/'tests/integration/diagnostics/audit_sdk_stages.py',ROOT/'tests/unit/sdk_stages_test.py',
           ROOT/'docs/test-plan/sdk-stages-protocol.md',ROOT/'docs/test-plan/sdk-io-threads-protocol.md',
           ROOT/'tests/integration/diagnostics/audit_service_timing.py']
    sources={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(set(files))}
    binary=ROOT/'build/m5-someip-tsan/project/tests/integration/someip/someip_front_adapter'
    binary_hash=hashlib.sha256(binary.read_bytes()).hexdigest()
    assert manifest['helper_sha256']==sources['tests/integration/someip/sdk_observation.hpp']
    plan={'base':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
          'sdk':manifest,'sources':sources,'binary':str(binary),'binary_sha256':binary_hash,
          'cases':([(block,fault,threads) for block,threads in enumerate((2,1,1,2),1) for fault in ('ack-loss','stop-ack-loss')]
                   if a.compare_io_threads else [(repeat,fault,2) for repeat in range(1,4) for fault in ('ack-loss','stop-ack-loss')]),
          'audit_phase':'after-all-runtimes','sched_schedstats':Path('/proc/sys/kernel/sched_schedstats').read_text().strip(),
          'perf_event_paranoid':Path('/proc/sys/kernel/perf_event_paranoid').read_text().strip()}
    (out/'manifest.json').write_text(json.dumps(plan,indent=2)+'\n')
    env=dict(os.environ,STRATADRIVE_SOMEIP_OBSERVATION_LIB=manifest['library_path']);rows=[]
    for repeat,fault,threads in plan['cases']:
        assert hashlib.sha256(binary.read_bytes()).hexdigest()==binary_hash
        for path,digest in sources.items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
        for path,digest in manifest['libraries'].items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest,path
        name=f'tsan-{fault}-r{repeat}'
        command=[sys.executable,str(Path(__file__).with_name('front_run.py')),str(out/name),'--profile','tsan',
            '--fixed-layout','--three','--simple-vehicle','--diagnostics','--diagnostic-service','--isolated-ecus',
            '--split-owner-io','--owner-fifo','--separate-aux-io','--sdk-observation','--sdk-io-threads',str(threads),'--service-fault',fault,'--cases','central-rejoin']
        row={'name':name,'sdk_io_threads':threads,'command':command,'begin_ns':time.monotonic_ns(),'load_before':Path('/proc/loadavg').read_text().strip()}
        with (out/(name+'.runtime.txt')).open('w') as log:row['runtime_exit']=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT).returncode
        row.update(end_ns=time.monotonic_ns(),load_after=Path('/proc/loadavg').read_text().strip());rows.append(row)
        (out/'results.json').write_text(json.dumps(rows,indent=2)+'\n');print(name,'runtime',row['runtime_exit'],flush=True)
    (out/'runtime-complete.json').write_text(json.dumps({'runs':len(rows),'ns':time.monotonic_ns()})+'\n')
    for row in rows:
        for tag,script in [('service','audit_native_service_faults.py'),('ordering','audit_service_ordering.py'),
                           ('timing','audit_service_timing.py'),('response','audit_service_response.py'),('stages','audit_sdk_stages.py')]:
            command=[sys.executable,str(ROOT/'tests/integration/diagnostics'/script),str(out/row['name']/'central-rejoin-1')]
            if tag!='stages':command+=['--mutations']
            with (out/(row['name']+'.'+tag+'.txt')).open('w') as log:
                row[tag+'_exit']=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT).returncode
        (out/'results.json').write_text(json.dumps(rows,indent=2)+'\n');print(row['name'],{k:v for k,v in row.items() if k.endswith('_exit')},flush=True)
    # The declared loss recipes intentionally return runtime failure. Only the
    # strict fault oracle can distinguish that from a failed normal prerequisite.
    return int(any(r[field] for r in rows for field in ('service_exit','ordering_exit','timing_exit','response_exit','stages_exit')))


if __name__=='__main__':sys.exit(main())

#!/usr/bin/env python3
"""Fixed M9 component/simulation gate, separate from native wall-time acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tests/integration/someip'))
from run import sanitizer_errors

TARGETS=('remote_contract_test','async_owner_test','vehicle_coordinator_test','normal_stop_test',
         'owner_schedule_test','m4_async_runtime_test','plant_io_test','concurrent_trace_buffer_test',
         'monotonic_condition_test','fixture_signals_test','diagnostics_test','diagnostic_binding_test',
         'native_diagnostics_test','remote_diagnostics_context_test','diagnostics_delivery_test',
         'diagnostics_delivery_process_test','diagnostics_journal_test','control_diagnostics_sil_test',
         'native_diagnostics_sil_test','startup_diagnostics_sil_test','owner_diagnostics_sil_test')


def test_filter(target):
    return '-M4AsyncWall.*' if target=='m4_async_runtime_test' else '*'


def judge_xml(path, exit_code, log):
    root=ET.parse(path).getroot()
    count=int(root.attrib['tests'])
    bad=sum(int(root.attrib.get(k,0)) for k in ('failures','errors','disabled'))
    skipped=sum(1 for case in root.iter('testcase') if case.find('skipped') is not None or case.get('status')=='notrun')
    return {'tests':count,'failures_errors_disabled':bad,'skipped':skipped,
            'sanitizer_errors':sanitizer_errors(log),
            'pass':exit_code==0 and count>0 and bad==skipped==0 and not sanitizer_errors(log)}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('output',type=Path);p.add_argument('--build',type=Path,required=True)
    p.add_argument('--profile',choices=('asan','tsan'),required=True);a=p.parse_args()
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);build=a.build.resolve()
    cache=(build/'CMakeCache.txt').read_text()
    flag='STRATADRIVE_TSAN' if a.profile=='tsan' else 'STRATADRIVE_SANITIZERS'
    if flag+':BOOL=ON' not in cache:raise ValueError('build is not instrumented for '+a.profile)
    hashes={t:hashlib.sha256((build/t).read_bytes()).hexdigest() for t in TARGETS}
    manifest={'profile':a.profile,'base':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'scope':'component/logical SIL and concurrency; no native wall timing claim',
              'binaries':hashes,'filters':{t:test_filter(t) for t in TARGETS},
              'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');rows=[]
    for target in TARGETS:
        binary=build/target
        if hashlib.sha256(binary.read_bytes()).hexdigest()!=hashes[target]:raise ValueError('binary changed: '+target)
        xml=out/(target+'.xml');command=(['setarch','x86_64','-R'] if a.profile=='tsan' else [])
        command += [str(binary),'--gtest_filter='+test_filter(target),'--gtest_output=xml:'+str(xml)]
        with (out/(target+'.log')).open('w') as log:
            try:code=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=600,check=False).returncode
            except subprocess.TimeoutExpired:code=124
        row={'target':target,'command':command,'exit':code}
        try:row.update(judge_xml(xml,code,(out/(target+'.log')).read_text(errors='replace')))
        except (OSError,ValueError,ET.ParseError) as error:row.update({'pass':False,'error':str(error)})
        rows.append(row);(out/'results.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(row),flush=True)
    return int(not all(r['pass'] for r in rows))


if __name__=='__main__':sys.exit(main())

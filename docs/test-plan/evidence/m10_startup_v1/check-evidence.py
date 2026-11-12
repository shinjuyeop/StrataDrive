#!/usr/bin/env python3
"""Rebuild instrumented-original and corrected owners from one archived source set."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import xml.etree.ElementTree as ET


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args()
    bundle=Path(__file__).resolve().parent;work=a.work.resolve();work.mkdir(parents=True,exist_ok=False);source=work/'source';source.mkdir()
    manifest=json.loads((bundle/'sources.json').read_text());assert sha(bundle/'sources.tar.gz')==manifest['archive_sha256']
    with tarfile.open(bundle/'sources.tar.gz','r:gz') as tar:
        members=tar.getmembers();assert len(members)==len(manifest['files']) and {m.name for m in members}==set(manifest['files'])
        for m in members:
            name=Path(m.name);assert m.isfile() and not name.is_absolute() and '..' not in name.parts
            data=tar.extractfile(m).read();item=manifest['files'][m.name]
            assert len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256']
            dst=source/name;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(data)
    env=dict(os.environ,PYTHONPATH=str(source)+':'+str(source/'tests/integration/perception'),OMP_WAIT_POLICY='PASSIVE')
    build=work/'build'
    def run(name,cmd):
        with (work/(name+'.log')).open('w') as f:r=subprocess.run(list(map(str,cmd)),cwd=source,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=300)
        if r.returncode:raise RuntimeError(name+'; see retained log')
    run('configure',['cmake','-S',source,'-B',build,'-DCMAKE_BUILD_TYPE=Release','-DSTRATADRIVE_M7_FUNCTIONAL_TESTS=ON','-DSTRATADRIVE_PERCEPTION_TESTS=ON','-DPython3_EXECUTABLE='+str(Path(sys.executable).absolute())])
    old=source/'docs/test-plan/evidence/m10_startup_v1/baseline-runtime'
    current={n:(source/'simulation/runtime'/n).read_bytes() for n in ('async_leaf_owner.cpp','async_leaf_owner.hpp')}
    for n in current:shutil.copy2(old/n,source/'simulation/runtime'/n)
    run('baseline-build',['cmake','--build',build,'--target','m7_wall_startup_replay','-j4'])
    replay=[sys.executable,source/'tests/integration/perception/replay_wall_startup_v1.py','--capture',source/'docs/test-plan/evidence/m10_live_shadow_v1/run-01/capture','--binary',build/'tests/integration/carla/m7_1g/m7_wall_startup_replay','--scenario',source/'tests/integration/carla/scenarios/m7_integrated_v1.txt']
    run('baseline-replay',replay+['--output',work/'baseline-replay','--require-exact'])
    for n,data in current.items():(source/'simulation/runtime'/n).write_bytes(data)
    run('corrected-build',['cmake','--build',build,'--target','m7_wall_startup_replay','m7_wheel_test','m7_carla_wall_owner','-j4'])
    run('fixed-replay',replay+['--output',work/'fixed-replay'])
    for mode in ('baseline-replay','fixed-replay'):
        for n in ('input.txt','replay.csv','replay.json'):
            assert (work/mode/n).read_bytes()==(bundle/mode/n).read_bytes(),(mode,n)
    tests=work/'m7_wheel_test.xml'
    run('wheel-tests',[build/'tests/integration/carla/m7_1g/m7_wheel_test','--gtest_output=xml:'+str(tests)])
    result=ET.parse(tests).getroot().attrib;assert int(result['tests'])==38 and int(result['failures'])==int(result['errors'])==0
    run('cleanup-tests',[sys.executable,'-m','unittest','test_control_shadow_cleanup_v1','-v'])
    report=dict(status='PASS',source_files=len(manifest['files']),baseline_replay_exact=True,corrected_replay_exact=True,cpp_tests=38,python_tests=4,
                scope='frozen functional reproduction; no new live trial')
    (work/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()

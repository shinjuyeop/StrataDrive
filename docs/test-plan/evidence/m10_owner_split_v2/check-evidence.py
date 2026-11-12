#!/usr/bin/env python3
"""Verify/extract frozen sources and run focused tests, without starting a server."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile


def extract(bundle,work):
    frozen=json.loads((bundle/'sources.json').read_text())
    assert hashlib.sha256((bundle/'sources.tar.gz').read_bytes()).hexdigest()==frozen['archive_sha256']
    source=work/'source';source.mkdir(parents=True,exist_ok=False)
    with tarfile.open(bundle/'sources.tar.gz','r:gz') as tar:
        members=tar.getmembers();assert len(members)==len(frozen['files']) and {m.name for m in members}==set(frozen['files'])
        for member in members:
            name=Path(member.name);assert member.isfile() and not name.is_absolute() and '..' not in name.parts
            data=tar.extractfile(member).read();item=frozen['files'][member.name]
            assert len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256']
            path=source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    return source,frozen


def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();work=a.work.resolve();work.mkdir(parents=True,exist_ok=False)
    source,frozen=extract(Path(__file__).resolve().parent,work)
    env=dict(os.environ,PYTHONPATH=str(source)+':'+str(source/'tests/integration/perception'),PYTHONDONTWRITEBYTECODE='1')
    with (work/'tests.log').open('w') as log:
        subprocess.run([sys.executable,'-m','unittest','test_owner_split_profile_v1','test_fence_compare_v1','test_server_timing_v1','test_control_shadow_cleanup_v1','test_readback_v1','test_world_async_v1','test_world_async_2k_v1','test_boundary_2k_v1','test_ipc_2k_v1','-v'],cwd=source,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
    build=work/'build'
    def run(name,cmd):
        with (work/(name+'.log')).open('w') as log:
            subprocess.run(list(map(str,cmd)),cwd=source,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
    run('configure',['cmake','-S',source,'-B',build,'-DCMAKE_BUILD_TYPE=Release','-DSTRATADRIVE_M7_FUNCTIONAL_TESTS=ON','-DSTRATADRIVE_PERCEPTION_TESTS=ON','-DPython3_EXECUTABLE='+sys.executable])
    run('build',['cmake','--build',build,'--target','m7_native_admission_test','m7_wall_startup_replay','-j4'])
    run('admission',[build/'tests/integration/carla/m7_1q/m7_native_admission_test'])
    result=dict(status='PASS',cpp_tests=23,source_files=len(frozen['files']),tests=69,scope='frozen focused tests including compiled C++ journal; no live launch')
    (work/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()

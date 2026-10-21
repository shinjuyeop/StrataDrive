#!/usr/bin/env python3
"""Build pinned, isolated SDK and pilot; never installs into the system."""
import argparse
import fcntl
from run import open_lock
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request
import time

ROOT = Path(__file__).resolve().parents[3]
PIN = '4187431d2815bd351845a09d01aa85b2a3163cab'
BOOST_SHA = '7009fe1faa1697476bdc7027703a2badb84e849b7b0baad5086b087b971f8617'

def main():
    p = argparse.ArgumentParser()
    p.add_argument('profile', choices=['normal', 'asan', 'tsan'])
    a = p.parse_args()
    deps = ROOT/'build/m5-someip-deps'
    out = ROOT/'build'/('m5-someip-'+a.profile)
    deps.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    logs = out/('attempt-'+str(time.time_ns()))
    logs.mkdir()
    commands = []
    def run(cmd, cwd=ROOT):
        commands.append({'argv':list(map(str,cmd)), 'cwd':str(cwd)})
        (logs/'commands.json').write_text(json.dumps(commands, indent=2)+'\n')
        with (logs/f'build-{len(commands):02}.txt').open('w') as log:
            subprocess.run(list(map(str,cmd)), cwd=cwd, stdout=log,
                           stderr=subprocess.STDOUT, check=True, timeout=900)
    sdk = deps/'vsomeip'
    if not sdk.exists():
        run(['git','clone','--depth','1','--branch','3.7.6',
             'https://github.com/COVESA/vsomeip.git',sdk])
    assert subprocess.check_output(['git','-C',str(sdk),'rev-parse','HEAD'],text=True).strip() == PIN
    assert not subprocess.check_output(['git','-C',str(sdk),'status','--porcelain'])
    archive = deps/'boost_1_85_0.tar.bz2'
    if not archive.exists():
        urllib.request.urlretrieve('https://archives.boost.io/release/1.85.0/source/'+archive.name,archive)
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == BOOST_SHA
    boost = deps/'boost_1_85_0'
    if not boost.exists(): run(['tar','-xjf',archive,'-C',deps])
    if not (boost/'b2').exists(): run(['./bootstrap.sh','--with-libraries=filesystem'],boost)
    flags = '-O1 -g -fno-omit-frame-pointer'
    sanitize = {'normal':'','asan':'address,undefined','tsan':'thread'}[a.profile]
    if sanitize: flags += ' -fsanitize='+sanitize
    run(['./b2','-j4','--with-filesystem','variant=release','link=shared',
         'cxxflags='+flags,'linkflags='+('-fsanitize='+sanitize if sanitize else ''),
         '--build-dir='+str(out/'boost-build'),'--prefix='+str(out/'install'),'install'],boost)
    run(['cmake','-S',sdk,'-B',out/'sdk','-G','Ninja',
         '-DCMAKE_BUILD_TYPE=RelWithDebInfo','-DCMAKE_CXX_FLAGS='+flags,
         '-DCMAKE_INSTALL_PREFIX='+str(out/'install'),
         '-DCMAKE_PREFIX_PATH='+str(out/'install'),'-DBoost_NO_SYSTEM_PATHS=ON',
         '-DENABLE_SIGNAL_HANDLING=OFF','-DENABLE_MULTIPLE_ROUTING_MANAGERS=OFF',
         '-DDISABLE_DLT=ON','-DCMAKE_EXPORT_COMPILE_COMMANDS=ON'])
    run(['cmake','--build',out/'sdk','--parallel','3'])
    run(['cmake','--install',out/'sdk'])
    run(['cmake','-S',ROOT,'-B',out/'project','-G','Ninja','-DBUILD_TESTING=OFF',
         '-DSTRATADRIVE_SOMEIP_PILOT=ON','-DCMAKE_BUILD_TYPE=RelWithDebInfo',
         '-DCMAKE_CXX_FLAGS=-O1 -g -fno-omit-frame-pointer',
         '-DCMAKE_PREFIX_PATH='+str(out/'install'),
         '-DSTRATADRIVE_SANITIZERS='+('ON' if a.profile=='asan' else 'OFF'),
         '-DSTRATADRIVE_TSAN='+('ON' if a.profile=='tsan' else 'OFF')])
    run(['cmake','--build',out/'project','--target','someip_pilot','someip_front_adapter','--parallel','4'])

if __name__ == '__main__':
    with open_lock() as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        main()

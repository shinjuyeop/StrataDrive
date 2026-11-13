"""Isolated UE4 ShaderConductor build and reversible, hash-checked DXC install.

The owned source copy changes only ManagedStatic mutex lifetime and a CRLF shell
script. Same-host x86_64 compilation uses the bundled SDK/sysroot/libc++ without
the old cross-build's concurrent recursive Ninja invocations. CMake3 is required.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from build_endurance import sha,stopped

RELATIVE='Engine/Binaries/ThirdParty/ShaderConductor/Linux/x86_64-unknown-linux-gnu/libdxcompiler.so'
MUTEX=Path('External/DirectXShaderCompiler/lib/Support/ManagedStatic.cpp')
GUESS=Path('External/DirectXShaderCompiler/autoconf/config.guess')
OLD='  static sys::Mutex ManagedStaticMutex;\n  return ManagedStaticMutex;'
NEW=('  // DllShutdown runs after function-static destructors. Keep this tiny\n'
     '  // lock alive until process teardown, including the final llvm_shutdown.\n'
     '  static sys::Mutex *const ManagedStaticMutex = new sys::Mutex();\n'
     '  return *ManagedStaticMutex;')


def prepare(engine,out):
    original=engine/'Engine/Source/ThirdParty/ShaderConductor/ShaderConductor'
    out.mkdir(parents=True,exist_ok=False);shutil.copytree(original,out/'source')
    p=out/'source'/MUTEX;text=p.read_text();assert text.count(OLD)==1;p.write_text(text.replace(OLD,NEW))
    p=out/'source'/GUESS;p.write_bytes(p.read_bytes().replace(b'\r\n',b'\n'))
    sdk=engine/'Engine/Extras/ThirdPartyNotUE/SDKs/HostLinux/Linux_x64/v17_clang-10.0.1-centos7/x86_64-unknown-linux-gnu'
    third=engine/'Engine/Source/ThirdParty';libs=third/'Linux/LibCxx/lib/Linux/x86_64-unknown-linux-gnu'
    # Host and target are both Linux x86_64. The sysroot still binds SDK headers
    # and ABI. Do not declare cross compilation and recursively race tablegen.
    text=f'''set(CMAKE_SYSROOT "{sdk}")
set(CMAKE_C_COMPILER "{sdk}/bin/clang")
set(CMAKE_C_COMPILER_TARGET x86_64-unknown-linux-gnu)
set(CMAKE_CXX_COMPILER "{sdk}/bin/clang++")
set(CMAKE_CXX_COMPILER_TARGET x86_64-unknown-linux-gnu)
set(CMAKE_C_FLAGS "-fms-extensions")
set(CMAKE_CXX_FLAGS "-std=c++1z -fms-extensions -nostdinc++")
include_directories("{third}/Linux/LibCxx/include" "{third}/Linux/LibCxx/include/c++/v1")
set(CMAKE_EXE_LINKER_FLAGS "-stdlib=libc++ -L{libs} {libs}/libc++.a {libs}/libc++abi.a")
set(CMAKE_MODULE_LINKER_FLAGS "${{CMAKE_EXE_LINKER_FLAGS}}")
set(CMAKE_SHARED_LINKER_FLAGS "${{CMAKE_EXE_LINKER_FLAGS}}")
'''
    (out/'toolchain-host.cmake').write_text(text)


def record(engine,out):
    assert not (out/'manifest.json').exists(),'immutable build manifest'
    original=engine/'Engine/Source/ThirdParty/ShaderConductor/ShaderConductor'
    installed=engine/RELATIVE;source=out/'source';inputs={};changes={}
    for path in sorted(original.rglob('*')):
        if not path.is_file():continue
        relative=path.relative_to(original);other=source/relative
        before,after=sha(path),sha(other);inputs[str(relative)]=before
        if before!=after:changes[str(relative)]=dict(before=before,after=after)
    assert set(changes)=={str(MUTEX),str(GUESS)}
    assert (source/MUTEX).read_text()==(original/MUTEX).read_text().replace(OLD,NEW)
    assert (source/GUESS).read_bytes()==(original/GUESS).read_bytes().replace(b'\r\n',b'\n')
    binary=out/'build-host/External/DirectXShaderCompiler/lib/libdxcompiler.so';assert binary.is_file()
    backup=out/'original-libdxcompiler.so'
    if backup.exists():assert sha(backup)==sha(installed)
    else:shutil.copy2(installed,backup)
    candidate=out/'libdxcompiler.so';shutil.copy2(binary,candidate)
    subprocess.run(['strip','--strip-debug',str(candidate)],check=True)
    manifests=dict(schema='m10-dxc-lifetime-build-v1',installed_path=str(installed),
        original_sha256=sha(backup),candidate_sha256=sha(candidate),unstripped_sha256=sha(binary),
        source_root=str(original),source_files=inputs,changes=changes,
        mutex_scope='one intentionally retained small mutex per library load; other ManagedStatic objects still destroyed',
        build_files={str(p.relative_to(out)):sha(p) for p in [out/'toolchain-host.cmake',out/'build-host/CMakeCache.txt',out/'build-host/build.ninja']})
    (out/'manifest.json').write_text(json.dumps(manifests,indent=2)+'\n')
    return manifests


def main(a):
    engine=a.engine.resolve();out=a.output.resolve();installed=engine/RELATIVE
    if a.install or a.restore:
        stopped();m=json.loads((out/'manifest.json').read_text());assert str(installed)==m['installed_path']
        before=m['candidate_sha256'] if a.restore else m['original_sha256']
        after=m['original_sha256'] if a.restore else m['candidate_sha256']
        assert sha(installed)==before
        replacement=out/('original-libdxcompiler.so' if a.restore else 'libdxcompiler.so');assert sha(replacement)==after
        temporary=Path(str(installed)+'.strata-lifetime-new');shutil.copy2(replacement,temporary)
        assert sha(temporary)==after;stopped();assert sha(installed)==before;temporary.replace(installed)
        print(json.dumps(dict(restored=a.restore,sha256=sha(installed))));return
    if not out.exists():prepare(engine,out)
    if not a.record:
        version=subprocess.check_output(['/usr/bin/cmake','--version'],text=True).splitlines()[0]
        assert version.startswith('cmake version 3.'),'use compatible CMake3'
        commands=[['/usr/bin/cmake','-S',str(out/'source'),'-B',str(out/'build-host'),'-G','Ninja',
            '-DCMAKE_TOOLCHAIN_FILE='+str(out/'toolchain-host.cmake'),'-DCMAKE_BUILD_TYPE=RelWithDebInfo',
            '-DSC_ARCH_NAME=x64','-DPYTHON_EXECUTABLE=/usr/bin/python3','-DSPIRV_CROSS_ENABLE_TESTS=OFF'],
            ['ninja','-C',str(out/'build-host'),'-j2','dxcompiler']]
        for i,command in enumerate(commands):
            with (out/f'recipe-{i}.log').open('w') as log:subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT)
    m=record(engine,out);print(json.dumps(dict(candidate_sha256=m['candidate_sha256'],source_files=len(m['source_files']))))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--engine',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    g=p.add_mutually_exclusive_group();g.add_argument('--install',action='store_true');g.add_argument('--restore',action='store_true');g.add_argument('--record',action='store_true')
    main(p.parse_args())

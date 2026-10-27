#!/usr/bin/env python3
"""Build a read-only NoDrive observer from pinned external UE sources.

Engine sources and static archives stay untouched. --install atomically replaces
only the PhysXVehicles module, preserving its original binary for --restore.
Stop every UE process before install/restore. Generated source stays outside git.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def once(s, before, after):
    if s.count(before) != 1:
        raise RuntimeError('nonunique solver anchor: '+before[:80])
    return s.replace(before, after, 1)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--engine', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--install', action='store_true')
    p.add_argument('--restore', action='store_true')
    a = p.parse_args()
    root, out = a.engine.resolve(), a.output.resolve()
    own = Path(__file__).resolve().parent
    engine = root/'Engine'
    px = engine/'Source/ThirdParty/PhysX3'
    source = px/'PhysX_3.4/Source/PhysXVehicle/src/PxVehicleUpdate.cpp'
    archive = px/'Lib/Linux/x86_64-unknown-linux-gnu/libPhysX3VehiclePROFILE.a'
    module = engine/'Plugins/Runtime/PhysXVehicles/Binaries/Linux/libUE4Editor-PhysXVehicles.so'
    backup = out/'original-libUE4Editor-PhysXVehicles.so'
    if a.install or a.restore:
        # No replacement underneath a live simulator/editor, including other tasks.
        if subprocess.run(['pgrep', '-x', 'UE4Editor'], stdout=subprocess.DEVNULL).returncode == 0:
            raise RuntimeError('UE4Editor is running')
    if a.restore:
        manifest = json.loads((out/'manifest.json').read_text())
        if digest(module) != manifest['instrumented_module_sha256'] or digest(backup) != manifest['original_module_sha256']:
            raise RuntimeError('unrecognized module/backup; refusing restore')
        shutil.copy2(backup, str(module)+'.m7-new')
        Path(str(module)+'.m7-new').replace(module)
        return
    if subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'], text=True).strip() != 'e9d9e60c85f643e10eeb03f42f61554d18dcb30f':
        raise RuntimeError('engine pin')
    subprocess.run(['git','-C',str(root),'diff','--exit-code','HEAD','--',
                    'Engine/Source/ThirdParty/PhysX3','Engine/Plugins/Runtime/PhysXVehicles/Source'],check=True)
    if digest(source) != 'face50bc0460ded43facdbea8e858e8478119d8abadd73e49c1188698631181c' or digest(archive) != '9989a1cf00dab7bc0f5a1ca50cc898cf51c0ce5c6a9427f5e1a95568e0a18aa1':
        raise RuntimeError('solver source/archive pin')
    out.mkdir(parents=True, exist_ok=True)
    s = source.read_text()
    begin = s.index('void PxVehicleUpdate::updateNoDrive\n')
    end = s.index('\n}\n', begin)+2
    body = s[begin:end]
    body = once(body, '\n\tPX_SIMD_GUARD;', '\n\tm7_begin(vehNoDrive, vehNoDrive->mWheelsSimData.getNbWheels(), timestep);\n\tPX_SIMD_GUARD;')
    body = once(body, '\t\t\t\treturn;', '\t\t\t\tm7_end(vehNoDrive, true);\n\t\t\t\treturn;')
    body = once(body, '\t\t\tintegrateNoDriveWheelSpeeds(', '\t\t\tfloat m7_before[4];\n\t\t\tfor (unsigned j=0;j<4;++j) m7_before[j]=wheels4DynData.mWheelSpeeds[j];\n\t\t\tintegrateNoDriveWheelSpeeds(')
    body = once(body, '\n\t\t\tintegrateNoDriveWheelRotationAngles(', '\n\t\t\tm7_step(vehNoDrive, k, numSubSteps, i, subTimestep, m7_before, wheels4DynData.mWheelSpeeds, rawDriveTorques, brakeTorques, outputData.tireTorques, wheelDampingRates);\n\n\t\t\tintegrateNoDriveWheelRotationAngles(')
    body = body[:-1]+'\tm7_end(vehNoDrive, false);\n}'
    generated = out/'PxVehicleUpdate.cpp'
    generated.write_text('#include "solver_observer.inc"\n'+s[:begin]+body+s[end:])
    for name in ('solver_observer.inc','M7SolverTrace.h'):
        shutil.copy2(own/name, out/name)
    sdk = engine/'Extras/ThirdPartyNotUE/SDKs/HostLinux/Linux_x64/v17_clang-10.0.1-centos7/x86_64-unknown-linux-gnu'
    includes = [px/'PxShared/include',px/'PxShared/src/foundation/include',px/'PxShared/src/pvd/include']
    base = px/'PhysX_3.4'
    includes += [base/d for d in ('Include','Include/vehicle','Include/common','Include/geometry','Include/extensions','Include/pvd','Source/Common/include','Source/Common/src','Source/PhysXVehicle/src','Source/PhysXMetaData/extensions/include','Source/PhysXMetaData/core/include','Source/PhysXVehicle/src/PhysXMetaData/include','Source/PhysXExtensions/src/serialization/Xml','Source/PvdSDK/src')]
    obj = out/'PxVehicleUpdate.cpp.o'
    command = [str(sdk/'bin/clang++'), '-c','-O3','-fPIC','-fno-exceptions','-fno-rtti','-fno-strict-aliasing','-msse2','-std=c++14','-DPX_PHYSX_STATIC_LIB','-DNDEBUG','-DPX_PROFILE=1','-DPX_SUPPORT_PVD=1','-target','x86_64-unknown-linux-gnu','--sysroot='+str(sdk),'-nostdinc++','-I'+str(engine/'Source/ThirdParty/Linux/LibCxx/include/c++/v1')]
    command += ['-I'+str(d) for d in includes]+[str(generated),'-o',str(obj)]
    subprocess.run(command, check=True)
    local_archive = out/archive.name
    shutil.copy2(archive, local_archive)
    subprocess.run(['ar','r',str(local_archive),str(obj)],check=True)
    linkfile = engine/'Intermediate/Build/Linux/B4D820EA/UE4Editor/Development/Link-libUE4Editor-PhysXVehicles.so.link.sh'
    link = shlex.split(next(line for line in linkfile.read_text().splitlines() if ' -shared ' in line))
    response_arg = next(arg for arg in link if arg.startswith('-Wl,@'))
    original_response = Path(response_arg[5:])
    response = out/'module.response'
    response.write_text(once(original_response.read_text(),str(archive),str(local_archive)))
    binary = out/module.name
    link[link.index('-o')+1] = str(binary)
    link[link.index(response_arg)] = '-Wl,@'+str(response)
    subprocess.run(link,cwd=engine/'Source',check=True)
    if not backup.exists():
        shutil.copy2(module,backup)
    elif module.read_bytes() != backup.read_bytes():
        old = json.loads((out/'manifest.json').read_text())
        if digest(module) != old['instrumented_module_sha256']:
            raise RuntimeError('unknown installed module')
    manifest = dict(source_sha256=digest(source),archive_sha256=digest(archive),
        generated_source_sha256=digest(generated),compile_command=command,link_command=link,
        observer_sha256=digest(own/'solver_observer.inc'),abi_sha256=digest(own/'M7SolverTrace.h'),
        original_module_sha256=digest(backup),instrumented_module_sha256=digest(binary))
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    if a.install:
        if subprocess.run(['pgrep','-x','UE4Editor'],stdout=subprocess.DEVNULL).returncode == 0:
            raise RuntimeError('UE4Editor started during build; no module replacement')
        shutil.copy2(binary,str(module)+'.m7-new')
        Path(str(module)+'.m7-new').replace(module)
    print(json.dumps(dict(status='built', installed=a.install, module_sha256=digest(binary))))


if __name__ == '__main__':
    main()

"""Isolated bounded-evidence CARLA module build; atomic install/exact restore."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def stopped():
    if subprocess.run(['pgrep','-x','UE4Editor'],stdout=subprocess.DEVNULL).returncode==0:
        raise RuntimeError('cannot replace a live engine module')


def main(a):
    root=Path(__file__).resolve().parents[3];own=Path(__file__).resolve().parent
    engine=a.engine.resolve()/'Engine';plugin=a.source.resolve()/'Unreal/CarlaUE4/Plugins/Carla'
    installed=plugin/'Binaries/Linux/libUE4Editor-Carla.so';out=a.output.resolve()
    baseline=json.loads((root/'profiles/perception-source-compare-server-v2.json').read_text())['baseline_module_sha256']
    if a.install or a.restore:
        stopped();m=json.loads((out/'manifest.json').read_text())
        assert sha(installed)==(m['module_sha256'] if a.restore else baseline)
        replacement=out/('original.so' if a.restore else 'libUE4Editor-Carla.so')
        assert sha(replacement)==(baseline if a.restore else m['module_sha256'])
        temp=Path(str(installed)+'.endurance-new');shutil.copy2(replacement,temp);stopped();temp.replace(installed)
        print(json.dumps(dict(installed=not a.restore,restored=a.restore,sha256=sha(installed))));return
    assert sha(installed)==baseline
    out.mkdir(parents=True,exist_ok=False);shutil.copy2(installed,out/'original.so')
    external=plugin/'Source/Carla/M7NoDrive'
    # Original other headers retain their canonical paths, avoiding duplicate UE types.
    port=(own/'M7NoDrivePort.cpp').read_text()
    for name in ('M7NoDrivePort.h','M7NoDriveMovement.h','M7NoDriveModelConstants.h'):
        port=port.replace('"'+name+'"','"'+str(external/name)+'"')
    (out/'M7NoDrivePort.cpp').write_text(port)
    (out/'solver_journal.hpp').write_text((own/'solver_journal.hpp').read_text())
    intermediate=plugin/'Intermediate/Build/Linux/B4D820EA/UE4Editor/Development/Carla'
    unity=intermediate/'Module.Carla.2_of_4.cpp';original=external/'M7NoDrivePort.cpp'
    membership=own/'endurance_unity_v1.json'
    text=''.join('#include "'+str(plugin/'Source'/name)+'"\n' for name in json.loads(membership.read_text())['sources'])
    assert text.count(str(original))==1
    local=out/unity.name;local.write_text(text.replace(str(original),str(out/'M7NoDrivePort.cpp')))
    rsp=Path(str(unity)+'.o.rsp');args=shlex.split(rsp.read_text());obj=out/(unity.name+'.o')
    args[args.index('-o')+1]=str(obj);args[args.index(str(unity))]=str(local)
    args=[('-MF'+str(out/'module.d')) if x.startswith('-MF') else x for x in args]
    args+=['-I'+str(external)]
    pch=next(i for i,x in enumerate(args) if x.endswith('/SharedPCH.UnrealEd.Cpp17.h'))
    assert args[pch-1]=='-include'
    del args[pch-1:pch+1]
    # Cleanup removed generated PCH files. Compile the pinned public header after
    # the complete retained module definitions; no guessed generated definitions.
    shared_header=engine/'Source/Editor/UnrealEd/Public/UnrealEdSharedPCH.h'
    args+=['-include',str(shared_header)]
    compiler=engine/'Extras/ThirdPartyNotUE/SDKs/HostLinux/Linux_x64/v17_clang-10.0.1-centos7/x86_64-unknown-linux-gnu/bin/clang++'
    commands=[[str(compiler),*args]]
    recipe_path=root/'docs/test-plan/evidence/m10_readback_v1/build/manifest.json'
    recipe=json.loads(recipe_path.read_text());link=list(recipe['link_command'])
    response=recipe_path.parent/'module.response'
    assert sha(response)==recipe['generated']['module.response']
    reference=next(x for x in link if x.startswith('-Wl,@'));text=response.read_text()
    camera_object=next(x for x in shlex.split(text) if 'Module.Carla.3_of_4.cpp.o' in x)
    baseline_camera=intermediate/'Module.Carla.3_of_4.cpp.o'
    text=text.replace(camera_object,str(baseline_camera))
    for path in shlex.split(text):
        if path.endswith('.o'):assert sha(path)==recipe['inputs'][path], 'baseline object changed: '+path
    assert text.count(str(unity)+'.o')==1
    local_response=out/'module.response';local_response.write_text(text.replace(str(unity)+'.o',str(obj)))
    link[link.index(reference)]='-Wl,@'+str(local_response);link[link.index('-o')+1]=str(out/installed.name)
    commands += [link,['strip','--strip-debug',str(out/installed.name)]]
    for i,command in enumerate(commands):
        with (out/f'build-{i}.log').open('w') as log:
            subprocess.run(command,cwd=engine/'Source',stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
    inputs={own/'build_endurance.py',own/'M7NoDrivePort.cpp',own/'solver_journal.hpp',membership,rsp,recipe_path,response,compiler,baseline_camera,shared_header,intermediate/'Definitions.Carla.h'}
    inputs.update(plugin/'Source'/name for name in json.loads(membership.read_text())['sources'])
    inputs.update(p for p in external.iterdir() if p.is_file())
    inputs.update(Path(x) for x in shlex.split(response.read_text()) if Path(x).is_file())
    manifest=dict(schema='m10-endurance-build-v1',module_path=str(installed),original_sha256=baseline,
        module_sha256=sha(out/installed.name),commands=commands,
        inputs={str(p):sha(p) for p in sorted(inputs)},
        generated={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.suffix not in ('.log','.d')})
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'module_sha256':manifest['module_sha256']}))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('engine','source','output'):p.add_argument('--'+name,type=Path,required=True)
    g=p.add_mutually_exclusive_group();g.add_argument('--install',action='store_true');g.add_argument('--restore',action='store_true')
    main(p.parse_args())

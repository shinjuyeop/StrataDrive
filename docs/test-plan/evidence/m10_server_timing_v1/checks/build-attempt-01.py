#!/usr/bin/env python3
"""Rebuild only two pinned unity objects, then opt-in install/exact restore."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess

PINS = dict(launch='c1867a5dff23194ad3fb3009d2441ca2953392e070bdce39597392a7938afd05',
            carla='6ca374f484afcfc099235c8ed68bc6ed6ea8268d6e37c20f0ccd2688bc792eaa',
            executable='dacb6a821b92768a4ce38e3f2188e11b16e2e6f41d39ab7988f0c2ea831054f8',
            module='099f15274e768049c774166b17eb55838e672f9098f7d9e9f89aeddab6f81134')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''): h.update(block)
    return h.hexdigest()


def once(text, old, new):
    if text.count(old) != 1: raise ValueError('nonunique anchor: ' + old[:120])
    return text.replace(old, new, 1)


def helper(component):
    return '''
#include "timing.hpp"
namespace {
strata_server_timing::Journal<>& StrataTimingJournal() {
  static strata_server_timing::Journal<> J("COMPONENT", FParse::Param(FCommandLine::Get(), TEXT("StrataM10ServerTiming")));
  return J;
}
}
'''.replace('COMPONENT', component)


def scoped(text, original, stage, frame='CurrentFrameCounter'):
    return once(text, original, '{ strata_server_timing::Scope StrataScope(StrataTimingJournal(), "'+stage+'", '+frame+'); '+original+' }')


def patch_launch(text):
    text = once(text, 'void FEngineLoop::Tick()\n{', helper('launch') + '\nvoid FEngineLoop::Tick()\n{\n\tstrata_server_timing::Scope StrataTick(StrataTimingJournal(), "engine_tick", GFrameCounter);')
    for anchor, stage in (
        ('GEngine->UpdateTimeAndHandleMaxTickRate();', 'tick_rate'),
        ('GEngine->Tick(FApp::GetDeltaTime(), bIdleMode);', 'game_tick'),
        ('RHITick( FApp::GetDeltaTime() );', 'rhi_tick'),
        ('FrameEndSync.Sync( CVarAllowOneFrameThreadLag->GetValueOnGameThread() != 0 );', 'frame_sync'),
        ('FTicker::GetCoreTicker().Tick(FApp::GetDeltaTime());', 'core_ticker'),
        ('GEngine->TickDeferredCommands();', 'deferred_commands')):
        text = scoped(text, anchor, stage)
    return text


def patch_carla(text):
    helpers = helper('carla') + '''
namespace {
bool StrataTimedPump(UCarlaEpisode& Episode) {
  auto& J=StrataTimingJournal();
  if(!J.enabled())return M7NoDrive::PumpWall(Episode);
  static uint64 LastEnd=0;
  const uint64 Begin=strata_server_timing::clock_ns(CLOCK_MONOTONIC);
  const uint64 Frame=FCarlaEngine::GetFrameCounter()+1;
  if(LastEnd && Begin-LastEnd>=500000)J.record({"pump_gap",Frame,LastEnd,Begin,0,0});
  const bool Result=M7NoDrive::PumpWall(Episode);
  const uint64 End=strata_server_timing::clock_ns(CLOCK_MONOTONIC);
  if(Result || End-Begin>=500000)J.record({"pump_call",Frame,Begin,End,0,0});
  LastEnd=End;return Result;
}
}
'''
    anchor = 'void FCarlaEngine::OnPreTick(UWorld *World, ELevelTick TickType, float DeltaSeconds)\n{'
    text = once(text, anchor, helpers+'\n'+anchor+'\n  strata_server_timing::Scope StrataPre(StrataTimingJournal(), "pre_tick", GetFrameCounter()+1);')
    text = once(text, 'CurrentEpisode && M7NoDrive::PumpWall(*CurrentEpisode)', 'CurrentEpisode && StrataTimedPump(*CurrentEpisode)')
    anchor = 'void FCarlaEngine::OnPostTick(UWorld *World, ELevelTick TickType, float DeltaSeconds)\n{'
    text = once(text, anchor, anchor+'\n  strata_server_timing::Scope StrataPost(StrataTimingJournal(), "post_tick", GetFrameCounter());')
    for anchor, stage in (
        ('M7NoDrive::AfterTick(*CurrentEpisode, GetFrameCounter(), DeltaSeconds);', 'after_physics'),
        ('WorldObserver.BroadcastTick(*CurrentEpisode, DeltaSeconds, bMapChanged, LightUpdatePending);', 'world_snapshot'),
        ('CurrentEpisode->GetSensorManager().PostPhysTick(World, TickType, DeltaSeconds);', 'sensor_dispatch')):
        text = scoped(text, anchor, stage, 'GetFrameCounter()')
    return text


def stopped():
    if subprocess.run(['pgrep', '-x', 'UE4Editor'], stdout=subprocess.DEVNULL).returncode == 0:
        raise RuntimeError('UE4Editor is running')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','engine','readback','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--install',action='store_true');p.add_argument('--restore',action='store_true');a=p.parse_args()
    if a.install and a.restore:p.error('choose install or restore')
    source=a.source.resolve();engine=a.engine.resolve()/'Engine';out=a.output.resolve();readback=a.readback.resolve()
    plugin=source/'Unreal/CarlaUE4/Plugins/Carla';own=Path(__file__).resolve().parent
    paths=dict(executable=engine/'Binaries/Linux/UE4Editor',module=plugin/'Binaries/Linux/libUE4Editor-Carla.so')
    if a.install or a.restore:
        stopped();manifest=json.loads((out/'manifest.json').read_text())
        for name,path in paths.items():
            item=manifest['installed'][name]
            assert str(path)==item['path'] and sha(out/item['backup'])==PINS[name] and sha(out/item['binary'])==item['instrumented_sha256']
            assert sha(path)==(item['instrumented_sha256'] if a.restore else PINS[name]), 'installed identity'
        for name,path in paths.items():
            item=manifest['installed'][name];temp=Path(str(path)+'.m10-timing-new')
            shutil.copy2(out/item['backup' if a.restore else 'binary'],temp);stopped();temp.replace(path)
        print(json.dumps(dict(restored=a.restore,installed=a.install,files={str(p):sha(p) for p in paths.values()})));return
    assert not out.exists(), 'fresh output required'
    assert all(sha(path)==PINS[name] for name,path in paths.items()), 'baseline executable/module'
    rb=json.loads((readback/'manifest.json').read_text())
    assert sha(readback/'manifest.json')=='fb1ad10a33a46e4688d628533cfab2c24173e2b0e49f3317447579092d5f3178'
    for name,digest in rb['generated'].items():assert sha(readback/name)==digest
    out.mkdir(parents=True);shutil.copy2(own/'timing.hpp',out/'timing.hpp')
    installed={}
    for name,path in paths.items():
        backup='original-'+path.name;shutil.copy2(path,out/backup)
        installed[name]=dict(path=str(path),backup=backup,binary=path.name,original_sha256=PINS[name])
    compiler=engine/'Extras/ThirdPartyNotUE/SDKs/HostLinux/Linux_x64/v17_clang-10.0.1-centos7/x86_64-unknown-linux-gnu/bin/clang++'
    intermediate=engine/'Intermediate/Build/Linux/B4D820EA/UE4Editor/Development'
    carla_intermediate=plugin/'Intermediate/Build/Linux/B4D820EA/UE4Editor/Development/Carla'
    inputs={own/'build.py',own/'timing.hpp',compiler,readback/'manifest.json'};commands=[]
    def run(label,command):
        commands.append(command)
        with (out/(label+'.log')).open('w') as log:
            subprocess.run(command,cwd=engine/'Source',stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
    # Recompile the previously pinned camera variant; do not trust an unmanifested object.
    for name in ('SceneCaptureCamera.cpp','Module.Carla.3_of_4.cpp','readback.inc'):
        (out/name).write_text((readback/name).read_text().replace(str(readback),str(out)))
    run('readback-compile',[arg.replace(str(readback),str(out)) for arg in rb['compile_command']])
    inputs.update(Path(p) for p in rb['inputs'])
    for path,digest in rb['inputs'].items():assert sha(path)==digest, 'readback build input changed: '+path
    jobs=(('launch',engine/'Source/Runtime/Launch/Private/LaunchEngineLoop.cpp',intermediate/'Launch/Module.Launch.cpp',patch_launch,'executable'),
          ('carla',plugin/'Source/Carla/Game/CarlaEngine.cpp',carla_intermediate/'Module.Carla.1_of_4.cpp',patch_carla,'module'))
    for name,original,unity,patch,target in jobs:
        assert sha(original)==PINS[name], 'source pin'
        generated=out/original.name;generated.write_text(patch(original.read_text()))
        local=out/unity.name;local.write_text(once(unity.read_text(),str(original),str(generated)))
        rsp=Path(str(unity)+'.o.rsp');args=shlex.split(rsp.read_text());obj=out/(unity.name+'.o')
        args[args.index('-o')+1]=str(obj);args[args.index(str(unity))]=str(local)
        args=[('-MF'+str(out/(name+'.d'))) if x.startswith('-MF') else x for x in args]
        run(name+'-compile',[str(compiler),*args]);inputs.update((original,unity,rsp))
        inputs.update(Path(x) for x in re.findall(r'#include "([^"]+)"',unity.read_text()))
        linkfile=intermediate/('Link-'+('UE4Editor' if target=='executable' else 'libUE4Editor-Carla.so')+'.link.sh')
        link=shlex.split(next(x for x in linkfile.read_text().splitlines() if ' -o ' in x))
        ref=next(x for x in link if x.startswith('-Wl,@'));response=Path(ref[5:]);text=once(response.read_text(),str(unity)+'.o',str(obj))
        if target=='module':
            previous=carla_intermediate/'Module.Carla.3_of_4.cpp.o'
            replacement=out/previous.name
            text=once(text,str(previous),str(replacement))
        local_response=out/(name+'.response');local_response.write_text(text)
        link[link.index(ref)]='-Wl,@'+str(local_response);link[link.index('-o')+1]=str(out/paths[target].name)
        run(name+'-link',link);run(name+'-strip',['strip','--strip-debug',str(out/paths[target].name)])
        inputs.update((linkfile,response));inputs.update(Path(x) for x in shlex.split(response.read_text()) if Path(x).is_file())
        installed[target]['instrumented_sha256']=sha(out/paths[target].name)
    manifest=dict(schema='m10-server-timing-build-v1',installed=installed,commands=commands,
                  inputs={str(p):sha(p) for p in sorted(inputs)},
                  generated={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.suffix not in ('.log','.d')})
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(installed,indent=2))


if __name__=='__main__':main()

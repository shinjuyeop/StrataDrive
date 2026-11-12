#!/usr/bin/env python3
"""Pinned Engine/RenderCore timing overlay; reuse the verified outer timing build."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('outer_timing',ROOT/'tools/carla/m10_server_timing_v1/build.py')
outer=importlib.util.module_from_spec(spec);spec.loader.exec_module(outer)
once=outer.once;sha=outer.sha
PINS=dict(engine_source='dc6b205842925c78c3465fdef62624bdb415dc7bf39059d1daaafe46a26dec72',
          rendercore_source='6e00c43cffcf283050a631a1b5f98ffdc67a1a389e0961e8f65e28f797bc93a0',
          engine='9362962edd68c32cc2981858e4dd0b1d5fc5a81e9c5b2b4d5b6cbc19fa22ff48',
          rendercore='26f7ed9863dcc9e08a8a556a656533c955a701dc688fcca136c6b1af581f915b',**outer.PINS)


def patch_engine(text):
    anchor='void FFrameEndSync::Sync( bool bAllowOneFrameThreadLag )\n{'
    helper=outer.helper('engine_fence')+'''
extern "C" RENDERCORE_API bool StrataSetFrameFenceTiming(bool Active);
namespace {
struct StrataFenceSelection {
  bool Previous;
  StrataFenceSelection():Previous(StrataSetFrameFenceTiming(StrataTimingJournal().enabled())) {}
  ~StrataFenceSelection(){StrataSetFrameFenceTiming(Previous);}
};
}
'''
    text=once(text,anchor,helper+'\n'+anchor+'\n\tStrataFenceSelection StrataSelection;\n\tstrata_server_timing::Scope StrataTotal(StrataTimingJournal(), "sync_inner", GFrameCounter);')
    begin=text.index(anchor);end=text.index('\nFString appGetStartupMap(',begin);part=text[begin:end]
    for expression,stage in (('Fence[EventIndex].BeginFence(true);','begin_fence'),
                             ('ProcessAsyncLoading(true, false, TimeLimit);','async_loading'),
                             ('Fence[EventIndex].Wait(bEmptyGameThreadTasks);','fence_wait')):
        part=outer.scoped(part,expression,stage,'GFrameCounter')
    expression='FTaskGraphInterface::Get().ProcessThreadUntilIdle(ENamedThreads::GameThread);'
    assert part.count(expression)==2
    part=part.replace(expression,'{ strata_server_timing::Scope StrataTasks(StrataTimingJournal(), "sync_game_tasks", GFrameCounter); '+expression+' }')
    return text[:begin]+part+text[end:]


def patch_rendercore(text):
    helper=outer.helper('render_fence')+'''
namespace {
thread_local bool StrataFenceActive=false;
struct StrataOptionalScope {
  strata_server_timing::Row Row{};
  bool Active=StrataFenceActive;
  StrataOptionalScope(const char* Stage) {
    if(Active)Row={Stage,GFrameCounter,strata_server_timing::clock_ns(CLOCK_MONOTONIC),0,strata_server_timing::clock_ns(CLOCK_THREAD_CPUTIME_ID),0};
  }
  ~StrataOptionalScope() {
    if(!Active)return;
    Row.cpu_end=strata_server_timing::clock_ns(CLOCK_THREAD_CPUTIME_ID);
    Row.end=strata_server_timing::clock_ns(CLOCK_MONOTONIC);StrataTimingJournal().record(Row);
  }
};
}
extern "C" RENDERCORE_API bool StrataSetFrameFenceTiming(bool Active) {
  const bool Previous=StrataFenceActive;StrataFenceActive=Active;return Previous;
}
'''
    anchor='void FRenderCommandFence::BeginFence(bool bSyncToRHIAndGPU)\n{'
    text=once(text,anchor,helper+'\n'+anchor+'\n\tStrataOptionalScope StrataBegin("render_begin_fence");')
    text=once(text,'// Sync Game Thread with Render Thread only','StrataOptionalScope StrataRoute("route_render_only");\n\t\t\t// Sync Game Thread with Render Thread only')
    text=once(text,'// Create a task graph event which we can pass to the render or RHI threads.',
              'StrataOptionalScope StrataRoute(GTSyncType==1?"route_rhi":"route_gpu");\n\t\t\t// Create a task graph event which we can pass to the render or RHI threads.')
    anchor='void FRenderCommandFence::Wait(bool bProcessGameThreadTasks) const\n{'
    text=once(text,anchor,anchor+'\n\tStrataOptionalScope StrataWait("render_fence_wait");')
    anchor='static void GameThreadWaitForTask(const FGraphEventRef& Task, ENamedThreads::Type TriggerThreadIndex = ENamedThreads::ActualRenderingThread, bool bEmptyGameThreadTasks = false)\n{'
    text=once(text,anchor,anchor+'\n\tStrataOptionalScope StrataTask(TriggerThreadIndex==ENamedThreads::RHIThread?"task_wait_rhi":"task_wait_render");')
    text=once(text,'bDone = Event->Wait(WaitTime);','{ StrataOptionalScope StrataEvent("event_wait"); bDone = Event->Wait(WaitTime); }')
    begin=text.index(anchor);end=text.index('\n/**\n * Waits for pending fence commands',begin);part=text[begin:end]
    expression='FTaskGraphInterface::Get().ProcessThreadUntilIdle(ENamedThreads::GameThread);'
    part=once(part,expression,'{ StrataOptionalScope StrataTasks("wait_game_tasks"); '+expression+' }')
    return text[:begin]+part+text[end:]


def main():
    p=argparse.ArgumentParser()
    for n in ('engine','source','outer','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--install',action='store_true');p.add_argument('--restore',action='store_true');a=p.parse_args()
    if a.install and a.restore:p.error('choose install or restore')
    engine=a.engine.resolve()/'Engine';source=a.source.resolve();out=a.output.resolve();prior=a.outer.resolve()
    paths=dict(executable=engine/'Binaries/Linux/UE4Editor',module=source/'Unreal/CarlaUE4/Plugins/Carla/Binaries/Linux/libUE4Editor-Carla.so',
               engine=engine/'Binaries/Linux/libUE4Editor-Engine.so',rendercore=engine/'Binaries/Linux/libUE4Editor-RenderCore.so')
    if a.install or a.restore:
        outer.stopped();m=json.loads((out/'manifest.json').read_text())
        for name,path in paths.items():
            item=m['installed'][name];assert str(path)==item['path']
            assert sha(out/item['backup'])==PINS[name] and sha(out/item['binary'])==item['instrumented_sha256']
            assert sha(path) in ((PINS[name],item['instrumented_sha256']) if a.restore else (PINS[name],))
        for name,path in paths.items():
            item=m['installed'][name];temp=Path(str(path)+'.m10-fence-new');shutil.copy2(out/item['backup' if a.restore else 'binary'],temp);outer.stopped();temp.replace(path)
        print(json.dumps(dict(restored=a.restore,installed=a.install,files={str(p):sha(p) for p in paths.values()})));return
    assert not out.exists() and all(sha(path)==PINS[name] for name,path in paths.items())
    previous=json.loads((prior/'manifest.json').read_text())
    assert sha(prior/'manifest.json')==sha(ROOT/'docs/test-plan/evidence/m10_server_timing_v1/build-02/manifest.json')
    for name,digest in previous['generated'].items():assert sha(prior/name)==digest
    out.mkdir(parents=True);shutil.copy2(ROOT/'tools/carla/m10_server_timing_v1/timing.hpp',out/'timing.hpp')
    installed={}
    for name,path in paths.items():
        backup='original-'+path.name;shutil.copy2(path,out/backup)
        installed[name]=dict(path=str(path),backup=backup,binary=path.name,original_sha256=PINS[name])
    for name in ('executable','module'):
        shutil.copy2(prior/previous['installed'][name]['binary'],out/paths[name].name)
        installed[name]['instrumented_sha256']=sha(out/paths[name].name)
    compiler=engine/'Extras/ThirdPartyNotUE/SDKs/HostLinux/Linux_x64/v17_clang-10.0.1-centos7/x86_64-unknown-linux-gnu/bin/clang++'
    intermediate=engine/'Intermediate/Build/Linux/B4D820EA/UE4Editor/Development'
    commands=[];inputs={Path(__file__).resolve(),ROOT/'tools/carla/m10_server_timing_v1/build.py',ROOT/'tools/carla/m10_server_timing_v1/timing.hpp',prior/'manifest.json',compiler}
    def run(label,cmd):
        commands.append(cmd)
        with (out/(label+'.log')).open('w') as log:subprocess.run(cmd,cwd=engine/'Source',stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
    jobs=(('rendercore','RenderCore','RenderingThread.cpp','1_of_3',patch_rendercore),('engine','Engine','UnrealEngine.cpp','44_of_47',patch_engine))
    for name,mod,file,number,patch in jobs:
        original=engine/'Source/Runtime'/mod/'Private'/file;assert sha(original)==PINS[name+'_source']
        generated=out/file;generated.write_text(patch(original.read_text()))
        unity=intermediate/mod/('Module.'+mod+'.'+number+'.cpp');local=out/unity.name
        local.write_text(once(unity.read_text(),str(original),str(generated)))
        rsp=Path(str(unity)+'.o.rsp');args=shlex.split(rsp.read_text());obj=out/(unity.name+'.o')
        args[args.index('-o')+1]=str(obj);args[args.index(str(unity))]=str(local)
        args=[('-MF'+str(out/(name+'.d'))) if x.startswith('-MF') else x for x in args]
        run(name+'-compile',[str(compiler),*args])
        linkfile=intermediate/('Link-libUE4Editor-'+mod+'.so.link.sh');link=outer.link_command(linkfile.read_text())
        ref=next(x for x in link if x.startswith('-Wl,@'));response=Path(ref[5:]);local_response=out/(name+'.response')
        local_response.write_text(once(response.read_text(),str(unity)+'.o',str(obj)))
        link[link.index(ref)]='-Wl,@'+str(local_response);link[link.index('-o')+1]=str(out/paths[name].name)
        # Strip debug while linking, avoiding a multi-GB transient engine library.
        link.append('-Wl,--strip-debug');run(name+'-link',link)
        installed[name]['instrumented_sha256']=sha(out/paths[name].name)
        inputs.update((original,unity,rsp,linkfile,response));inputs.update(Path(x) for x in re.findall(r'#include "([^"]+)"',unity.read_text()))
        inputs.update(Path(x) for x in shlex.split(response.read_text()) if Path(x).is_file())
    m=dict(schema='m10-fence-compare-build-v1',installed=installed,commands=commands,outer_build_sha256=sha(prior/'manifest.json'),
           inputs={str(p):sha(p) for p in sorted(inputs)},generated={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.suffix not in ('.log','.d')})
    (out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(json.dumps(installed,indent=2))


if __name__=='__main__':main()

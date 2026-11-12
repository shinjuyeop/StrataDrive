import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from audit_server_timing_v1 import parse, PREFIX, END
from run_carla_control_shadow_v1 import timing_runtime, sha

ROOT = Path(__file__).resolve().parents[3]


def logs():
    return '\n'.join(PREFIX+json.dumps(dict(component=c,stage=s,frame=1,begin=10,end=30,cpu_begin=2,cpu_end=10))+'\n'+
                     END+json.dumps(dict(component=c,rows=1,overflow=0)) for c,s in (('launch','frame_sync'),('carla','post_tick')))


class ServerTimingTests(unittest.TestCase):
    def test_complete_journals(self):
        self.assertEqual(len(parse(logs())),2)

    def test_rejects_missing_overflow_duplicate_and_reversed_time(self):
        text=logs()
        for bad in (text.splitlines()[0],text.replace('"overflow": 0','"overflow": 1'),text+'\n'+text,
                    text.replace('"end": 30','"end": 9'),text.replace('"cpu_end": 10','"cpu_end": 1'),
                    text.replace('"rows": 1','"rows": 2'),'noise'+text):
            with self.subTest(bad=bad[:50]),self.assertRaises(ValueError):parse(bad)

    def test_cpp_journal_is_bounded_and_disabled_is_silent(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory);source=path/'test.cpp';binary=path/'test'
            source.write_text('''#include "timing.hpp"
#include <cassert>
int main() {
  using namespace strata_server_timing;
  Journal<2> j("test",true);
  j.record({"a",1,10,20,1,2});j.record({"b",1,20,30,2,3});j.record({"c",1,30,40,3,4});
  assert(j.size()==2 && j.overflow()==1 && j.at(1).stage[0]=='b');j.dump();j.dump();
  Journal<> disabled("disabled",false);{ Scope s(disabled,"ignored",0); }
  assert(disabled.size()==0);return 0;
}
''')
            subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-I'+str(ROOT/'tools/carla/m10_server_timing_v1'),str(source),'-o',str(binary)],check=True,capture_output=True)
            result=subprocess.run([str(binary)],check=True,capture_output=True,text=True)
            self.assertEqual(result.stdout,'');self.assertEqual(result.stderr.count(PREFIX),2)
            self.assertEqual(result.stderr.count(END),1);self.assertNotIn('disabled',result.stderr)

    def test_patches_preserve_each_original_operation_once(self):
        spec=importlib.util.spec_from_file_location('timing_build',ROOT/'tools/carla/m10_server_timing_v1/build.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        anchors=['void FEngineLoop::Tick()\n{','GEngine->UpdateTimeAndHandleMaxTickRate();',
                 'GEngine->Tick(FApp::GetDeltaTime(), bIdleMode);','RHITick( FApp::GetDeltaTime() );',
                 'FrameEndSync.Sync( CVarAllowOneFrameThreadLag->GetValueOnGameThread() != 0 );',
                 'FTicker::GetCoreTicker().Tick(FApp::GetDeltaTime());','GEngine->TickDeferredCommands();']
        text=module.patch_launch('\n'.join(anchors))
        for anchor in anchors:self.assertEqual(text.count(anchor),1)
        with self.assertRaises(ValueError):module.patch_launch('\n'.join(anchors+anchors))
        self.assertEqual(module.link_command('set -o errexit\nclang -o binary -Wl,@response\ndump_syms -o symbols'),['clang','-o','binary','-Wl,@response'])

    def test_runtime_override_requires_frozen_manifest_and_exact_binaries(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);module='Unreal/CarlaUE4/Plugins/Carla/Binaries/Linux/libUE4Editor-Carla.so'
            paths={'module':base/module,'executable':base/'Engine/Binaries/Linux/UE4Editor'}
            for p in paths.values():p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'known')
            data=dict(schema='m10-server-timing-build-v1',installed={k:dict(path=str(p),instrumented_sha256=sha(p),original_sha256='original') for k,p in paths.items()})
            manifest=base/'manifest.json';manifest.write_text(json.dumps(data));freeze=base/'freeze.json'
            freeze.write_text(json.dumps(dict(external={str(manifest):sha(manifest)})))
            profile=dict(baseline_module_sha256='original',external_files={module:'previous','other':'unchanged'})
            result=timing_runtime(manifest,freeze,base,base,profile)
            self.assertEqual(result['other'],'unchanged');self.assertEqual(profile['external_files'][module],'previous')
            paths['module'].write_bytes(b'changed')
            with self.assertRaises(ValueError):timing_runtime(manifest,freeze,base,base,profile)
            freeze.write_text(json.dumps(dict(external={})))
            with self.assertRaises(ValueError):timing_runtime(manifest,freeze,base,base,profile)


if __name__=='__main__':unittest.main()

"""Verify unchanged plant/native behavior and bound the opt-in scheduling changes."""
import hashlib,json,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];SERIES=Path(__file__).resolve().parent
BASE=SERIES.with_name('m10_parallel_gc_v1');OWN=Path('tools/carla/m7_nodrive')
sha=lambda b:hashlib.sha256(b).hexdigest()
frozen=json.loads((BASE/'sources.json').read_text())
assert sha((BASE/'sources.tar.gz').read_bytes())==frozen['archive_sha256']
with tarfile.open(BASE/'sources.tar.gz','r:gz') as tar:
 def old(name):
  data=tar.extractfile(str(name)).read();assert sha(data)==frozen['files'][str(name)]['sha256'];return data.decode()
 unchanged=[]
 for name,item in frozen['files'].items():
  if name.startswith(('central/','interfaces/','simulation/','vecu/','zone/')):
   assert sha((ROOT/name).read_bytes())==item['sha256'],name;unchanged.append(name)
 for name in ('M7NoDriveMovement.h','M7NoDriveMovement.cpp','M7NoDriveWork.cpp','M7NoDriveEffort.cpp','M7NoDriveGeometry.cpp','solver_journal.hpp','wall_bridge.hpp','state_path_profile.hpp','owner_wait_profile.hpp'):
  assert (ROOT/OWN/name).read_text()==old(OWN/name),name
 header=(ROOT/OWN/'native_admission.hpp').read_text()
 before='constexpr Time wall_preview_reserve(bool structured) {return structured?2000000:4000000;}'
 after='constexpr Time wall_preview_reserve(bool structured,bool purge_slice=false) {\n  return structured?(purge_slice?1000000:2000000):4000000;\n}'
 assert header.count(after)==1 and header.replace(after,before)==old(OWN/'native_admission.hpp')
 port=(ROOT/OWN/'M7NoDrivePort.cpp').read_text();baseline=old(OWN/'M7NoDrivePort.cpp')
 # Actual staging/commit and physics/measurement code remain exact. The only
 # change within stage_native is selection of the declared preview slack.
 start='  if (Op == TEXT("stage_native")) {';end='std::string Request('
 def region(s,a,b):return s[s.index(a):s.index(b)]
 assert region(port,start,end).replace('wall_preview_reserve(S.StructuredState,S.PurgeSlice)','wall_preview_reserve(S.StructuredState)')==region(baseline,start,end)
 assert port[port.index('bool BeforeTick('):]==baseline[baseline.index('bool BeforeTick('):]
 assert 'IncrementalPurgeGarbage(true,float(PurgeProfile::BudgetNs)/1e9f)' in port
 assert 'CollectGarbage(' not in port
engine=Path('/d/shin/stratadrive-tools/UnrealEngine_4.26/Engine')
paths=['Source/Runtime/Engine/Private/UnrealEngine.cpp','Source/Runtime/Engine/Private/LevelTick.cpp','Source/Runtime/Engine/Classes/Engine/Engine.h','Source/Runtime/CoreUObject/Public/UObject/UObjectGlobals.h','Source/Runtime/CoreUObject/Private/UObject/GarbageCollection.cpp','Binaries/Linux/libUE4Editor-Engine.so','Binaries/Linux/libUE4Editor-CoreUObject.so']
external={str(engine/p):sha((engine/p).read_bytes()) for p in paths}
code=(engine/paths[0]).read_text();a=code.index('void UEngine::ConditionalCollectGarbage()');b=code.index('void UEngine::PerformGarbageCollectionAndCleanupActors()',a);block=code[a:b]
assert block.index('if (bFullPurgeTriggered)')<block.index('if (bShouldDelayGarbageCollect)')<block.index('else if (!IsIncrementalPurgePending()')<block.index('IncrementalPurgeGarbage(true);')
assert 'TimeLimit = 0.002' in (engine/paths[3]).read_text()
result=dict(status='PASS_UNCHANGED_COMPUTATION_AND_LAYOUT',baseline_archive_sha256=frozen['archive_sha256'],native_source_files_unchanged=len(unchanged),final_admission_body_unchanged=True,original_physics_and_sensor_clock_unchanged=True,physical_age_ns=30000000,preview_reserve_ns=1000000,legacy_structured_reserve_ns=2000000,text_reserve_ns=4000000,engine_source_and_binary_hashes=external,changes=['owner opt-in once/frame incremental purge scheduling and bounded journal','opt-in structured preview slack 2ms to 1ms'])
(SERIES/'code-equivalence.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='engine_source_and_binary_hashes'}))

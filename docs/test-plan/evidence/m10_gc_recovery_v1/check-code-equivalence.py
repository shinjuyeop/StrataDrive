"""Permit only the explicit preview option; preserve final gates and computation."""
import hashlib
import json
from pathlib import Path
import tarfile

ROOT=Path(__file__).resolve().parents[4];SERIES=Path(__file__).resolve().parent
PRIOR=SERIES.with_name('m10_gc_owner3_v1')
read=lambda p:json.loads(p.read_text())
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()
old=read(PRIOR/'sources.json');assert sha(PRIOR/'sources.tar.gz')==old['archive_sha256']
base='tools/carla/m7_nodrive/'
changed={base+'native_admission.hpp',base+'M7NoDrivePort.cpp'}
with tarfile.open(PRIOR/'sources.tar.gz','r:gz') as archive:
    originals={name:archive.extractfile(name).read().decode() for name in changed}
for name,text in originals.items():assert hashlib.sha256(text.encode()).hexdigest()==old['files'][name]['sha256']
header=(ROOT/base/'native_admission.hpp').read_text()
normalized=header.replace('bool purge_slice=false,bool recovery_preview=false','bool purge_slice=false').replace(
    '(purge_slice?(recovery_preview?300000:1000000):2000000)','(purge_slice?1000000:2000000)')
assert normalized==originals[base+'native_admission.hpp'],'only the opt-in preview helper may change'
port=(ROOT/base/'M7NoDrivePort.cpp').read_text()
normalized=port.replace('    R->SetBoolField(TEXT("recovery_preview"),S.RecoveryPreview);\n','')
normalized=normalized.replace('  bool RecoveryPreview=false;\n','').replace(',S.RecoveryPreview)',')')
normalized=normalized.replace('    S.RecoveryPreview=FParse::Param(FCommandLine::Get(),TEXT("StrataM10RecoveryPreview"));\n    if(S.RecoveryPreview && !S.PurgeSlice)\n      return Encode(Response(false,TEXT("recovery_preview_requires_purge_slice")));\n','')
assert normalized==originals[base+'M7NoDrivePort.cpp'],'only selection/readback and preview call arguments may change'
checked=[]
for name,item in old['files'].items():
    if name.startswith(('central/','interfaces/','simulation/','vecu/','zone/',base)) and name not in changed:
        assert sha(ROOT/name)==item['sha256'],name;checked.append(name)
for name in ('tests/integration/carla/m7_1g/carla_wall_owner.cpp','tests/integration/carla/m7_1g/wall_startup_replay.cpp'):
    assert sha(ROOT/name)==old['files'][name]['sha256'];checked.append(name)
engine=read(PRIOR/'code-equivalence.json')['engine_source_and_binary_hashes']
for name,expected in engine.items():assert sha(name)==expected,name
gate=header[header.index('class Admission'):]
assert gate==originals[base+'native_admission.hpp'][originals[base+'native_admission.hpp'].index('class Admission'):]
before=port[port.index('bool BeforeTick('):port.index('void AfterTick(')]
oldport=originals[base+'M7NoDrivePort.cpp']
assert before==oldport[oldport.index('bool BeforeTick('):oldport.index('void AfterTick(')]
plan=read(ROOT/'profiles/perception-endurance-host-v4.json')['cpus']
assert plan==read(PRIOR/'prepared.json')['cpu_plan']
native=ROOT/'build/m10-watch-timing-v1/native-postfix/tests/integration/carla/m7_1g/m7_carla_wall_owner'
assert sha(native)==old['external'][str(native)]
result=dict(status='PASS_UNCHANGED_FINAL_GATE_AND_EXPLICIT_PREVIEW',baseline_archive_sha256=old['archive_sha256'],
    unchanged_computation_source_files=len(checked),changed_source_files={n:dict(before=old['files'][n]['sha256'],after=sha(ROOT/n)) for n in sorted(changed)},
    final_admission_class_sha256=hashlib.sha256(gate.encode()).hexdigest(),prephysics_guard_sha256=hashlib.sha256(before.encode()).hexdigest(),
    final_admission_body_unchanged=True,original_physics_and_sensor_clock_unchanged=True,physical_age_ns=30_000_000,
    preview_reserve_before_ns=1_000_000,preview_reserve_ns=300_000,requested_purge_slice_ns=100_000,
    native_binary_sha256=sha(native),engine_source_and_binary_hashes=engine,cpu_plan=plan,
    changes=['explicit owner-only 300us extra preview option; default 1ms purge preview preserved','matching strict declaration/readback audits and staging regression'])
(SERIES/'code-equivalence.json').write_text(json.dumps(result,indent=2)+'\n')
print('Original final admission, prephysics guard, native/model code and engine unchanged; explicit preview-only delta verified.')

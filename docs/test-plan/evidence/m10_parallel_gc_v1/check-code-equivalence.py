"""Whitelist only the post-ingress clock and structured preview scheduling changes."""
import hashlib
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT/'docs/test-plan/evidence/m10_owner_gc_v2'
OWN = Path('tools/carla/m7_nodrive')
sha = lambda data: hashlib.sha256(data).hexdigest()
frozen = json.loads((BASE/'sources.json').read_text())
assert sha((BASE/'sources.tar.gz').read_bytes()) == frozen['archive_sha256']
with tarfile.open(BASE/'sources.tar.gz', 'r:gz') as tar:
    def old(name):
        data = tar.extractfile(str(name)).read()
        assert sha(data) == frozen['files'][str(name)]['sha256']
        return data.decode()
    checked = []
    for name, item in frozen['files'].items():
        if name.startswith(('central/', 'interfaces/', 'simulation/', 'vecu/', 'zone/')):
            assert sha((ROOT/name).read_bytes()) == item['sha256'], name
            checked.append(name)
    for name in ('M7NoDriveMovement.h', 'M7NoDriveMovement.cpp', 'M7NoDriveWork.cpp',
                 'M7NoDriveEffort.cpp', 'M7NoDriveGeometry.cpp', 'solver_journal.hpp',
                 'wall_bridge.hpp', 'state_path_profile.hpp', 'owner_wait_profile.hpp', 'gc_profile.hpp'):
        assert (ROOT/OWN/name).read_text() == old(OWN/name), name
    port = old(OWN/'M7NoDrivePort.cpp')
    def change(before, after, count=1):
        global port
        assert port.count(before)==count
        port = port.replace(before, after)
    change('  const uint64 Now=WallNow();\n  if(S.AwaitSettlement)', '  if(S.AwaitSettlement)')
    change('  if(Now<S.NextDue)', '  // Ingress advances the canonical receiver clock to Received. A timestamp\n'
           '  // sampled before ingest would make the preview poll backwards in time.\n'
           '  const uint64 Now=WallNow();\n  if(Now<S.NextDue)')
    change('    R->SetBoolField(TEXT("structured_state"),S.StructuredState);',
           '    R->SetBoolField(TEXT("structured_state"),S.StructuredState);\n'
           '    R->SetStringField(TEXT("wall_preview_reserve_ns"),Dec(stratadrive::m7_native::wall_preview_reserve(S.StructuredState)));')
    change('eligible(Native,AdmissionNow,Actual,&Why,4000000)',
           'eligible(Native,AdmissionNow,Actual,&Why,stratadrive::m7_native::wall_preview_reserve(S.StructuredState))')
    change('eligible(Native,Now,Actual,&Why,4000000)',
           'eligible(Native,Now,Actual,&Why,wall_preview_reserve(S.StructuredState))')
    assert port == (ROOT/OWN/'M7NoDrivePort.cpp').read_text()
    header = (ROOT/OWN/'native_admission.hpp').read_text()
    addition = ('// Extra staging slack for the read-only host preview. The final gate still\n'
                '// checks the full original physics interval, timestamps and 30ms age limits.\n'
                '// The opt-in structured path removes the JSON round trip; retain 2ms slack.\n'
                'constexpr Time wall_preview_reserve(bool structured) {return structured?2000000:4000000;}\n')
    assert header.count(addition)==1 and header.replace(addition,'')==old(OWN/'native_admission.hpp')
result = dict(status='PASS_UNCHANGED_COMPUTATION_AND_LAYOUT', baseline_archive_sha256=frozen['archive_sha256'],
              native_source_files_unchanged=len(checked), final_admission_body_unchanged=True,
              original_physics_and_sensor_clock_unchanged=True, physical_age_ns=30_000_000,
              changes=['fresh scheduling timestamp after ingress', 'structured preview extra reserve 4ms to 2ms',
                       'reserve readback'], legacy_preview_reserve_ns=4_000_000)
Path(__file__).with_name('code-equivalence.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))

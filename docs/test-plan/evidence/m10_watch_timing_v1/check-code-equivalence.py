"""Compare moved computation bodies and class layout to the frozen V3 source."""
import hashlib
import json
from pathlib import Path
import tarfile

ROOT=Path(__file__).resolve().parents[4]
BASE=ROOT/'docs/test-plan/evidence/m10_state_path_v3'
OWN=Path('tools/carla/m7_nodrive')
sha=lambda data:hashlib.sha256(data).hexdigest()
frozen=json.loads((BASE/'sources.json').read_text())
assert sha((BASE/'sources.tar.gz').read_bytes())==frozen['archive_sha256']
with tarfile.open(BASE/'sources.tar.gz','r:gz') as tar:
    def old(name):
        name=str(OWN/name);data=tar.extractfile(name).read()
        assert sha(data)==frozen['files'][name]['sha256']
        return data.decode()
    moved={}
    for file,legacy,structured,old_end,new_end in (
        ('M7NoDriveMovement.cpp','FString UM7NoDriveMovement::DescribePhysics() const',
         'TSharedPtr<FJsonObject> UM7NoDriveMovement::DescribePhysicsObject() const','  FString Result;','  return Object;'),
        ('M7NoDriveWork.cpp','FString UM7NoDriveMovement::FinishSolverWork(bool& Valid, M7SolverTrace* Saved)',
         'TSharedPtr<FJsonObject> UM7NoDriveMovement::FinishSolverWorkObject(bool& Valid, M7SolverTrace* Saved)','  FString Out;','  return R;')):
        before=old(file).split(legacy+'\n{',1)[1].rsplit(old_end,1)[0]
        after=(ROOT/OWN/file).read_text().split(structured+'\n{',1)[1].rsplit(new_end,1)[0]
        assert before==after,file
        moved[file]=dict(identical_computation_bytes=len(before.encode()),sha256=sha(before.encode()))
    header=(ROOT/OWN/'M7NoDriveMovement.h').read_text()
    header=header.replace('struct M7SolverTrace; class FJsonObject;','struct M7SolverTrace;')
    for line in ('  TSharedPtr<FJsonObject> DescribePhysicsObject() const;\n',
                 '  TSharedPtr<FJsonObject> FinishSolverWorkObject(bool& Valid, M7SolverTrace* Saved = nullptr);\n'):
        assert header.count(line)==1;header=header.replace(line,'')
    assert header==old('M7NoDriveMovement.h'),'no layout/virtual/reflection changes'
    for name in ('M7NoDriveEffort.cpp','M7NoDriveGeometry.cpp','native_admission.hpp','wall_bridge.hpp'):
        assert (ROOT/OWN/name).read_text()==old(name),name
result=dict(status='PASS_UNCHANGED_COMPUTATION_AND_LAYOUT',baseline_archive_sha256=frozen['archive_sha256'],
    moved=moved,legacy_api_preserved=True,class_layout_virtual_reflection_unchanged=True,
    scope='source-body identity; actual UE numeric roundtrip and live audits are additional requirements')
Path(__file__).with_name('code-equivalence.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))

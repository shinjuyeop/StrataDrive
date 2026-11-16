"""Verify the frozen candidate, declared later diagnostics and restored runtime."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile

ROOT=Path(__file__).resolve().parents[4]
SERIES=Path(__file__).resolve().parent
BUNDLE=SERIES/'normal-30s-01'
def read(path):return json.loads(path.read_text())
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

frozen=read(SERIES/'sources.json')
assert sha(SERIES/'sources.tar.gz')==frozen['archive_sha256']
post_live={'tests/integration/perception/profile_host_v1.py',
           'tests/integration/perception/test_profile_host_v1.py',
           'tests/integration/perception/audit_structured_state_v1.py',
           'tests/integration/perception/test_structured_state_v1.py',
           'tools/carla/m7_nodrive/structured_json.hpp','tools/carla/m7_nodrive/M7NoDrivePort.cpp'}
revisions={}
for name,item in frozen['files'].items():
    current=dict(bytes=(ROOT/name).stat().st_size,sha256=sha(ROOT/name))
    if name in post_live:
        revisions[name]=dict(live_frozen=item,current=current,
            reason='post-live scheduler observation or nonfinite parser fallback; changed-source snapshots retain each tested revision')
    else:assert current==item,name
original=read(SERIES/'pre-install.json')['files']
runtime={name:dict(path=item['path'],sha256=sha(Path(item['path']))) for name,item in original.items()}
assert all(runtime[name]['sha256']==item['sha256'] for name,item in original.items())
shared={item['path'] for item in original.values()}
external={name:sha(Path(name)) for name in frozen['external'] if name not in shared}
assert all(value==frozen['external'][name] for name,value in external.items())
case=read(BUNDLE/'disposition.json');sequence=read(SERIES/'sequence-disposition.json')
assert not case['finite_diagnostic_pass'] and case['archive']=='PASS'
assert all(sequence[n]=='NOT_RUN_STOP_ON_FIRST_FAILURE' for n in ('normal_30s_02','normal_300s_01'))
assert read(BUNDLE/'restoration.json')['status']=='PASS'
archive=read(BUNDLE/'archive-validation.json')
assert archive==dict(status='PASS',case_verdict='FAIL',source_files=1428,raw_packets=6,future_exclusion=15211)
assert read(BUNDLE/'state-path-reproduction.json')==dict(status='PASS',original_status='PASS_DIAGNOSTIC_TRACE_INTEGRITY')
assert read(BUNDLE/'structured-state-reproduction.json')==dict(status='PASS',original_status='FAIL')
assert not read(BUNDLE/'replay.json')['exact']
assert read(BUNDLE/'prefix-comparison.json')['status']=='NOT_COMPARABLE'
native=SERIES/'native-isolation-01'
declaration=read(native/'declaration.json')
assert all(sha(ROOT/name)==digest for name,digest in declaration['identities'].items())
observation=read(native/'result.json')
assert observation['status']=='RECORDED' and observation['physical_receipts']==0
assert observation['monitor_slots']['eligible']==500
assert observation['monitor_slots']['missing']==observation['monitor_slots']['late']==0
assert {(r['scheduling_policy'],r['rt_priority'],tuple(r['affinity']))
        for r in observation['monitor_identity_samples']}=={(1,18,(1,9))}
records=read(native/'records.json')
assert sha(native/records['archive'])==records['sha256']
with tarfile.open(native/records['archive'],'r:gz') as tar:
    assert set(tar.getnames())==set(records['members'])
    for name,item in records['members'].items():
        data=tar.extractfile(name).read()
        assert dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())==item
guard=SERIES/'nonfinite-guard-01';guard_freeze=read(guard/'changed-sources.json')
assert guard_freeze['parent_archive_sha256']==frozen['archive_sha256']
assert sha(guard/'changed-sources.tar.gz')==guard_freeze['archive_sha256']
with tarfile.open(guard/'changed-sources.tar.gz','r:gz') as tar:
    assert set(tar.getnames())==set(guard_freeze['files'])
    for name,item in guard_freeze['files'].items():
        data=tar.extractfile(name).read()
        assert dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())==item
        assert sha(ROOT/name)==item['sha256']
guard_result=read(guard/'result.json');guard_client=read(guard/'client.json')
guard_order=read(guard/'order-observation.json')
assert guard_order['qualification_after_final_test_log_seconds']>0
assert guard_result['status']==guard_client['status']=='PASS_BEFORE_START_ONLY'
assert all(v['restored'] for v in guard_result['runtime'].values())
assert guard_client['check']['nonfinite_cases']==3 and guard_client['check']['nonfinite_legacy_fallback']
assert guard_client['check']['finite_direct_identity'] and not guard_client['native_started']
assert guard_client['images']==0 and int(guard_client['final']['wall_frames'])==0
log=(SERIES/'python-tests-final.txt').read_text()
assert re.search(r'Ran 484 tests in [\d.]+s\s+OK\s*$',log)
processes=subprocess.check_output(['ps','-eo','comm='],text=True).splitlines()
assert not any(n.strip()=='UE4Editor' or n.strip().startswith('m7_carla_wall') for n in processes)
result=dict(status='PASS_EVIDENCE_AND_RESTORATION_ONLY',checked_utc=datetime.now(timezone.utc).isoformat(),
    physical_stability_accepted=False,structured_state_promoted=False,native_perception_accepted=False,milestone_closed=False,
    source_files=len(frozen['files']),post_live_revisions=revisions,immutable_external_files=len(external),
    runtime=runtime,python_pre_live_tests=483,python_final_tests=484,native_boundary_tests=40,
    frozen_focused_tests=67,raw_images_checked=6,future_exclusion=15211,
    nonfinite_guard_check='PASS_BEFORE_START_ONLY',guard_changed_source_files=len(guard_freeze['files']),
    guard_protocol_order_deviation=guard_order['protocol_order_deviation'],
    no_owned_servers_running=True)
(SERIES/'final-validation.json').write_text(json.dumps(result,indent=2)+'\n')
run=read(BUNDLE/'run-manifest.json');known={BUNDLE/run['archive']:run}
known.update({BUNDLE/item['archive']:item for item in read(BUNDLE/'raw-manifest.json')['archives']})
entries=[]
for path in sorted(p for p in SERIES.rglob('*') if p.is_file() and p.name!='SHA256SUMS' and '__pycache__' not in p.parts):
    if path in known:
        assert path.stat().st_size==known[path]['bytes']
        digest=known[path]['sha256'] # full raw audit and expanded-tar compaction already verified
    else:digest=sha(path)
    entries.append(f'{digest}  {path.relative_to(SERIES)}\n')
(SERIES/'SHA256SUMS').write_text(''.join(entries))
print(json.dumps(result,indent=2))

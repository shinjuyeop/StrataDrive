"""Verify original live evidence, separate diagnostic fixes and runtime restoration."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile

ROOT=Path(__file__).resolve().parents[4]
SERIES=Path(__file__).resolve().parent
def read(path):return json.loads(path.read_text())
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def identity(path):return dict(bytes=path.stat().st_size,sha256=sha(path))
def check_tar(path,members):
    with tarfile.open(path,'r:gz') as tar:
        assert set(tar.getnames())==set(members)
        for name,item in members.items():
            data=tar.extractfile(name).read()
            assert dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())==item,name

frozen=read(SERIES/'sources.json')
assert sha(SERIES/'sources.tar.gz')==frozen['archive_sha256']
check_tar(SERIES/'sources.tar.gz',frozen['files'])
post=read(SERIES/'post-live-revisions.json')
assert identity(SERIES/post['archive'])==post['archive_identity']
assert post['original_source_manifest_sha256']==sha(SERIES/'sources.json')
check_tar(SERIES/post['archive'],{name:item['corrected'] for name,item in post['changed'].items()})
for name,item in frozen['files'].items():
    expected=post['changed'][name]['corrected'] if name in post['changed'] else item
    assert identity(ROOT/name)==expected,name
for name,item in post['changed'].items():
    assert item['original']==frozen['files'].get(name)
    assert identity(ROOT/name)==item['corrected']

original=read(SERIES/'pre-install.json')['files']
runtime={name:dict(path=item['path'],sha256=sha(Path(item['path']))) for name,item in original.items()}
assert all(runtime[name]['sha256']==item['sha256'] for name,item in original.items())
shared={item['path'] for item in original.values()}
external={name:sha(Path(name)) for name in frozen['external'] if name not in shared}
assert all(value==frozen['external'][name] for name,value in external.items())

known={};cases={}
for name,passed,images,count in [('normal-30s-01',True,287,15498),('normal-30s-02',False,286,15784)]:
    bundle=SERIES/name;case=read(bundle/'disposition.json');cases[name]=case
    assert case['finite_diagnostic_pass']==passed and case['archive']=='PASS'
    assert not case['native_perception_accepted'] and not case['milestone_closed']
    assert read(bundle/'restoration.json')['status']=='PASS'
    assert read(bundle/'archive-validation.json')==dict(status='PASS',
        case_verdict='PASS_DIAGNOSTIC_CASE_ONLY' if passed else 'FAIL',
        source_files=1439,raw_packets=images,future_exclusion=count)
    assert read(bundle/'replay.json')['exact']
    assert read(bundle/'prefix-comparison.json')['status']=='PASS_MATCHED_PREFIX'
    for target in ('state-path-reproduction.json','structured-state-reproduction.json','monitor-timing-reproduction.json'):
        assert read(bundle/target)['status']=='PASS'
    assert read(bundle/'compaction-validation.json')['status']=='PASS'
    review=read(bundle/'retained-metadata.json');assert review['status']=='PASS'
    assert identity(bundle/review['archive'])=={k:review[k] for k in ('bytes','sha256')}
    with tarfile.open(bundle/review['archive'],'r:gz') as tar:
        manifest=json.loads(tar.extractfile('MANIFEST.json').read())
    check_tar(bundle/review['archive'],dict(manifest['original_members'],
        **{n:{k:v[k] for k in ('bytes','sha256')} for n,v in manifest['derived'].items()},
        **{'MANIFEST.json':dict(bytes=len((json.dumps(manifest,indent=2)+'\n').encode()),
             sha256=hashlib.sha256((json.dumps(manifest,indent=2)+'\n').encode()).hexdigest())}))
    assert 'host-native.jsonl.gz' in manifest['original_members']
    run=read(bundle/'run-manifest.json');known[bundle/run['archive']]=run
    known.update({bundle/item['archive']:item for item in read(bundle/'raw-manifest.json')['archives']})
assert read(SERIES/'sequence-disposition.json')['remaining']=={'normal-300s-01':'NOT_RUN_STOP_ON_FIRST_FAILURE'}
native=SERIES/'native-isolation-01';observation=read(native/'result.json')
assert observation['status']=='RECORDED' and not observation['native']['first_fault']
assert observation['physical_receipts']==0 and observation['monitor_slots']['eligible']==500
assert observation['monitor_slots']['missing']==observation['monitor_slots']['late']==0
assert observation['profile_integrity']['status']=='PASS_MONITOR_DIAGNOSTIC_INTEGRITY'
assert {(r['scheduling_policy'],r['rt_priority'],tuple(r['affinity']))
        for r in observation['monitor_identity_samples']}=={(1,18,(1,9))}
records=read(native/'records.json');assert identity(native/records['archive'])=={k:records[k] for k in ('bytes','sha256')}
check_tar(native/records['archive'],records['members'])
assert read(SERIES/'native-preflight.json')['status']=='PASS'
assert read(SERIES/'frozen-tests.json')['focused_tests']==70
assert re.search(r'Ran 487 tests in [\d.]+s\s+OK\s*$',(SERIES/'postfix-python-tests.txt').read_text())
native_tests={'postfix-drive-tests.txt':47,'postfix-native-tests.txt':40,
    'postfix-async_owner_test.txt':24,'postfix-m4_async_runtime_test.txt':22,
    'postfix-m4_fault_test.txt':46,'postfix-drive_energy_model_test.txt':28}
for name,count in native_tests.items():
    assert f'[  PASSED  ] {count} tests.' in (SERIES/name).read_text()
    assert '[  FAILED  ]' not in (SERIES/name).read_text()
assert read(SERIES/'interrupt-read-correction.json')['status']=='PASS'
diagnostic=read(SERIES/'held-input-analysis.json');assert diagnostic['status']=='PASS'
assert all(diagnostic['byte_exact_original_outputs'].values())
replay=read(SERIES/'postfix-replay.json');assert replay['status']=='PASS'
assert all(all(case['byte_exact_original_outputs'].values()) for case in replay['cases'])
assert replay['cases'][0]['first_drive_fault'] is None
fault=replay['cases'][1]['first_drive_fault']
assert fault['fault']==5 and fault['observed_ns']-fault['held_hv']['dependency_ns']==30349940
assert sha(ROOT/'build/m10-watch-timing-v1/native-postfix/tests/integration/carla/m7_1g/m7_wall_startup_replay')==replay['binary_sha256']
processes=subprocess.check_output(['ps','-eo','comm='],text=True).splitlines()
assert not any(n.strip()=='UE4Editor' or n.strip().startswith('m7_carla_wall') for n in processes)
storage=read(SERIES/'storage-closeout.json')
result=dict(status='PASS_EVIDENCE_AND_RESTORATION_ONLY',checked_utc=datetime.now(timezone.utc).isoformat(),
    physical_stability_accepted=False,structured_state_promoted=False,native_perception_accepted=False,milestone_closed=False,
    original_cases=cases,source_files=len(frozen['files']),post_live_revision_files=len(post['changed']),
    immutable_external_files=len(external),runtime=runtime,python_pre_live_tests=486,python_final_tests=487,
    cpp_final_tests=sum(native_tests.values()),frozen_focused_tests=70,raw_images_checked=573,future_exclusion=15784,
    original_interrupt_observer='INCOMPLETE_FIRST17_ROWS; cannot exclude unobserved IRQ activity',
    post_live_fixes='complete procfs IRQ read; immutable first Drive fault input; no new live acceptance',
    storage_saved_bytes=storage['removed_bytes']+storage['raw_compaction_saved_bytes']+storage['native_record_compaction_saved_bytes'],
    no_owned_servers_running=True)
(SERIES/'final-validation.json').write_text(json.dumps(result,indent=2)+'\n')
entries=[]
for path in sorted(p for p in SERIES.rglob('*') if p.is_file() and p.name!='SHA256SUMS' and '__pycache__' not in p.parts):
    if path in known:
        assert path.stat().st_size==known[path]['bytes']
        digest=known[path]['sha256'] # Original full raw audit and byte-exact compaction already verified.
    else:digest=sha(path)
    entries.append(f'{digest}  {path.relative_to(SERIES)}\n')
(SERIES/'SHA256SUMS').write_text(''.join(entries))
print(json.dumps(result,indent=2))

"""Preserve the original pre-native FAIL and verify only redundant extractions."""
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[4]
SERIES=Path(__file__).resolve().parent
WORK=ROOT/'build/m10-owner-wait-v1'
sys.path.insert(0,str(ROOT/'tests/integration/perception'))
from runtime_restoration_v1 import sha
def read(p):return json.loads(p.read_text())
def digest(data):return dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
def identity(p):return dict(bytes=p.stat().st_size,sha256=sha(p))
def write(p,v):
    assert not p.exists(), 'immutable closeout'
    p.write_text(json.dumps(v,indent=2)+'\n')
def add(tar,name,data):
    info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o644
    tar.addfile(info,io.BytesIO(data))
def check_tar(path,members):
    with tarfile.open(path,'r:gz') as tar:
        assert len(tar.getnames())==len(members) and set(tar.getnames())==set(members)
        for name,item in members.items():assert digest(tar.extractfile(name).read())==item,name

bundle=SERIES/'normal-30s-01';run=WORK/'normal-30s-01/archive-check/run'
physical=read(run/'capture/result.json');perception=read(run/'capture/perception.json')
prep=perception['preparation_final'];stages=perception['backend_stages']
assert physical['status']=='FAIL' and physical['receipts']==0
assert prep['state']=='FAILED' and prep['error']=='settled probe deadline'
assert len(prep['calls'])==2 and not (run/'capture/native.json').exists()
assert read(bundle/'archive-validation.json')==dict(status='PASS',case_verdict='FAIL',source_files=1483,raw_packets=0,future_exclusion=16633)
assert not read(bundle/'disposition.json')['finite_diagnostic_pass']
for name in ['state-path','structured-state','monitor-timing','host-clock','owner-wait']:
    assert read(bundle/(name+'-reproduction.json'))['status']=='PASS'
write(bundle/'preparation-failure-analysis.json',dict(status='ORIGINAL_FAIL_PRESERVED',
    error=physical['error'],physical_receipts=0,native_started=False,raw_images=0,
    preparation=prep,stage_durations_ms=[dict(
        gray=(r['gray']-r['begin'])/1e6,health=(r['health']-r['gray'])/1e6,
        resize=(r['resize']-r['health'])/1e6,tensor=(r['tensor']-r['resize'])/1e6,
        inference=(r['inference']-r['tensor'])/1e6,decode=(r['decode']-r['inference'])/1e6) for r in stages],
    model_setup_cpus=perception['model_setup_cpus'],thread_overrides=perception['preparation_thread_overrides'],
    interpretation='Preparation tail recurred despite corrected pipeline CPU placement and CV4/resize4. Second call151.561ms includes119.010ms tensor stage and21.156ms inference. Original wall stamps alone cannot distinguish allocation, scheduling or kernel delay. No new physical/HV observations.',
    next_candidate='Explicit existing byte-exact reusable NCHW workspace; unchanged three-call/last-two<100ms gate; separate source freeze and first-failure stop.'))

manifest=read(bundle/'run-manifest.json');assert not read(bundle/'raw-manifest.json')['archives']
assert identity(bundle/manifest['archive'])=={k:manifest[k] for k in ('bytes','sha256')}
check_tar(bundle/manifest['archive'],manifest['members'])
review=dict(schema='m10-retained-review-v1',scope='All pre-native failure members; zero physical receipts and raw images',
    original_archive=manifest['archive'],original_archive_sha256=manifest['sha256'],original_members=manifest['members'],derived={})
review_data=(json.dumps(review,indent=2)+'\n').encode();target=bundle/'retained-metadata.tar.gz'
assert not target.exists()
with tarfile.open(target,'w:gz') as tar:
    for name,item in manifest['members'].items():
        data=(run/name).read_bytes();assert digest(data)==item;add(tar,name,data)
    add(tar,'MANIFEST.json',review_data)
check_tar(target,dict(manifest['members'],**{'MANIFEST.json':digest(review_data)}))
write(bundle/'retained-metadata.json',dict(status='PASS',archive=target.name,**identity(target),
    original_members=len(manifest['members']),derived_window_rows=0,full_run_preserved_locally=True))

frozen=read(SERIES/'sources.json');assert sha(SERIES/'sources.tar.gz')==frozen['archive_sha256']
check_tar(SERIES/'sources.tar.gz',frozen['files'])
# Post-live preparation study and workspace fix are distinct from the live source.
names=set(frozen['files'])|{str(p.relative_to(ROOT)) for p in SERIES.glob('*.py')}
changed={n:identity(ROOT/n) for n in sorted(names) if n not in frozen['files'] or identity(ROOT/n)!=frozen['files'][n]}
post=SERIES/'post-live-sources.tar.gz';assert not post.exists()
with tarfile.open(post,'w:gz') as tar:
    for name in changed:tar.add(ROOT/name,arcname=name,recursive=False)
check_tar(post,changed)
write(SERIES/'post-live-sources.json',dict(scope='Changes after original FAIL; not used in original run',
    original_source_archive_sha256=frozen['archive_sha256'],archive=post.name,archive_sha256=sha(post),files=changed))

removed=[]
for folder,expected in [(run,manifest['members']),
        (WORK/'normal-30s-01/archive-check/source',frozen['files']),
        (WORK/'frozen-tests/source',frozen['files'])]:
    files={str(p.relative_to(folder)):p for p in folder.rglob('*') if p.is_file()}
    assert all('__pycache__' in Path(n).parts and n.endswith('.pyc') for n in set(files)-set(expected))
    for name,item in expected.items():assert not files[name].is_symlink() and identity(files[name])==item
    removed.append(dict(path=str(folder.relative_to(ROOT)),bytes=sum(p.stat().st_size for p in files.values())))
    shutil.rmtree(folder)
write(SERIES/'storage-closeout.json',dict(status='PASS',removed=removed,removed_bytes=sum(v['bytes'] for v in removed),
    retained='Original full run/source and all pre-native metadata; no raw images existed',free_bytes={p:shutil.disk_usage(p).free for p in ('/tmp','/d')}))

files=read(SERIES/'pre-install.json')['files']
for item in files.values():
    item['checked_sha256']=sha(item['path']);assert item['sha256']==item['checked_sha256']
policy={n:Path('/sys/devices/system/cpu/intel_pstate',n).read_text().strip() for n in ('min_perf_pct','max_perf_pct','no_turbo')}
assert policy==dict(min_perf_pct='16',max_perf_pct='100',no_turbo='0')
shutil.copy2(WORK/'power-lease.jsonl',SERIES/'power-lease.jsonl')
lease=[json.loads(line) for line in (SERIES/'power-lease.jsonl').read_text().splitlines()]
assert [r['event'] for r in lease]==['OWNER','APPLIED','RESTORED'] and lease[-1]['reason']=='OWNER_EXIT'
processes=subprocess.check_output(['ps','-eo','comm='],text=True).splitlines()
assert not any(p.strip()=='UE4Editor' or p.strip().startswith('m7_carla_wall') for p in processes)
write(SERIES/'restoration-confirmation.json',dict(status='PASS',checked_utc=datetime.now(timezone.utc).isoformat(),files=files,policy=policy))
sequence=read(SERIES/'sequence-disposition.json')
assert sequence['runtime_restoration']['status']=='PASS'
assert all(sequence['cases'][n]=='NOT_RUN_STOP_ON_FIRST_FAILURE_OR_LEASE_END' for n in ('normal-30s-02','normal-300s-01'))
write(SERIES/'final-validation.json',dict(status='PASS_EVIDENCE_AND_RESTORATION_ONLY',original_case_verdict='FAIL_BEFORE_NATIVE',
    source_files=len(frozen['files']),python_tests_before_live=504,frozen_tests_before_live=88,
    original_failure_reproduced=True,raw_images=0,future_exclusion=16633,host_policy=policy,shared_runtime_restored=True,
    preparation_study=read(SERIES/'preparation-study/summary.json'),
    study_scope='40 fixed fresh processes without CARLA at original cap100; no reproduction of live tail, not acceptance',
    physical_stability_accepted=False,boost_cap_promoted=False,native_perception_accepted=False,milestone_closed=False))
print('Original pre-native FAIL preserved, archives checked, duplicate extractions removed, runtime/cap restored.')

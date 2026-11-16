"""Verify the completed original V2 sequence and compact only checked copies."""
from datetime import datetime,timezone
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[4];SERIES=Path(__file__).resolve().parent
WORK=ROOT/'build/m10-owner-wait-v2';PYTHON=ROOT/'build/m10-perception/cuda-venv/bin/python'
sys.path.insert(0,str(ROOT/'tests/integration/perception'))
from runtime_restoration_v1 import sha
def read(p):return json.loads(p.read_text())
def identity(p):return dict(bytes=p.stat().st_size,sha256=sha(p))
def write(p,v):
    assert not p.exists(),'immutable completion evidence'
    p.write_text(json.dumps(v,indent=2)+'\n')
def call(args,log):
    with log.open('w') as stream:subprocess.run(list(map(str,args)),stdout=stream,stderr=subprocess.STDOUT,check=True)

sequence=read(SERIES/'sequence-disposition.json');assert sequence['runtime_restoration']['status']=='PASS'
known={};cases={};total=0
for name,passed,images,exclusion in [('normal-30s-01',True,283,16916),('normal-30s-02',True,282,17198),('normal-300s-01',False,2793,19991)]:
    bundle=SERIES/name;run=WORK/name/'archive-check/run';case=read(bundle/'disposition.json');cases[name]=case
    assert case['finite_diagnostic_pass']==passed and case['archive']=='PASS' and case['drive_fault_replay']
    assert read(bundle/'archive-validation.json')==dict(status='PASS',case_verdict='PASS_DIAGNOSTIC_CASE_ONLY' if passed else 'FAIL',source_files=1490,raw_packets=images,future_exclusion=exclusion)
    assert read(bundle/'workspace.json')['status']=='PASS_EXPLICIT_WORKSPACE_ONLY'
    for kind in ['state-path','structured-state','monitor-timing','host-clock','owner-wait','workspace']:
        assert read(bundle/(kind+'-reproduction.json'))['status']=='PASS'
    assert read(bundle/'replay.json')['exact'] and read(bundle/'restoration.json')['status']=='PASS'
    perception=read(run/'capture/perception.json')
    assert perception['preparation']['state']=='READY' and perception['tensor_workspace'] is True
    write(bundle/'model-preparation.json',dict(status='PASS',scope='Original live preparation, before shutdown cancellation',
        preparation=perception['preparation'],tensor_workspace=perception['tensor_workspace'],
        model_cpus=perception['model_setup_cpus'],observer_cpus=perception['observer_cpus_after_setup'],
        thread_overrides=perception['preparation_thread_overrides'],original_stages=perception['backend_stages']))
    call([PYTHON,SERIES/'package-review.py','--run',run,'--bundle',bundle],WORK/name/'package-review.log')
    print('REVIEW '+name,flush=True)
    call([PYTHON,ROOT/'tests/integration/perception/compact_endurance_archive_v1.py','--bundle',bundle,'--checked-run',run],WORK/name/'compaction.log')
    compact=read(WORK/name/'compaction.log');assert compact['status']=='PASS'
    write(bundle/'compaction-validation.json',compact)
    print('COMPACTED '+name,flush=True)
    archive=read(bundle/'run-manifest.json');known[bundle/archive['archive']]=archive
    known.update({bundle/v['archive']:v for v in read(bundle/'raw-manifest.json')['archives']})
    total+=images

frozen=read(SERIES/'sources.json');assert sha(SERIES/'sources.tar.gz')==frozen['archive_sha256']
names=set(frozen['files'])|{str(p.relative_to(ROOT)) for p in SERIES.glob('*.py')}
paths=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT,text=True).split('\0')
names.update(n for n in paths if n.startswith(('physical_ai/','tests/','tools/')) and (ROOT/n).is_file())
changed={n:identity(ROOT/n) for n in sorted(names) if n not in frozen['files'] or identity(ROOT/n)!=frozen['files'][n]}
target=SERIES/'post-live-sources.tar.gz';assert not target.exists()
with tarfile.open(target,'w:gz') as tar:
    for name in changed:tar.add(ROOT/name,arcname=name,recursive=False)
with tarfile.open(target,'r:gz') as tar:
    assert set(tar.getnames())==set(changed)
    for name,item in changed.items():
        data=tar.extractfile(name).read();assert dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())==item
write(SERIES/'post-live-sources.json',dict(scope='After original V2 measurements; includes post-hoc analysis and next GC candidate, not used in V2',
    original_source_archive_sha256=frozen['archive_sha256'],archive=target.name,archive_sha256=sha(target),files=changed))
call([PYTHON,SERIES/'closeout-storage.py'],WORK/'storage-closeout.log')

files=read(SERIES/'pre-install.json')['files']
for item in files.values():
    item['checked_sha256']=sha(item['path']);assert item['checked_sha256']==item['sha256']
policy={n:Path('/sys/devices/system/cpu/intel_pstate',n).read_text().strip() for n in ('min_perf_pct','max_perf_pct','no_turbo')}
assert policy==dict(min_perf_pct='16',max_perf_pct='100',no_turbo='0')
shutil.copy2(WORK/'power-lease.jsonl',SERIES/'power-lease.jsonl')
lease=[json.loads(line) for line in (SERIES/'power-lease.jsonl').read_text().splitlines()]
assert [v['event'] for v in lease]==['OWNER','APPLIED','RESTORED'] and lease[-1]['reason']=='TIME_LIMIT'
for name in cases:
    analysis=read(SERIES/name/'analysis.json')
    assert max(v['end_wall_ns'] for v in analysis['shutdown'].values())<lease[-1]['wall_ns']
    assert read(SERIES/name/'preflight.json')['host_policy']['max_perf_pct']=='70'
processes=subprocess.check_output(['ps','-eo','comm='],text=True).splitlines()
assert not any(p.strip()=='UE4Editor' or p.strip().startswith('m7_carla_wall') for p in processes)
write(SERIES/'restoration-confirmation.json',dict(status='PASS',checked_utc=datetime.now(timezone.utc).isoformat(),files=files,policy=policy,
    lease_restoration_reason='TIME_LIMIT',all_measured_runs_and_server_shutdowns_before_restoration=True))
assert total==3358
fault=read(SERIES/'normal-300s-01/first-fault-analysis.json');gap=read(SERIES/'normal-300s-01/native-gap-analysis.json')
assert fault['status']=='PASS_ORIGINAL_FAILURE_LOCALIZED' and len(gap['missing'])==18
storage=read(SERIES/'storage-closeout.json')
write(SERIES/'final-validation.json',dict(status='PASS_EVIDENCE_AND_RESTORATION_ONLY',original_cases=cases,
    original_source_files=1490,python_tests_before_live=505,frozen_tests_before_live=93,original_first_fault_preserved=True,
    raw_images_checked=total,future_exclusion=19991,host_policy=policy,shared_runtime_restored=True,
    storage_saved_bytes=storage['removed_bytes']+storage['raw_compaction_saved_bytes'],
    physical_stability_accepted=False,boost_cap_promoted=False,native_perception_accepted=False,milestone_closed=False,
    next_focus='Direct GC brackets and owner-only serial GC; retain separate later18 missing jobs and90C observation'))
print('COMPLETE: original PASS/PASS/FAIL retained; all raw bytes and runtime restoration verified.',flush=True)

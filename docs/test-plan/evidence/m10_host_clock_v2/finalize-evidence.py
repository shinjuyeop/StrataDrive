"""Verify immutable V2 trials, post-run analysis and original runtime restoration."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[4];SERIES=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tests/integration/perception'))
from runtime_restoration_v1 import sha
def read(path):return json.loads(path.read_text())
def identity(path):return dict(bytes=path.stat().st_size,sha256=sha(path))
def digest(data):return dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
def check_tar(path,members):
    with tarfile.open(path,'r:gz') as tar:
        assert len(tar.getnames())==len(members) and set(tar.getnames())==set(members)
        for name,item in members.items():assert digest(tar.extractfile(name).read())==item,name
frozen=read(SERIES/'sources.json');assert len(frozen['files'])==1468
assert sha(SERIES/'sources.tar.gz')==frozen['archive_sha256']
check_tar(SERIES/'sources.tar.gz',frozen['files'])
for name,item in frozen['files'].items():assert identity(ROOT/name)==item,name
known={};cases={}
for name,passed,images,count in [('normal-30s-01',True,284,16351),('normal-30s-02',False,282,16633)]:
    bundle=SERIES/name;case=read(bundle/'disposition.json');cases[name]=case
    assert case['finite_diagnostic_pass']==passed and case['archive']=='PASS'
    assert case['drive_fault_replay'] and not case['native_perception_accepted'] and not case['milestone_closed']
    assert read(bundle/'archive-validation.json')==dict(status='PASS',case_verdict='PASS_DIAGNOSTIC_CASE_ONLY' if passed else 'FAIL',source_files=1468,raw_packets=images,future_exclusion=count)
    for target in ['state-path-reproduction.json','structured-state-reproduction.json','monitor-timing-reproduction.json','host-clock-reproduction.json']:
        assert read(bundle/target)['status']=='PASS'
    assert read(bundle/'restoration.json')['status']=='PASS'
    assert read(bundle/'replay.json')['exact'] and read(bundle/'compaction-validation.json')['status']=='PASS'
    prep=read(bundle/'model-preparation.json');assert prep['status']=='PASS' and prep['preparation']['state']=='READY'
    clock=read(bundle/'host-clock-audit.json');assert not any(clock['thermal_delta'].values())
    assert not clock['all_cores_at_most_850mhz_wall_ns']
    run=read(bundle/'run-manifest.json');known[bundle/run['archive']]=run
    known.update({bundle/item['archive']:item for item in read(bundle/'raw-manifest.json')['archives']})
    review=read(bundle/'retained-metadata.json');assert review['status']=='PASS'
    target=bundle/review['archive'];assert identity(target)=={k:review[k] for k in ('bytes','sha256')}
    with tarfile.open(target,'r:gz') as tar:data=tar.extractfile('MANIFEST.json').read();manifest=json.loads(data)
    check_tar(target,dict(manifest['original_members'],**{n:{k:v[k] for k in ('bytes','sha256')} for n,v in manifest['derived'].items()},**{'MANIFEST.json':digest(data)}))
assert read(SERIES/'normal-30s-01/prefix-comparison.json')['status']=='PASS_MATCHED_PREFIX'
assert read(SERIES/'normal-30s-02/prefix-comparison.json')['status']=='NOT_COMPARABLE'
fault=read(SERIES/'normal-30s-02/first-fault-analysis.json')
assert fault['status']=='PASS_ORIGINAL_FAILURE_EXPLAINED'
assert fault['original_first_fault']['observed_ns']-fault['original_first_fault']['held_hv']['dependency_ns']==30_490_079
assert fault['native_slots_all']==dict(eligible=150010,missing=0,late=0)
sequence=read(SERIES/'sequence-disposition.json')
assert sequence['cases']['normal-300s-01']=='NOT_RUN_STOP_ON_FIRST_FAILURE_OR_LEASE_END'
assert sequence['runtime_restoration']['status']=='PASS'
assert all(r['status']=='ALREADY_ORIGINAL' for r in sequence['runtime_restoration']['components'].values())
restoration=read(SERIES/'restoration-confirmation.json');assert restoration['status']=='PASS'
for item in restoration['files'].values():assert sha(item['path'])==item['sha256']
shared={r['path'] for r in restoration['files'].values()}
for name,expected in frozen['external'].items():
    if name not in shared:assert sha(name)==expected,name
policy={n:Path('/sys/devices/system/cpu/intel_pstate',n).read_text().strip() for n in ('min_perf_pct','max_perf_pct','no_turbo')}
assert policy==dict(min_perf_pct='16',max_perf_pct='100',no_turbo='0')
lease=[json.loads(line) for line in (SERIES/'power-lease.jsonl').read_text().splitlines()]
assert [r['event'] for r in lease]==['OWNER','APPLIED','RESTORED'] and lease[-1]['reason']=='OWNER_EXIT'
assert re.search(r'Ran 501 tests in [\d.]+s\s+OK\s*$',(SERIES/'python-tests.txt').read_text())
assert read(SERIES/'frozen-tests.json')['focused_tests']==85
processes=subprocess.check_output(['ps','-eo','comm='],text=True).splitlines()
assert not any(n.strip()=='UE4Editor' or n.strip().startswith('m7_carla_wall') for n in processes)
storage=read(SERIES/'storage-closeout.json')
result=dict(status='PASS_EVIDENCE_AND_RESTORATION_ONLY',checked_utc=datetime.now(timezone.utc).isoformat(),
    source_files=1468,source_unchanged_since_freeze=True,python_tests=501,frozen_tests=85,unchanged_native_cpp_tests=207,
    original_cases=cases,raw_images_checked=566,future_exclusion=16633,host_policy=policy,shared_runtime_restored=True,
    no_owned_servers_running=True,storage_saved_bytes=storage['removed_bytes']+storage['raw_compaction_saved_bytes'],
    next_focus='owner pump wait/gate eligibility and thread scheduling; original HV30ms unchanged',
    physical_stability_accepted=False,boost_cap_promoted=False,native_perception_accepted=False,milestone_closed=False)
(SERIES/'final-validation.json').write_text(json.dumps(result,indent=2)+'\n')
entries=[]
for path in sorted(p for p in SERIES.rglob('*') if p.is_file() and p.name!='SHA256SUMS' and '__pycache__' not in p.parts):
    if path in known:
        assert path.stat().st_size==known[path]['bytes'];value=known[path]['sha256']
    else:value=sha(path)
    entries.append(f'{value}  {path.relative_to(SERIES)}\n')
(SERIES/'SHA256SUMS').write_text(''.join(entries))
print(json.dumps(result))

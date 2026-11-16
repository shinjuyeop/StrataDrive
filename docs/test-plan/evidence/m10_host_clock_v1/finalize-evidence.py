"""Verify V1's original results, separate post-live fixes, and restoration."""
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[4]
SERIES=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tests/integration/perception'))
from runtime_restoration_v1 import sha
def read(p): return json.loads(p.read_text())
def identity(p): return dict(bytes=p.stat().st_size,sha256=sha(p))
def digest(data): return dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
def write(p,v): p.write_text(json.dumps(v,indent=2)+'\n')
def check_tar(path,members):
    with tarfile.open(path,'r:gz') as tar:
        assert len(tar.getnames())==len(members) and set(tar.getnames())==set(members)
        for name,item in members.items(): assert digest(tar.extractfile(name).read())==item,name
def pack(path,files):
    assert not path.exists()
    with tarfile.open(path,'w:gz') as tar:
        for name,data in sorted(files.items()):
            info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o644
            tar.addfile(info,io.BytesIO(data))
    check_tar(path,{n:digest(v) for n,v in files.items()})

frozen=read(SERIES/'sources.json')
assert sha(SERIES/'sources.tar.gz')==frozen['archive_sha256']
check_tar(SERIES/'sources.tar.gz',frozen['files'])
expected_changed={f'tests/integration/perception/{name}' for name in (
    'control_shadow_capture_v1.py','endurance_host_v1.py','test_endurance_host_v1.py','test_fence_compare_v1.py')}
changed={n:dict(original=v,corrected=identity(ROOT/n)) for n,v in frozen['files'].items() if identity(ROOT/n)!=v}
assert set(changed)==expected_changed,set(changed)
for name in ('evidence_reproduction_v1.py','runtime_restoration_v1.py','test_evidence_reproduction_v1.py',
             'test_runtime_restoration_v1.py','test_capture_setup_v1.py'):
    name='tests/integration/perception/'+name
    changed[name]=dict(original=None,corrected=identity(ROOT/name))
post=SERIES/'post-live-revisions.json'
archive=SERIES/'post-live-sources.tar.gz'
if not post.exists():
    pack(archive,{n:(ROOT/n).read_bytes() for n in changed})
    write(post,dict(scope='Post-live preparation placement and cleanup fixes; original source and live verdicts unchanged',
        archive=archive.name,archive_identity=identity(archive),original_source_manifest_sha256=sha(SERIES/'sources.json'),changed=changed))
assert read(post)['changed']==changed
check_tar(archive,{n:v['corrected'] for n,v in changed.items()})

# Preserve the exact source used for the three predeclared preparation checks.
declaration=read(SERIES/'preparation-check-declaration.json');files={}
for name,expected in declaration['files'].items():
    data=(ROOT/name).read_bytes()
    if digest(data)['sha256']!=expected and name.endswith('control_shadow_capture_v1.py'):
        data=data.replace(b"str(self.report['preparation']['error'] or 'not ready')",b"self.report['preparation']['error']")
    assert digest(data)['sha256']==expected,name
    files[name]=data
probe=SERIES/'preparation-check-sources.tar.gz'
if not probe.exists():pack(probe,files)
check_tar(probe,{n:digest(d) for n,d in files.items()})
assert read(SERIES/'preparation-check-results.json')['status']=='PASS'

runtime=read(SERIES/'restoration-confirmation.json')
assert runtime['status']=='PASS'
for item in runtime['files'].values():assert sha(item['path'])==item['sha256']
policy={n:Path('/sys/devices/system/cpu/intel_pstate',n).read_text().strip() for n in ('min_perf_pct','max_perf_pct','no_turbo')}
assert policy==dict(min_perf_pct='16',max_perf_pct='100',no_turbo='0')
lease=[json.loads(line) for line in (SERIES/'power-lease.jsonl').read_text().splitlines()]
assert [r['event'] for r in lease]==['OWNER','APPLIED','RESTORED']
assert lease[-1]['maximum_percent']==100 and lease[-1]['reason']=='OWNER_EXIT'
known={}
for case_name,verdict,images in [('normal-30s-01','PASS_DIAGNOSTIC_CASE_ONLY',283),('normal-30s-02','FAIL',0)]:
    bundle=SERIES/case_name
    assert read(bundle/'archive-validation.json')==dict(status='PASS',case_verdict=verdict,source_files=1452,raw_packets=images,future_exclusion=16067)
    assert read(bundle/'restoration.json')['status']=='PASS'
    run=read(bundle/'run-manifest.json');known[bundle/run['archive']]=run
    known.update({bundle/r['archive']:r for r in read(bundle/'raw-manifest.json')['archives']})
    review=read(bundle/'retained-metadata.json');assert review['status']=='PASS'
    target=bundle/review['archive'];assert identity(target)=={k:review[k] for k in ('bytes','sha256')}
    with tarfile.open(target,'r:gz') as tar:
        data=tar.extractfile('MANIFEST.json').read();manifest=json.loads(data)
    members=dict(manifest['original_members'],**{n:{k:v[k] for k in ('bytes','sha256')} for n,v in manifest['derived'].items()},**{'MANIFEST.json':digest(data)})
    check_tar(target,members)
first=SERIES/'normal-30s-01';second=SERIES/'normal-30s-02'
assert read(first/'disposition.json')['finite_diagnostic_pass']
assert read(first/'replay.json')['exact'] and read(first/'drive-fault-replay.json')['equal']
assert read(first/'audit.json')['physical']['missing_slots']==read(first/'audit.json')['physical']['late_slots']==0
clock=read(first/'host-clock-audit.json')
assert not any(clock['thermal_delta'].values()) and not clock['all_cores_at_most_850mhz_wall_ns']
assert read(second/'posthoc-reproduction.json')['status']=='PASS'
assert read(second/'preparation-failure-analysis.json')['physical_receipts']==0
sequence=read(SERIES/'sequence-disposition.json')
assert not sequence['cases']['normal-30s-02']['finite_diagnostic_pass']
assert sequence['cases']['normal-300s-01']=='NOT_RUN_STOP_ON_FIRST_FAILURE_OR_LEASE_END'
assert sequence['runtime_restore_exit']==dict(dxc=1,module=1) # Original command errors retained.
assert re.search(r'Ran 501 tests in [\d.]+s\s+OK\s*$',(SERIES/'postfix-python-tests.txt').read_text())
assert read(SERIES/'frozen-tests.json')['focused_tests']==77
native=SERIES/'sensor-probe-01';records=read(native/'records.json')
check_tar(native/records['archive'],records['members'])
assert read(native/'result.json')['monitor_slots']['missing']==read(native/'result.json')['monitor_slots']['late']==0
processes=subprocess.check_output(['ps','-eo','comm='],text=True).splitlines()
assert not any(n.strip()=='UE4Editor' or n.strip().startswith('m7_carla_wall') for n in processes)
storage=read(SERIES/'storage-closeout.json')
result=dict(status='PASS_EVIDENCE_AND_RESTORATION_ONLY',checked_utc=datetime.now(timezone.utc).isoformat(),
    original_sequence='FIRST30_PASS_SECOND_PREPARATION_FAIL_300_NOT_RUN',source_files=1452,post_live_revision_files=len(changed),
    python_pre_live_tests=493,python_post_live_tests=501,frozen_tests=77,unchanged_native_cpp_tests=207,
    raw_images_checked=283,future_exclusion=16067,host_policy=policy,shared_runtime_restored=True,no_owned_servers_running=True,
    storage_saved_bytes=storage['removed_bytes']+storage['raw_compaction_saved_bytes'],
    physical_stability_accepted=False,native_perception_accepted=False,milestone_closed=False)
write(SERIES/'final-validation.json',result)
entries=[]
for path in sorted(p for p in SERIES.rglob('*') if p.is_file() and p.name!='SHA256SUMS' and '__pycache__' not in p.parts):
    if path in known:
        assert path.stat().st_size==known[path]['bytes'];value=known[path]['sha256']
    else:value=sha(path)
    entries.append(f'{value}  {path.relative_to(SERIES)}\n')
(SERIES/'SHA256SUMS').write_text(''.join(entries))
print(json.dumps(result))

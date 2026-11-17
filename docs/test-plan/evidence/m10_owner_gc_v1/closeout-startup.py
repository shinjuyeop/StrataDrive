"""Preserve the original pre-control readiness failure and restoration evidence."""
from datetime import datetime,timezone
import gzip,hashlib,io,json,shutil,subprocess,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];SERIES=Path(__file__).resolve().parent
WORK=ROOT/'build/m10-owner-gc-v1';BUNDLE=SERIES/'normal-30s-01';RUN=WORK/'normal-30s-01/archive-check/run'
def read(p):return json.loads(p.read_text())
def identity(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return dict(bytes=p.stat().st_size,sha256=h.hexdigest())
def write(p,v):
    assert not p.exists(),'immutable closeout record'
    p.write_text(json.dumps(v,indent=2)+'\n')
archive=read(BUNDLE/'run-manifest.json')
assert identity(BUNDLE/archive['archive'])=={k:archive[k] for k in ('bytes','sha256')}
for name,item in archive['members'].items():assert identity(RUN/name)==item
assert read(BUNDLE/'archive-validation.json')==dict(status='PASS',case_verdict='FAIL',source_files=1501,raw_packets=0,future_exclusion=19991)
server=read(RUN/'server.json');assert server['status']=='FAIL' and 'original180s readiness horizon exhausted' in server['error']
assert not (RUN/'capture').exists() and set(server['shutdown'])=={'renderer'}
snapshot=read(RUN/'renderer/shutdown/before.json');main=next(r for r in snapshot['threads'] if r['tid']==snapshot['pid'])
assert main['wchan']['text']=='folio_wait_bit_common'
profile=[]
with gzip.open(RUN/'host-profile.jsonl.gz','rt') as f:
    for line in f:profile.append(json.loads(line))
samples=[p for row in profile for p in row['processes'] if p['pid']==snapshot['pid']]
temperatures=[v/1000 for row in profile for k,v in row['host'].items() if '/temp' in k]
write(BUNDLE/'startup-analysis.json',dict(status='RECORDED_PRE_CONTROL_FAILURE',cause_boundary='renderer readiness before owner launch or any capture',
    original_error=server['error'],owner_started=False,control_receipts=0,raw_images=0,inferences=0,gc_cycles_measured=0,
    renderer_shutdown=server['shutdown']['renderer'],main_thread_at_shutdown_diagnostic=main,
    sampled_main_states={state:sum(p['state']==state for p in samples) for state in sorted({p['state'] for p in samples})},
    max_cpu_c=max(temperatures),renderer_major_faults_max=max(p['major_faults'] for p in samples),
    cache_read_megabytes_per_second=dict(current=5.99,prior_owner_wait_v2_normal30_01=2993.01),
    interpretation='Direct read/page-cache disk wait observation; cold asset I/O is leading startup explanation, not a controlled storage benchmark or GC result'))
names=[n for n in archive['members'] if not n.endswith('.jsonl.gz')]
target=BUNDLE/'retained-metadata.tar.gz';assert not target.exists()
review=dict(scope='Selected original startup metadata; full host profiles and original run remain local',
    original_archive_sha256=archive['sha256'],members={n:archive['members'][n] for n in names})
with tarfile.open(target,'w:gz') as tar:
    for name in names:tar.add(RUN/name,arcname=name,recursive=False)
    data=(json.dumps(review,indent=2)+'\n').encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(data)
    tar.addfile(info,io.BytesIO(data))
with tarfile.open(target,'r:gz') as tar:
    for name,item in review['members'].items():
        data=tar.extractfile(name).read();assert dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())==item
write(BUNDLE/'retained-metadata.json',dict(status='PASS',archive=target.name,**identity(target),original_members=len(names),full_run_preserved_locally=True))
shutil.copy2(WORK/'power-lease.jsonl',SERIES/'power-lease.jsonl')
lease=[json.loads(line) for line in (SERIES/'power-lease.jsonl').read_text().splitlines()]
assert [r['event'] for r in lease]==['OWNER','APPLIED','RESTORED'] and lease[-1]['reason']=='OWNER_EXIT'
assert server['shutdown']['renderer']['end_wall_ns']<lease[-1]['wall_ns']
files=read(SERIES/'pre-install.json')['files']
for item in files.values():item['checked_sha256']=identity(Path(item['path']))['sha256'];assert item['checked_sha256']==item['sha256']
policy={n:Path('/sys/devices/system/cpu/intel_pstate',n).read_text().strip() for n in ('min_perf_pct','max_perf_pct','no_turbo')}
assert policy==dict(min_perf_pct='16',max_perf_pct='100',no_turbo='0')
assert not any(n.strip()=='UE4Editor' for n in subprocess.check_output(['ps','-eo','comm='],text=True).splitlines())
write(SERIES/'restoration-confirmation.json',dict(status='PASS',checked_utc=datetime.now(timezone.utc).isoformat(),files=files,policy=policy,lease_restoration_reason='OWNER_EXIT'))
write(SERIES/'final-validation.json',dict(status='PASS_EVIDENCE_AND_RESTORATION_ONLY',physical_verdict='FAIL_BEFORE_CONTROL',
    archive_validation=read(BUNDLE/'archive-validation.json'),following_cases='NOT_RUN',original_source_files=1501,
    gc_effect_measured=False,physical_stability_accepted=False,native_perception_accepted=False,milestone_closed=False))
print('Original readiness failure preserved; all runtime files and maximum100 restored.')

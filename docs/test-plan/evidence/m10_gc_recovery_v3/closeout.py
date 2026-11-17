"""Preserve original finite verdicts and confirm the bounded host lease/restoration."""
from datetime import datetime,timezone
import hashlib,json,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];SERIES=Path(__file__).resolve().parent;WORK=ROOT/'build/m10-gc-recovery-v3'
read=lambda p:json.loads(p.read_text())
def write(p,v):
 assert not p.exists(),'immutable closeout';p.write_text(json.dumps(v,indent=2)+'\n')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as stream:
  for b in iter(lambda:stream.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
sequence=read(SERIES/'sequence-disposition.json');assert sequence['runtime_restoration']['status']=='PASS'
identity=read(WORK/'experiment-owner.json'); proc=Path('/proc')/str(identity['pid'])
assert not proc.exists() or int((proc/'stat').read_text().rsplit(')',1)[1].split()[19])!=identity['start_ticks']
shutil.copy2(WORK/'power-lease.jsonl',SERIES/'power-lease.jsonl')
events=[json.loads(line) for line in (SERIES/'power-lease.jsonl').read_text().splitlines()]
assert [e['event'] for e in events]==['OWNER','APPLIED','RESTORED']
assert events[-1]['maximum_percent']==100 and events[1]['maximum_percent']==70
cases={}
for name in ('normal-30s-01','normal-30s-02','normal-300s-01'):
 bundle=SERIES/name
 if not (bundle/'disposition.json').exists():continue
 run=WORK/name/'archive-check/run';disposition=read(bundle/'disposition.json');archive=read(bundle/'archive-validation.json')
 assert archive['status']=='PASS' and read(bundle/'replay.json')['exact'] and read(bundle/'drive-fault-replay.json')['equal']
 for stem in ('state-path','structured-state','monitor-timing','host-clock','owner-wait','workspace','owner-gc','admission-window'):
  assert read(bundle/(stem+'-reproduction.json'))['status']=='PASS'
 analysis=read(bundle/'analysis.json');path=read(bundle/'path-analysis.json');server=read(run/'server.json')
 assert events[1]['wall_ns']<path['initial_ns']<path['physical_end_ns']<events[-1]['wall_ns']
 assert all(v['end_wall_ns']<events[-1]['wall_ns'] for v in server['shutdown'].values())
 gc=read(bundle/'owner-gc.json');purge=read(bundle/'admission-window.json')
 if disposition['finite_diagnostic_pass']:
  assert read(bundle/'audit.json')['status']=='PASS_DIAGNOSTIC_CASE_ONLY'
  assert purge['status']=='PASS_GC_RECOVERY_PREFETCH_INTEGRITY'
  assert analysis['protection_intervals']==0
 cases[name]=dict(physical_audit=read(bundle/'audit.json')['status'],disposition=disposition,
  receipts=analysis['physical_intervals'],normal=analysis['normal_intervals'],init=analysis['init_intervals'],protected=analysis['protection_intervals'],raw=analysis['raw'],inferences=analysis['inferences'],camera_hz=analysis['camera_hz_during_physical'],scene_result_ms=analysis['scene_result_ms'],over_100ms=analysis['over_100ms'],hottest_c=path['fast_clock']['hottest_c'],thermal_delta=path['fast_clock']['thermal_delta'],native_deadlines=read(bundle/'native-gap-analysis.json')['counts'],gc=gc,purge=purge,archive=archive)
files=read(SERIES/'pre-install.json')['files']
for value in files.values():value['checked_sha256']=sha(Path(value['path']));assert value['checked_sha256']==value['sha256']
policy={n:Path('/sys/devices/system/cpu/intel_pstate',n).read_text().strip() for n in ('min_perf_pct','max_perf_pct','no_turbo')}
assert policy==dict(min_perf_pct='16',max_perf_pct='100',no_turbo='0')
assert 'UE4Editor' not in subprocess.check_output(['ps','-eo','comm='],text=True).splitlines()
write(SERIES/'restoration-confirmation.json',dict(status='PASS',checked_utc=datetime.now(timezone.utc).isoformat(),files=files,policy=policy,lease_restoration_reason=events[-1]['reason'],all_measured_work_and_server_shutdown_before_restoration=True))
write(SERIES/'final-validation.json',dict(status='PASS_EVIDENCE_AND_RESTORATION_ONLY',cases=cases,original_verdicts_preserved=True,all_declared_finite_cases_pass=len(cases)==3 and all(c['disposition']['finite_diagnostic_pass'] for c in cases.values()),continuous_driving_accepted=False,native_perception_accepted=False,milestone_closed=False))
print('Original finite verdicts preserved; archive/replay/reproduction and six-file/100% restoration verified.')

"""Close evidence, preserving the serial-GC physical failure and original limits."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[4];SERIES=Path(__file__).resolve().parent
WORK=ROOT/'build/m10-admission-window-v2'
read=lambda p:json.loads(p.read_text())
def write(p,v):
    assert not p.exists(),'immutable closeout record'
    p.write_text(json.dumps(v,indent=2)+'\n')
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

sequence=read(SERIES/'sequence-disposition.json')
assert sequence['runtime_restoration']['status']=='PASS'
shutil.copy2(WORK/'power-lease.jsonl',SERIES/'power-lease.jsonl')
events=[json.loads(line) for line in (SERIES/'power-lease.jsonl').read_text().splitlines()]
assert [e['event'] for e in events]==['OWNER','APPLIED','RESTORED']
assert events[-1]['reason']=='TIME_LIMIT' and events[-1]['maximum_percent']==100
cases={}
for name in ('normal-30s-01','normal-30s-02','normal-300s-01'):
    bundle=SERIES/name;run=WORK/name/'archive-check/run'
    disposition=read(bundle/'disposition.json');archive=read(bundle/'archive-validation.json')
    assert archive['status']=='PASS'
    assert read(bundle/'replay.json')['exact'] and read(bundle/'drive-fault-replay.json')['equal']
    assert read(bundle/'admission-window.json')['status']=='PASS_ADMISSION_WINDOW_INTEGRITY'
    for stem in ('state-path','structured-state','monitor-timing','host-clock','owner-wait','workspace','owner-gc','admission-window'):
        assert read(bundle/(stem+'-reproduction.json'))['status']=='PASS'
    analysis=read(bundle/'analysis.json');path=read(bundle/'path-analysis.json')
    assert events[1]['wall_ns']<path['initial_ns']<path['physical_end_ns']<events[-1]['wall_ns']
    server=read(run/'server.json')
    assert all(v['end_wall_ns']<events[-1]['wall_ns'] for v in server['shutdown'].values())
    expected_pass=name!='normal-300s-01'
    assert disposition['finite_diagnostic_pass']==expected_pass
    if expected_pass:
        assert analysis['normal_intervals']==5838 and analysis['protection_intervals']==0
        assert read(bundle/'audit.json')['status']=='PASS_DIAGNOSTIC_CASE_ONLY'
    else:
        assert read(bundle/'audit.json')['status']=='FAIL'
        fault=read(bundle/'first-fault-analysis.json')
        assert fault['all_serial_collections_exceed_hv_age']
    cases[name]=dict(physical_audit=read(bundle/'audit.json')['status'],disposition=disposition,
        receipts=analysis['physical_intervals'],normal=analysis['normal_intervals'],init=analysis['init_intervals'],
        protected=analysis['protection_intervals'],raw=analysis['raw'],inferences=analysis['inferences'],
        camera_hz=analysis['camera_hz_during_physical'],scene_result_ms=analysis['scene_result_ms'],
        over_100ms=analysis['over_100ms'],hottest_c=path['fast_clock']['hottest_c'],
        thermal_delta=path['fast_clock']['thermal_delta'],native_deadlines=read(bundle/'native-gap-analysis.json')['counts'],
        gc_live_cycles=read(bundle/'owner-gc.json')['live_cycles'],archive=archive)
files=read(SERIES/'pre-install.json')['files']
for value in files.values():
    value['checked_sha256']=sha(Path(value['path']));assert value['checked_sha256']==value['sha256']
policy={n:Path('/sys/devices/system/cpu/intel_pstate',n).read_text().strip() for n in ('min_perf_pct','max_perf_pct','no_turbo')}
assert policy==dict(min_perf_pct='16',max_perf_pct='100',no_turbo='0')
assert 'UE4Editor' not in subprocess.check_output(['ps','-eo','comm='],text=True).splitlines()
assert not Path('/proc/3006022').exists(),'do not start a competing shared-runtime installer'
write(SERIES/'restoration-confirmation.json',dict(status='PASS',checked_utc=datetime.now(timezone.utc).isoformat(),
    files=files,policy=policy,lease_restoration_reason=events[-1]['reason'],
    all_measured_work_and_server_shutdown_before_restoration=True))
write(SERIES/'final-validation.json',dict(status='PASS_EVIDENCE_AND_RESTORATION_ONLY',cases=cases,
    diagnosis='Direct serial GC pauses exceed unchanged HV30ms; first native HV fault inside first GC; exact native replay',
    original_verdicts_preserved=True,physical_stability_accepted=False,native_perception_accepted=False,milestone_closed=False))
print('Both 30s passes and 300s serial-GC failure preserved; archives/replays verified; six files and 100% restored.')

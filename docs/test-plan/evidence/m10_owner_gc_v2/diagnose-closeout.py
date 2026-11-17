"""Record completed original trials and post-run diagnosis without reclassifying failure."""
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import statistics
import subprocess

ROOT=Path(__file__).resolve().parents[4]; SERIES=Path(__file__).resolve().parent
WORK=ROOT/'build/m10-owner-gc-v2'
read=lambda p:json.loads(p.read_text())
def write(p,value):
    assert not p.exists(), 'immutable closeout result'
    p.write_text(json.dumps(value,indent=2)+'\n')
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as stream:
        for b in iter(lambda:stream.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
cases={}
for name in ('normal-30s-01','normal-30s-02'):
    bundle=SERIES/name; run=WORK/name/'archive-check/run'
    audit=read(bundle/'archive-validation.json'); assert audit['status']=='PASS'
    assert read(bundle/'replay.json')['exact'] and read(bundle/'drive-fault-replay.json')['equal']
    gc=read(bundle/'owner-gc.json');assert gc['live_cycles']==0
    staging=[]; acquisition=[]; selected={}
    with gzip.open(run/'capture/trace.jsonl.gz','rt') as stream:
        for line in stream:
            row=json.loads(line);r=row['receipt'];path=row['state_path']
            if r['original_actual']['native']['normal']:
                staging.append(int(r['wall_applied_ns'])-int(path['admitted']['wall_ns']))
                acquisition.append(int(r['physics_acquisition_end_ns'])-int(path['admitted']['wall_ns']))
            if name=='normal-30s-02' and int(r['frame']) in (5915,5916):selected[int(r['frame'])]=row
    def quant(v):return dict(count=len(v),p99_ns=statistics.quantiles(v,n=100,method='inclusive')[98],maximum_ns=max(v))
    cases[name]=dict(archive=audit, physical_pass=read(bundle/'disposition.json')['finite_diagnostic_pass'],
                    owner_gc_cycles=0, normal_admitted_to_applied=quant(staging),normal_admitted_to_acquisition=quant(acquisition))
    if selected:
        fault=read(run/'capture/native-drive-fault.json');hv=fault['held_hv']
        assert fault['observed_ns']-hv['dependency_ns']==30_452_587
        replay=read(bundle/'admission-replay.json')
        assert replay['original_native_replay_exact'] and replay['original_proof_bytes_equal']
        pairs={}
        for q in replay['queries']:
            if q['kind'] in ('Q','R'):pairs.setdefault(int(q['at']),{})[q['kind']]=q
        initial=read(run/'capture/native.json')['initial']
        due=initial+5609*5_000_000
        saved=[t for t,pair in pairs.items() if t>=due and pair['Q']['accepted']=='0' and pair['R']['accepted']=='1']
        assert saved
        write(bundle/'first-fault-analysis.json',dict(scope='post-run diagnosis; counterfactual probes are not recorded live polls or a successful rerun',
            original_first_fault=fault, fault_after_initial_ns=fault['observed_ns']-initial,
            held_hv_dependency_age_ns=fault['observed_ns']-hv['dependency_ns'],
            inherited_dependency_age_ns=hv['source_ns']-hv['dependency_ns'],
            held_duration_ns=fault['observed_ns']-hv['source_ns'],
            waiting_frame=5916,owner_wait=selected[5916]['state_path']['owner_wait'],
            next_acquired_before_fault_ns=fault['observed_ns']-int(selected[5916]['receipt']['physics_acquisition_end_ns']),
            original_gate_replay=dict(admissions=replay['original_admissions'],ingress=replay['original_ingress'],proof_bytes_equal=True),
            scheduled_next_due_ns=due,candidate_first_eligible_probe_ns=min(saved),candidate_last_eligible_probe_ns=max(saved),
            candidate_probe_count=len(saved),original_extra_reserve_ns=4_000_000,candidate_extra_reserve_ns=2_000_000,
            relevant_command_original_expiry_ns=1903272807511673,
            original_latest_preview_ns=1903272798511672,candidate_latest_preview_ns=1903272800511672,
            conclusions=['No owner GC occurred in either 30s run; this fault does not measure serial GC effectiveness.',
              'The retained last ineligible reason is not a count or history of all 52 rejected previews.',
              'Exact native and gate replay identifies original command coverage as the main preview wait.',
              'Post-ingress preview with a pre-ingress timestamp independently reproduces backwards-clock rejection.',
              'The 2ms extra staging margin allows an earlier eligible window on retained input; live behavior is untested.',
              'The native old-held expiry check precedes new sample acceptance and remains unchanged.']))
shutil.copy2(WORK/'power-lease.jsonl',SERIES/'power-lease.jsonl')
events=[json.loads(l) for l in (SERIES/'power-lease.jsonl').read_text().splitlines()]
assert [r['event'] for r in events]==['OWNER','APPLIED','RESTORED'] and events[-1]['reason']=='OWNER_EXIT'
for name in cases:
    server=read(WORK/name/'archive-check/run/server.json')
    assert all(r['end_wall_ns']<events[-1]['wall_ns'] for r in server['shutdown'].values())
files=read(SERIES/'pre-install.json')['files']
for item in files.values():
    item['checked_sha256']=sha(Path(item['path']));assert item['checked_sha256']==item['sha256']
policy={n:Path('/sys/devices/system/cpu/intel_pstate',n).read_text().strip() for n in ('min_perf_pct','max_perf_pct','no_turbo')}
assert policy==dict(min_perf_pct='16',max_perf_pct='100',no_turbo='0')
assert 'UE4Editor' not in [n.strip() for n in subprocess.check_output(['ps','-eo','comm='],text=True).splitlines()]
write(SERIES/'restoration-confirmation.json',dict(status='PASS',checked_utc=datetime.now(timezone.utc).isoformat(),files=files,policy=policy,lease_restoration_reason='OWNER_EXIT'))
write(SERIES/'final-validation.json',dict(status='PASS_EVIDENCE_AND_RESTORATION_ONLY',cases=cases,
      physical_verdict='PASS_30S_THEN_FAIL_30S_HV_EXPIRY',following_300s='NOT_RUN',future_exclusion=20556,
      source_files=1513,gc_effect_measured=False,physical_stability_accepted=False,native_perception_accepted=False,milestone_closed=False))
print('Two original trials, exact replay, failure diagnosis and runtime restoration recorded.')

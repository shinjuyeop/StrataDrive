"""Join exact replay, observed recovery frames and staging costs without changing FAIL."""
import json
from pathlib import Path

BUNDLE=Path(__file__).resolve().parent/'normal-300s-01'
read=lambda name:json.loads((BUNDLE/name).read_text())
replay=read('admission-replay.json');frames=read('gc-recovery-frames.json');budget=read('preview-budget-analysis.json')
assert replay['original_native_replay_exact'] and replay['original_proof_bytes_equal']
gc=frames['gc'];end=int(gc['end']['wall_ns']);fault=frames['first_fault'];at=fault['observed_ns']
held=int(fault['held_hv']['sequence']);index={r['frame']:r for r in frames['frames']}
normal=[index[f] for f in range(int(gc['completed_frame'])+1,held+1)]
assert all(r['receipt']['original_actual']['admitted_actual']['normal'] for r in normal)
assert all(r['hv_origin']['dependency_ns']==fault['held_hv']['dependency_ns'] for r in normal)
last=index[held];next_row=index[held+1];outside=next_row['state_path']['owner_wait']['outside']
assert int(outside['longest_begin']['wall_ns'])==int(last['state_path']['complete']['wall_ns'])
next_pump=int(outside['longest_end']['wall_ns'])
windows={}
for kind in ('Q','R','H','T','C','Z'):
    groups=[]
    for row in replay['queries']:
        stamp=int(row['at'])
        if row['kind']!=kind or not end<=stamp<at:continue
        accepted=row['accepted']=='1';reason=row['reason']
        if not groups or (groups[-1]['accepted'],groups[-1]['reason'])!=(accepted,reason):
            groups.append(dict(accepted=accepted,reason=reason,first_after_gc_ns=stamp-end,last_after_gc_ns=stamp-end,queries=1))
        else:groups[-1]['last_after_gc_ns']=stamp-end;groups[-1]['queries']+=1
    windows[kind]=groups
result=dict(status='EXACT_ORIGINAL_REPLAY_AND_OBSERVED_RECOVERY',gc=gc,first_fault=fault,
    gc_wall_ns=end-int(gc['begin']['wall_ns']),normal_frames_after_gc=[r['frame'] for r in normal],
    inherited_dependency_age_ns=fault['held_hv']['source_ns']-fault['held_hv']['dependency_ns'],
    fault_dependency_age_ns=at-fault['held_hv']['dependency_ns'],fault_after_gc_ns=at-end,
    next_pump_after_gc_ns=next_pump-end,original_next_frame_reasons=next_row['state_path']['owner_wait']['reasons'],
    original_admissions=replay['original_admissions'],original_ingress=replay['original_ingress'],
    preview_query_kinds=replay['query_kind'],counterfactual_windows=windows,original_staging_costs=budget['metrics'],
    next_candidate=dict(extra_preview_ns=300_000,reason='0.5ms windows are narrow; 250us is below one observed 251494ns final-check-to-application sample. 300us exceeds that observed maximum while retaining additional read-only eligibility windows.',
        original_final_gate_unchanged=True,physical_interval_ns=5_000_000,hv_age_ns=30_000_000),
    interpretation='Three normal post-GC frames still inherited pre-GC wheel/actuator source time. Original 1ms preview rejected the next recovery window; the unchanged native held input subsequently expired. Counterfactual probes do not advance physics or establish that another trajectory recovers. The original FAIL and source timestamps remain authoritative.')
(BUNDLE/'recovery-window-analysis.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ('gc_wall_ns','normal_frames_after_gc','fault_dependency_age_ns','fault_after_gc_ns','next_pump_after_gc_ns','original_admissions','original_ingress')}))

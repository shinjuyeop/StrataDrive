"""Relate original post-GC work to the byte-exact native/admission replay."""
import argparse,gzip,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--bundle',type=Path,required=True);a=p.parse_args()
read=lambda p:json.loads(p.read_text())
fault=read(a.bundle/'first-fault-analysis.json');replay=read(a.bundle/'admission-replay.json')
assert replay['original_native_replay_exact'] and replay['original_proof_bytes_equal']
held=int(fault['original_first_fault']['held_hv']['sequence']);initial=read(a.run/'capture/native.json')['initial'];records=[]
with gzip.open(a.run/'capture/trace.jsonl.gz','rt') as stream:
 for line in stream:
  row=json.loads(line);frame=int(row['receipt']['frame'])
  if held-3<=frame<=held+5:
   receipt=row['receipt'];state=row['state_path'];actual=receipt['original_actual']['admitted_actual']
   records.append(dict(frame=frame,normal=actual['normal'],acquired_begin_ns=int(receipt['physics_acquisition_begin_ns']),acquired_end_ns=int(receipt['physics_acquisition_end_ns']),oldest_actuator_ns=int(actual['oldest_actuator_ns']),checked_through_ns=int(actual['command_checked_through_ns']),state_path=state))
  if frame>held+5:break
current=next(r for r in records if r['frame']==held);following=next(r for r in records if r['frame']==held+1)
outside=following['state_path']['owner_wait']['outside'];pump=int(outside['longest_end']['wall_ns'])
assert int(outside['longest_begin']['wall_ns'])==int(current['state_path']['complete']['wall_ns'])
first=int(fault['original_first_fault']['observed_ns']);windows={}
for kind in ('Q','R','Z'):
 accepted=[int(q['at']) for q in replay['queries'] if q['kind']==kind and q['accepted']=='1' and int(q['at'])<first]
 assert accepted
 windows[kind]=dict(count=len(accepted),first_ns=min(accepted),last_ns=max(accepted),last_before_actual_pump_ns=pump-max(accepted))
assert all(v['last_before_actual_pump_ns']>0 for v in windows.values())
result=dict(status='RECORDED_POST_GC_RECOVERY_WINDOW',initial_ns=initial,held_frame=held,records=records,
 original_admissions=replay['original_admissions'],original_ingress=replay['original_ingress'],original_native_replay_exact=True,original_proof_bytes_equal=True,probe_spacing_ns=50000,probe_windows=windows,first_actual_next_pump_ns=pump,
 interpretation='First post-GC frame carried inherited HV age. Subsequent 2.564712ms outside work missed every pre-fault sampled eligibility window, even with zero extra preview slack. Its CPU time was 2.565197ms with no context switches. Engine default incremental purge is 2ms, but the old trace did not directly bracket it. A smaller slice plus 1ms preview is a prospective candidate, not demonstrated recovery; all original judgments remain FAIL.')
(a.bundle/'recovery-window-analysis.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(held_frame=held,probe_windows=windows)))

"""Select original frames across the first GC and HV expiry; post-run only."""
import argparse
import gzip
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/integration/perception'))
from audit_state_path_v1 import hv_origin
p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--bundle',type=Path,required=True);a=p.parse_args()
read=lambda name:json.loads((a.run/'capture'/name).read_text())
fault=read('native-drive-fault.json');gc=read('owner-gc.json')['cycles'][0]
lo=int(gc['completed_frame'])-2;hi=int(fault['held_hv']['sequence'])+4
end=int(gc['end']['wall_ns']);selected=[]
with gzip.open(a.run/'capture/trace.jsonl.gz','rt') as stream:
    for line in stream:
        record=json.loads(line);r=record['receipt'];frame=int(r['frame'])
        if frame>hi:break
        if frame<lo:continue
        path=record['state_path'];origin=hv_origin(r)
        selected.append(dict(frame=frame,receipt=r,state_path=path,hv_origin=origin))
        print(json.dumps(dict(frame=frame,normal=r['original_actual']['admitted_actual']['normal'],
            admitted_ms=(int(path['admitted']['wall_ns'])-end)/1e6,
            source_ms=(origin['source_ns']-end)/1e6,dependency_ms=(origin['dependency_ns']-end)/1e6,
            actuator_ms=(origin['actuator_source_ns']-end)/1e6,coil_ms=(origin['coil_source_ns']-end)/1e6,
            complete_ms=(int(path['complete']['wall_ns'])-end)/1e6,
            wait_reasons=path['owner_wait']['reasons'],last_ineligible=path['owner_wait']['last_ineligible'])))
assert len(selected)==hi-lo+1
result=dict(scope='original receipt and state-path fields; unchanged timestamps and verdict',
    gc=gc,first_fault=fault,fault_after_gc_ms=(fault['observed_ns']-end)/1e6,frames=selected)
target=a.bundle/'gc-recovery-frames.json'
if target.exists():assert json.loads(target.read_text())==result,'original excerpt must reproduce exactly'
else:target.write_text(json.dumps(result,indent=2)+'\n')

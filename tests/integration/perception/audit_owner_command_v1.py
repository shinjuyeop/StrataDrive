"""Decode retained failed10ms commands; a5ms margin is not a live success."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'carla'))
from audit_m7_wall_carla import wire,frame


def audit(capture):
    events=json.loads((capture/'events.json').read_text())
    transitions=[];previous=None
    for event in events:
        if event['op']!='wall_status':continue
        row=event['response'];state=(row['wall_wait'],row['wall_terminal'])
        if state!=previous:
            transitions.append(dict(observed_wall_ns=event['wall_ns'],frames=int(row['wall_frames']),
                                    reason=state[0],terminal=state[1]));previous=state
    rejection=next(t for t in transitions if t['reason']=='native_command_interval_or_causal')
    candidates=[e for e in events if e['op']=='native_get' and e['wall_ns']<=rejection['observed_wall_ns']
                and e['response'].get('native',{}).get('normal')]
    selected=candidates[-1];report=selected['response'];now=report['now_ns'];native=report['native']
    rows=[]
    for role,packet in enumerate(native['commands']):
        q=wire(packet,0 if role<2 else 1,role+2,5)
        epoch,token,sent,deadline,operation=q.get('IQQQI');command=frame(q,role,False)
        assert epoch==42 and operation==0 and q.get('B')==1
        parent=q.get('IIQQdddB');oldest,expiry=q.get('QQ')
        actual=frame(wire(native['actual'][role],0 if role<2 else 1,7,9),role,True,False)
        assert actual['causal']==command['seq'] and command['causal']==parent[1]
        assert oldest<=parent[2]<=command['source']<=actual['source']<=now
        assert expiry<=min(parent[3],command['source']+30000001,parent[2]+30000001,oldest+70000001)
        rows.append(dict(role=role,command_source_ns=command['source'],parent_source_ns=parent[2],
                         actual_source_ns=actual['source'],oldest_input_ns=oldest,exclusive_expiry_ns=expiry,
                         margin_10ms_plus_preview_ns=expiry-now-14000000,
                         margin_5ms_plus_preview_ns=expiry-now-9000000))
    assert all(r['margin_10ms_plus_preview_ns']<0 for r in rows)
    return dict(scope='original decoded command coverage at native observation; not exact server admission time or counterfactual driving',
                observed_native_ns=now,observed_query_end_ns=selected['wall_ns'],
                first_server_rejection=rejection,transitions=transitions,commands=rows,
                original_fail_preserved=True,driving_acceptance=False)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('capture',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=audit(a.capture);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

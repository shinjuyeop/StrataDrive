"""Check fixed-size owner wait/scheduling evidence without changing case verdicts."""
import argparse
import gzip
import json
from pathlib import Path
from audit_state_path_v1 import PHASES, quant

COUNTERS=('cpu_ns','voluntary','involuntary','minor_faults','major_faults')
REASONS=('unavailable','proof_unreadable','settlement','stopped','invalid','not_due','gap','protection','ineligible','staging','ready')
def stamp(value):
    value={k:int(v) for k,v in value.items()}
    if set(value)!=set(('wall_ns','processor','valid',*COUNTERS)) or value['valid']!=1:
        raise ValueError('complete valid owner thread observation')
    if min(value.values())<0 or value['wall_ns']<=0 or value['cpu_ns']<=0:
        raise ValueError('owner observation range')
    return value
def delta(begin,end):
    if end['wall_ns']<begin['wall_ns'] or any(end[k]<begin[k] for k in COUNTERS):
        raise ValueError('owner observation regressed')
    return {k:end[k]-begin[k] for k in ('wall_ns',*COUNTERS)}
def validate(path):
    scheduling=path['scheduling'];points=[];spans={}
    if set(scheduling)!=set(PHASES):raise ValueError('owner phase coverage')
    for name in PHASES:
        observed=stamp(scheduling[name]);original={k:int(v) for k,v in path[name].items()}
        if observed['cpu_ns']!=original['cpu_ns']:raise ValueError('original phase CPU identity')
        if name.startswith('acquired_'):
            if observed['wall_ns']<original['wall_ns']:raise ValueError('original acquisition bracket')
        elif observed['wall_ns']!=original['wall_ns']:raise ValueError('original phase wall identity')
        if points:spans[PHASES[len(points)-1]+'_to_'+name]=delta(points[-1],observed)
        points.append(observed)
    wait=path['owner_wait'];reasons={k:int(v) for k,v in wait['reasons'].items()}
    if set(reasons)!=set(REASONS) or min(reasons.values())<0 or reasons['ready']!=1:
        raise ValueError('one admitted pump and complete wait reasons')
    groups={}
    for name in ('active','idle','outside'):
        group=wait[name];totals={k:int(group[k]) for k in ('count','errors','wall_ns',*COUNTERS)}
        if totals['errors'] or min(totals.values())<0:raise ValueError('owner wait counter integrity')
        if totals['count']:
            longest=delta(stamp(group['longest_begin']),stamp(group['longest_end']))
            if any(longest[k]>totals[k] for k in longest):raise ValueError('longest wait exceeds aggregate')
        else:
            if any(totals.values()) or any(int(v) for v in group['longest_begin'].values()) or any(int(v) for v in group['longest_end'].values()):
                raise ValueError('empty wait aggregate contains observations')
        groups[name]=totals
    if sum(reasons.values())!=groups['active']['count'] or groups['idle']['count']!=groups['active']['count']-1:
        raise ValueError('pump result/idle call coverage')
    if not 0<=int(wait['requested_sleep_ns'])<=groups['idle']['count']*50_000:
        raise ValueError('unchanged bounded idle sleep request')
    if int(wait['reason_truncated']) or len(wait['last_ineligible'].encode())>95:
        raise ValueError('ineligible reason truncated')
    return dict(spans=spans,groups=groups,reasons=reasons,last_ineligible=wait['last_ineligible'])
def audit(run):
    totals={k:0 for k in REASONS};details={};rows=[]
    with gzip.open(run/'capture/trace.jsonl.gz','rt') as stream:
        for line in stream:
            record=json.loads(line);result=validate(record['state_path'])
            for k,v in result['reasons'].items():totals[k]+=v
            reason=result['last_ineligible']
            if reason:details[reason]=details.get(reason,0)+1
            rows.append(dict(frame=int(record['receipt']['frame']),ticket=int(record['receipt']['ticket']),
                normal=record['receipt']['original_actual']['native']['normal'],**result))
    if not rows:raise ValueError('no physical owner wait observations')
    return dict(status='PASS_OWNER_WAIT_INTEGRITY_ONLY',scope='thread counters cannot distinguish blocking from a particular kernel cause; original audits still required',
        receipts=len(rows),reasons=totals,last_ineligible_frames=details,
        per_receipt_wait={name:{metric:quant(r['groups'][name][metric] for r in rows) for metric in ('wall_ns','cpu_ns','voluntary','involuntary')} for name in ('active','idle','outside')},
        worst_outside=sorted(rows,key=lambda r:r['groups']['outside']['wall_ns'],reverse=True)[:12],
        worst_physics=sorted(rows,key=lambda r:r['spans']['before_tick_to_after_tick']['wall_ns'],reverse=True)[:12])
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:result=audit(a.run)
    except Exception as error:result=dict(status='FAIL',error=str(error).replace(str(a.run),'<run>'))
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('worst_outside','worst_physics')}))
    raise SystemExit(0 if result['status']=='PASS_OWNER_WAIT_INTEGRITY_ONLY' else 1)

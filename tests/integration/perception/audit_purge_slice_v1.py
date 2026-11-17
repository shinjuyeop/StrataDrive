"""Check declared incremental work and 1ms preview without changing physical acceptance."""
import argparse
import json
from pathlib import Path
from audit_admission_window_v1 import audit as admission_audit
from audit_owner_gc_v1 import declared_policy, declared_owner_cpus, validate
from audit_owner_wait_v1 import stamp, delta


def validate_purge(profile,owner_cpus=(2,3,10,11)):
    collections=validate(profile,False,owner_cpus)
    purge=profile['incremental_purge']
    if purge['enabled'] is not True or int(purge['budget_ns'])!=100_000 or int(purge['errors']):
        raise ValueError('declared bounded incremental work')
    rows=purge['cycles']
    if len(rows)!=len(collections):raise ValueError('every collection has purge observation')
    summaries=[]
    for i,(row,gc) in enumerate(zip(rows,collections)):
        if row['complete'] is not True:raise ValueError('purge must drain, not accumulate')
        work=row['work'];count=int(work['count'])
        if int(work['errors']):raise ValueError('invalid purge stamps')
        if not row['pending_at_collection_end']:
            if count:raise ValueError('no incremental work without pending purge')
            continue
        if count<1 or count!=int(row['last_frame'])-int(row['first_frame'])+1:
            raise ValueError('one incremental slice each engine frame until completion')
        first,last=stamp(row['first']),stamp(row['last'])
        span=delta(first,last)
        longest=delta(stamp(work['longest_begin']),stamp(work['longest_end']))
        if any(int(point['processor']) not in owner_cpus for point in (row['first'],row['last'],work['longest_begin'],work['longest_end'])):
            raise ValueError('purge owner CPU placement')
        if first['wall_ns']<gc['end']['wall_ns'] or int(work['wall_ns'])>span['wall_ns']:
            raise ValueError('purge work must follow its collection')
        if int(work['wall_ns'])<longest['wall_ns'] or int(work['cpu_ns'])<longest['cpu_ns']:
            raise ValueError('purge aggregate cannot omit longest work')
        if i+1<len(collections):
            if last['wall_ns']>=collections[i+1]['begin']['wall_ns']:
                raise ValueError('purge must complete before next collection')
            if collections[i+1]['completed_frame']-gc['completed_frame']!=12220:
                raise ValueError('original 61.1s / 5ms collection cadence')
        summaries.append(dict(slices=count,completion_span_ns=span['wall_ns'],work_ns=int(work['wall_ns']),
                              longest_slice_ns=longest['wall_ns']))
    return summaries


def audit(run,preview_reserve_ns=1_000_000):
    read=lambda p:json.loads((run/p).read_text())
    server=read('server.json')
    if preview_reserve_ns not in (300_000,1_000_000):raise ValueError('explicit purge preview reserve')
    recovery=preview_reserve_ns==300_000
    if server.get('owner_recovery_preview',False) is not recovery:
        raise ValueError('declared recovery preview selection')
    if server['argv']['owner'].count('-StrataM10RecoveryPreview')!=int(recovery) or '-StrataM10RecoveryPreview' in server['argv']['renderer']:
        raise ValueError('owner only recovery preview')
    if declared_policy(server) or server.get('owner_purge_slice') is not True:
        raise ValueError('explicit parallel purge slice candidate')
    if server['argv']['owner'].count('-StrataM10PurgeSlice')!=1 or '-StrataM10PurgeSlice' in server['argv']['renderer']:
        raise ValueError('owner only incremental scheduling')
    for point in ('binding','final_server'):
        if read('capture/result.json')[point].get('incremental_purge_slice') is not True:
            raise ValueError('actual server incremental scheduling readback')
        if read('capture/result.json')[point].get('recovery_preview',False) is not recovery:
            raise ValueError('actual recovery preview readback')
    profile=read('capture/owner-gc.json');rows=validate_purge(profile,declared_owner_cpus(server))
    if server['endurance_seconds']==300 and len(rows)!=4:raise ValueError('four completed periodic purges')
    result=admission_audit(run,preview_reserve_ns)
    result.update(status='PASS_PURGE_SLICE_INTEGRITY',purges=rows,requested_slice_ns=100_000,
                  scope='scheduling integrity only; requested slice is not a hard execution bound or physical acceptance')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:result=audit(a.run)
    except Exception as e:result=dict(status='FAIL',error=str(e).replace(str(a.run),'<run>'))
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    raise SystemExit(0 if result['status']=='PASS_PURGE_SLICE_INTEGRITY' else 1)

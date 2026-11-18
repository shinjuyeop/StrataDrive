"""Audit explicit 500us native polling without changing ECU or watch deadlines."""
import argparse
import csv
import json
from pathlib import Path
from audit_visual_tags_v1 import audit as original_audit
from audit_hv50_cache_v1 import validate as validate_hv_cache


def validate(server,capture,meta,paths):
    period=500_000
    if (server.get('native_service_us')!=500 or capture.get('native_service_us')!=500
            or capture['native_initial'].get('service_period_ns')!=period
            or meta.get('service_period_ns')!=period
            or not server.get('profile_state_path') or not capture.get('profile_state_path')):
        raise ValueError('matching explicit native service cadence')
    initial=meta['initial'];previous=None;count=0;skipped=0
    for row in paths:
        wake,begin,end=(int(row[k]) for k in ('wake_ns','read_begin_ns','proof_publish_ns'))
        if wake<=initial or (wake-initial)%period or begin<wake or end<begin:
            raise ValueError('absolute native service grid and actual observation order')
        if previous is None:
            if wake!=initial+period:raise ValueError('first native service slot')
        else:
            old_wake,old_end=previous
            if wake<=old_wake or wake<=old_end:raise ValueError('no catchup service or historical clock')
            skipped+=(wake-old_wake)//period-1
        previous=(wake,end);count+=1
    if not count:raise ValueError('native service evidence required')
    return dict(service_period_ns=period,observed_calls=count,skipped_slots=skipped,
                original_ecu_periods_and_watch_deadlines=True)


def audit(run):
    result=original_audit(run)
    read=lambda name:json.loads((run/name).read_text())
    server=read('server.json');capture=read('capture/result.json')
    if server.get('packaged_renderer'):raise ValueError('declared source renderer required')
    with (run/'capture/native-state-path.csv').open() as stream:
        cadence=validate(server,capture,read('capture/native.json'),csv.DictReader(stream))
    result.update(status='PASS_SERVICE_HALF_INTEGRITY',cadence=cadence,
        declared_policy=validate_hv_cache(server,capture,read('capture/paired/renderer/result.json')),
        scope='service cadence and original policy integrity; separate physical acceptance required')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:result=audit(a.run)
    except Exception as error:result=dict(status='FAIL',error=str(error).replace(str(a.run),'<run>'))
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    raise SystemExit(0 if result['status']=='PASS_SERVICE_HALF_INTEGRITY' else 1)

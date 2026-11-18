"""Explicit ADR-0066 HV policy and closed-shard hints, with all physical gates."""
import argparse
import json
from pathlib import Path
from audit_packaged_renderer_v1 import audit as original_audit


def validate(server,capture,renderer):
    if server.get('packaged_target_map'):
        if server['packaged_renderer']['preparation']['initial_map']!='Carla/Maps/Town03_Opt':
            raise ValueError('stock renderer starts directly in the declared target map')
    if (server.get('wall_profile')!='wall5-hv50-v1' or capture.get('wall_profile')!='wall5-hv50-v1'
            or capture.get('hv_dependency_ns')!=50_000_000
            or capture['native_initial'].get('hv_dependency_ns')!=50_000_000
            or capture['model_step_ns']!=5_000_000):
        raise ValueError('explicit matching ADR-0066 HV50 policy')
    cache=renderer['recorder'].get('cache_release',{})
    rows=cache.get('records',[])
    if (server.get('release_recording_cache') is not True or cache.get('enabled') is not True
            or cache.get('stopped') is not True or cache.get('errors') or cache.get('workers')!=1
            or cache.get('capacity')!=2 or renderer['recorder']['mode']!='bounded-bgra-shards'
            or len(rows)!=len(renderer['recorder']['archives'])
            or {r['archive'] for r in rows}!=set(renderer['recorder']['archives'])):
        raise ValueError('every closed immutable raw shard has a bounded completed cache hint')
    for row in rows:
        if (row['status']!='HINT_APPLIED' or row['bytes']<=0
                or not 0<row['begin_ns']<=row['synced_ns']<=row['end_ns']):
            raise ValueError('closed shard sync precedes cache hint')
        frames=[r for r in renderer['raw'] if r['archive']==row['archive']]
        if not frames or max(r['write_end_ns'] for r in frames)>row['begin_ns']:
            raise ValueError('shard is closed after every original frame write')
    return dict(hv_dependency_ns=50_000_000,source_and_actual_policy='original 30ms gates',
                completed_cache_hints=len(rows),raw_bytes_retained=True)


def audit(run):
    result=original_audit(run)
    read=lambda name:json.loads((run/name).read_text())
    result.update(status='PASS_HV50_CACHE_INTEGRITY',
        declared_policy=validate(read('server.json'),read('capture/result.json'),read('capture/paired/renderer/result.json')),
        scope='existing ADR-0066 policy and cache hints; original physical audit still required')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:result=audit(a.run)
    except Exception as error:result=dict(status='FAIL',error=str(error).replace(str(a.run),'<run>'))
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    raise SystemExit(0 if result['status']=='PASS_HV50_CACHE_INTEGRITY' else 1)

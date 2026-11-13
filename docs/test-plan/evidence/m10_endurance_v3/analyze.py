"""Post-run observations; this never replaces the frozen acceptance auditor."""
import csv
import gzip
import json
from pathlib import Path
import sys
import numpy as np

root=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(root/'tests/integration/carla'))
from audit_m7_wall_carla import wire

def quantiles(values):
    return dict(min=min(values),median=float(np.median(values)),p95=float(np.percentile(values,95)),max=max(values)) if values else None

cases=[]
for i in (1,2,3):
    name=f'normal-30s-{i:02d}';run=root/'build/m10-endurance-v3'/name;capture=run/'capture'
    read=lambda p:json.loads(p.read_text())
    result=read(capture/'result.json');meta=read(capture/'native.json');server=read(run/'server.json')
    renderer=read(capture/'paired/renderer/result.json');native=list(csv.DictReader((capture/'native.csv').open()))
    with gzip.open(capture/'trace.jsonl.gz','rt') as f:receipts=[json.loads(line)['receipt'] for line in f]
    starts=[int(r['physics_acquisition_begin_ns']) for r in receipts];ends=[int(r['physics_acquisition_end_ns']) for r in receipts]
    normal=sum(r['original_actual']['native']['normal'] for r in receipts)
    protected=sum(bool(int(r['original_actual']['native']['protection_since_ns'])) for r in receipts)
    first_fault=next((n for n in native if int(n['protection'])),None)
    first_violation=None;ages=[];previous=None
    for n in native:
        if int(n['armed']) and not int(n['protection']):
            for source in (n,previous):
                if source is not None and int(source['armed']):
                    dep=(int(n['now'])-int(source['hv_dependency']))/1e6
                    source_age=(int(n['now'])-int(source['hv_source']))/1e6
                    ages.append(dep)
                    if first_violation is None and (dep>30 or source_age>30):
                        first_violation=dict(now_ns=int(n['now']),source_age_ms=source_age,dependency_age_ms=dep,
                            preceding_sample=source is previous)
        previous=n
    ingress=[]
    for row in read(capture/'ingress.json'):
        entry=row['ingress']
        if entry['accepted']:continue
        decodes=[]
        for role,packet in enumerate(entry['actual']):
            try:wire(packet,0 if role<2 else 1,7,9);verdict='CRC/domain/route pass'
            except Exception as error:verdict=str(error)
            decodes.append(dict(role=role,bytes=None if packet is None else len(packet)//2,verdict=verdict))
        ingress.append(dict(at_ns=int(entry['at_ns']),observed_age_ms=(int(entry['at_ns'])-int(entry['observed_ns']))/1e6,packets=decodes))
    calls=renderer['inference'];overlap=[c for c in calls if min(starts)<=c['begin_ns']<max(ends)]
    images=[r for r in renderer['raw'] if min(starts)<=r['received_wall_ns']<max(ends)]
    resources=server['resources'];during=[r for r in resources if min(starts)<=r['wall_ns']<=max(ends)]
    raw=renderer['raw'];overflows=renderer['recorder']['overflow'];fault_time=int(first_fault['now']) if first_fault else None
    cases.append(dict(case=name,requested_seconds=30,verdict='FAIL',completed_intervals=len(receipts),
        model_seconds=len(receipts)*.005,physical_wall_span_seconds=(max(ends)-min(starts))/1e9,
        normal_intervals=normal,protected_intervals=protected,init_intervals=len(receipts)-normal-protected,
        first_fault=meta['first_fault'],first_fault_after_initial_ms=(fault_time-meta['initial'])/1e6 if fault_time else None,
        first_normal_hv_budget_violation=first_violation,max_normal_hv_dependency_age_ms=max(ages) if ages else None,
        failed_ingress=ingress,raw_frames=len(raw),inference_calls=len(calls),overlapping_calls=len(overlap),
        raw_callbacks_during_physics=len(images),scene_to_result_ms=quantiles([(c['end_ns']-c['original_acquisition_ns'])/1e6 for c in calls]),
        recorder=dict(stored_bytes=renderer['recorder']['stored_bytes'],peak_queue_frames=renderer['recorder']['peak_queue_frames'],
            overflow_frames=overflows,write_ms=quantiles([(r['write_end_ns']-r['write_begin_ns'])/1e6 for r in raw]),
            overflow_after_first_fault_ms=[(r['received_wall_ns']-fault_time)/1e6 for r in raw if r['frame'] in overflows] if fault_time else []),
        min_available_ram_gib=min(r['available_ram_bytes'] for r in resources)/1024**3,
        min_free_disk_gib=min(r['free_bytes']['/d'] for r in resources)/1024**3,
        measurement_resource_samples=len(during),
        peak_owned_process_rss_gib=max(sum(p['rss_bytes'] for p in r['processes']) for r in resources)/1024**3,
        renderer_shutdown_exit=server['shutdown']['renderer']['server_exit'],
        renderer_shutdown_forced=server['shutdown']['renderer'].get('forced_stop',False),
        original_ini_restored=server['restored_ini_sha256']==server['original_ini_sha256'],
        replay=read(root/f'build/m10-endurance-v3/{name}-replay/validation.json'),
        frozen_audit=read(Path(__file__).parent/name/'audit.json')))
summary=dict(schema='m10-endurance-observations-v1',acceptance='FAIL',cases=cases,
    conditional_300s='NOT_RUN: all three original 30s cases must pass',
    observations_only=True,accepted_perception_results=0,holdout_access=False,
    limitation='Physical span includes protection; shortened inference and one-second RSS do not prove endurance or absence of memory leaks')
(Path(__file__).parent/'observations.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))

#!/usr/bin/env python3
"""Recompute frame diagnostic metrics from original snapshots and host brackets."""
import argparse
import json
import math
from pathlib import Path


def distribution(values):
    values=sorted(values)
    return dict(count=len(values),mean_ms=sum(values)/len(values),
                p99_ms=values[math.ceil(.99*len(values))-1],max_ms=values[-1],
                over_30ms=sum(v>30 for v in values))


def analyze(path):
    result=json.loads((path/'result.json').read_text())
    server=json.loads((path/'server.json').read_text())
    if result['status']!='COMPLETE_DIAGNOSTIC':
        return dict(case=path.name,status='EXCLUDED_FAILED_ATTEMPT',result_status=result['status'],
                    server_status=server['status'],error=result.get('error'))
    rows=json.loads((path/'samples.json').read_text());start=result['start']
    if len(rows)!=result['ticks'] or not rows:raise ValueError('sample count')
    old_platform=start['platform_seconds'];old_sim=start['sim_seconds'];old_end=None
    gaps=[];roundtrips=[];arrivals=[]
    for i,r in enumerate(rows):
        if r['index']!=i or r['frame']!=start['frame']+i+1:raise ValueError('frame continuity')
        if abs(r['simulation_seconds']-old_sim-.01)>1e-6:raise ValueError('original 10ms step')
        if not r['begin_ns']<=r['end_ns']<=r['read_end_ns']:raise ValueError('host bracket')
        gap=(r['platform_seconds']-old_platform)*1000
        if gap<0 or abs(gap-r['platform_gap_ms'])>1e-9:raise ValueError('server clock interval')
        gaps.append(gap);roundtrips.append((r['end_ns']-r['begin_ns'])/1e6)
        if old_end is not None:arrivals.append((r['end_ns']-old_end)/1e6)
        old_platform=r['platform_seconds'];old_sim=r['simulation_seconds'];old_end=r['end_ns']
    if not result['ego_destroyed'] or result['cleanup_errors'] or result['remaining_owned_actors']:
        raise ValueError('owned actor cleanup')
    if result['restored_settings']!=result['original_settings']:raise ValueError('world restoration')
    measurements={k:distribution(v) for k,v in [('server_platform_gap',gaps),('tick_roundtrip',roundtrips),('client_arrival_gap',arrivals)]}
    for k,v in measurements.items():
        for name,value in v.items():
            if abs(value-result[k][name])>1e-8:raise ValueError('reported '+k+' '+name)
    images=json.loads((path/'sensors.json').read_text());streams={}
    timeline={r['frame']:r['simulation_seconds'] for r in rows}
    for name,items in images.items():
        samples=[s for s in items if s['frame'] in timeline]
        if len(samples)!=result['sensor_counts'][name]:raise ValueError('sensor count')
        for s in samples:
            if abs(s['timestamp']-timeline[s['frame']])>1e-6:raise ValueError('sensor source time')
        streams[name]=dict(count=len(samples),frame_residues=sorted(set(s['frame']%5 for s in samples)),
                           gaps=[b['frame']-a['frame'] for a,b in zip(samples,samples[1:]) if b['frame']-a['frame']!=5])
    wall=(rows[-1]['read_end_ns']-rows[0]['begin_ns'])/1e9
    return dict(case=path.name,status='VERIFIED_DIAGNOSTIC_ONLY' if server['status']=='COMPLETE_DIAGNOSTIC' else 'VERIFIED_SAMPLES_WITH_SERVER_FAILURE',
                server_status=server['status'],server_exit=server.get('server_exit'),backend=result['backend'],
                cameras=result['cameras'],render=result['render'],pace_ms=result.get('pace_ms',0),
                simulated_seconds=old_sim-start['sim_seconds'],wall_seconds=wall,
                rtf=(old_sim-start['sim_seconds'])/wall,measurements=measurements,sensors=streams,
                slow_frame_modulo5={str(i):sum(r['platform_gap_ms']>30 for r in rows if r['frame']%5==i) for i in range(5)},
                stationary_only=True,wall_driving_accepted=False)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('root',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    cases=[]
    for path in sorted(a.root.iterdir()):
        if not (path/'result.json').is_file() or not (path/'server.json').is_file():continue
        try:cases.append(analyze(path))
        except (ValueError,KeyError,TypeError) as e:cases.append(dict(case=path.name,status='AUDIT_FAIL',error=str(e)))
    out=dict(status='DIAGNOSTIC_COMPARISON',cases=cases,acceptance='no real-time or driving acceptance')
    a.output.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out))
    return int(any(r['status']=='AUDIT_FAIL' for r in cases))


if __name__=='__main__':raise SystemExit(main())

#!/usr/bin/env python3
"""Recompute timing/clock diagnostics; never labels wall freshness PASS."""
import argparse
import json
import math
from pathlib import Path


def check(ok,why):
    if not ok:raise ValueError(why)


def read(p):return [json.loads(s) for s in p.read_text().splitlines() if s]


def stats(v):
    x=sorted(v);check(bool(x),'empty observations')
    return {'n':len(x),'mean':sum(x)/len(x),'p95':x[math.ceil(.95*len(x))-1],
            'p99':x[math.ceil(.99*len(x))-1],'max':x[-1],'min':x[0]}


def clock_fit(rows):
    # If platform event belongs within this tick request/snapshot bracket,
    # all intervals constrain a constant Host-monotonic minus platform offset.
    lo=max(t['begin_ns']-round(t['platform_s']*1e9) for t in rows)
    hi=min(t['snapshot_end_ns']-round(t['platform_s']*1e9) for t in rows)
    return {'offset_lower_ns':lo,'offset_upper_ns':hi,'intersection_nonempty':lo<=hi,
            'width_ns':hi-lo,'interpretation':'diagnostic constant-offset consistency only; not acquisition provenance or clock qualification'}


def analyze_case(folder):
    r=json.loads((folder/'result.json').read_text());rows=read(folder/'ticks.jsonl');cams=read(folder/'cameras.jsonl')
    check(r['status']=='COLLECTED' and len(rows)==600,'incomplete case')
    for i,t in enumerate(rows):
        check(t['begin_ns']<=t['snapshot_end_ns']<=t['state_read_end_ns']<=t['consume_end_ns'],'timing order')
        check(abs(t['delta_s']-.01)<1e-6 and math.isfinite(t['platform_s']),'delta/platform')
        if i:check(t['frame']==rows[i-1]['frame']+1 and abs(t['sim_s']-rows[i-1]['sim_s']-.01)<1e-6 and t['platform_s']>rows[i-1]['platform_s'],'frame/time sequence')
    index={t['frame']:t for t in rows};main=rows[100:500]
    groups={s:sorted([p for p in cams if p['stream']==s],key=lambda p:p['frame']) for s in ('rgb','gt')}
    camera={}
    if r['mode'].startswith('camera'):
        for stream,packets in groups.items():
            check(len({p['frame'] for p in packets})==len(packets),'duplicate camera')
            for p in packets:
                check(p['frame'] in index and abs(p['sim_s']-index[p['frame']]['sim_s'])<1e-6,'camera source')
                check(p['width']==800 and p['height']==600,'camera format')
                if 'histogram' in p:check(sum(p['histogram'].values())==480000,'GT histogram')
            tail=[p['frame'] for p in packets if rows[50]['frame']<=p['frame']<=rows[99]['frame']]
            check(len(tail)==10 and all(b-a==5 for a,b in zip(tail,tail[1:])),'startup phase')
            expected=[t['frame'] for t in main if t['frame']%5==tail[0]%5]
            actual=[p['frame'] for p in packets if main[0]['frame']<=p['frame']<=main[-1]['frame']]
            check(actual==expected and len(actual)==80,'main camera loss/cadence')
            camera[stream]={'main_expected':80,'main_received':len(actual),
                            'startup_frame_gaps':[b['frame']-a['frame'] for a,b in zip(packets,packets[1:]) if b['frame']<main[0]['frame']]}
    else:check(not cams,'unexpected camera')
    check(not r['events'] and not r['remaining_owned'] and all(r['destroyed'].values()) and all(r['stopped'].values()) and r['callback_quiet'],'queue/cleanup')
    gaps=[(t['snapshot_end_ns']-rows[i-1]['snapshot_end_ns'])/1e6 for i,t in enumerate(rows) if 100<=i<500]
    elapsed=(main[-1]['consume_end_ns']-main[0]['begin_ns'])/1e9
    return {'status':'DIAGNOSTIC_COMPLETE','mode':r['mode'],'main_ticks':400,'main_sim_s':4.,'main_wall_s':elapsed,
            'RTF':4/elapsed,'completion_gap_ms':stats(gaps),'gaps_gt10ms':sum(x>10 for x in gaps),
            'gaps_gt30ms':sum(x>30 for x in gaps),
            'tick_rpc_ms':stats([(t['snapshot_end_ns']-t['begin_ns'])/1e6 for t in main]),
            'consume_ms':stats([(t['consume_end_ns']-t['state_read_end_ns'])/1e6 for t in main]),
            'camera':camera,'clock_offset_diagnostic':clock_fit(main),'wall_freshness':'NOT RUN',
            'queue_high_water':r['queue_high_water']}


def analyze(root):
    attempt=root/'matrix_TERM/attempt';s=json.loads((attempt/'summary.json').read_text())
    check(s['status']=='COLLECTED' and s['settings_before']==s['settings_after'] and not s['remaining_actors'],'suite/restore')
    result={'status':'DIAGNOSTIC_COMPLETE','cases':{c['name']:analyze_case(attempt/c['name']) for c in s['cases']}}
    w=json.loads((attempt/'wheel-clock.json').read_text());rows=w['rows'];check(w['status']=='COLLECTED' and len(rows)==120 and not w['remaining_vehicles'],'wheel probe')
    check(all(t['frame']==t['frame_after_rpc'] and len(t['pitch_deg'])==4 and all(math.isfinite(x) for x in t['pitch_deg']) for t in rows),'wheel coherence')
    pause=w['pause'];check(pause['before_frame']==pause['after_frame'] and pause['before_sim_s']==pause['after_sim_s'] and pause['before_platform_s']==pause['after_platform_s'] and pause['wall_ns']>=250000000,'pause')
    result['wheel']={'scope':w['scope'],'pitch_deg_by_wheel':[stats([t['pitch_deg'][i] for t in rows]) for i in range(4)],
                     'four_RPC_ms':stats([(t['wheel_end_ns']-t['wheel_begin_ns'])/1e6 for t in rows]),
                     'max_speed_mps':max(math.sqrt(sum(v*v for v in t['velocity_mps'])) for t in rows),
                     'max_horizontal_speed_mps':max(math.hypot(*t['velocity_mps'][:2]) for t in rows),
                     'max_vertical_speed_mps':max(abs(t['velocity_mps'][2]) for t in rows),
                     'clock_offset_diagnostic':clock_fit(rows),'pause':pause,
                     'angular_speed_and_slip_validation':'NOT RUN; no driven stimulus'}
    all_main=[t for c in s['cases'] for t in read(attempt/c['name']/'ticks.jsonl')[100:500]]
    result['whole_matrix_clock_fit']=clock_fit(all_main)
    result['shutdowns']={}
    for name in ('empty_TERM','empty_INT','matrix_TERM'):
        p=json.loads((root/name/'process.json').read_text());log=(root/name/'server.log').read_text(errors='replace')
        result['shutdowns'][name]={'exit':p['launcher_exit'],'signal11':'Signal 11 caught.' in log,
                                   'final':p.get('final'),'forced_kill':p.get('forced_kill',False)}
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);a=p.parse_args();result=analyze(a.run)
    (a.run/'analysis.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()

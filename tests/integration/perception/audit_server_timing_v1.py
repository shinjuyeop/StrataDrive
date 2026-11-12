"""Direct stage attribution from bounded server journals, not a GPU causal model."""
import argparse
import json
from pathlib import Path

PREFIX = 'STRATA_SERVER_TIMING_V1 '
END = 'STRATA_SERVER_TIMING_END_V1 '
STAGES = dict(launch={'engine_tick','tick_rate','game_tick','rhi_tick','frame_sync','core_ticker','deferred_commands'},
              carla={'pre_tick','post_tick','after_physics','world_snapshot','sensor_dispatch','pump_gap','pump_call'})


def require(condition, why):
    if not condition:raise ValueError(why)


def parse(text):
    rows=[];summaries={}
    for line in text.splitlines():
        if PREFIX in line:
            require(line.startswith(PREFIX), 'ambiguous timing prefix')
            row=json.loads(line[len(PREFIX):]);require(set(row)=={'component','stage','frame','begin','end','cpu_begin','cpu_end'},'timing fields')
            component=row['component'];require(component in STAGES and row['stage'] in STAGES[component],'stage')
            require(component not in summaries,'row after end')
            require(all(type(row[k]) is int and row[k]>=0 for k in ('frame','begin','end','cpu_begin','cpu_end')),'integer timing')
            require(0<row['begin']<=row['end'],'wall bracket')
            if row['stage'].startswith('pump_'):require(row['cpu_begin']==row['cpu_end']==0,'pump has no CPU sample')
            else:require(0<row['cpu_begin']<=row['cpu_end'] and row['cpu_end']-row['cpu_begin']<=row['end']-row['begin']+100000,'CPU bracket')
            rows.append(row)
        elif END in line:
            require(line.startswith(END),'ambiguous end prefix');row=json.loads(line[len(END):])
            require(set(row)=={'component','rows','overflow'} and row['component'] in STAGES,'end fields')
            require(row['component'] not in summaries and type(row['rows']) is int and 0<row['rows']<=8192 and type(row['overflow']) is int and row['overflow']==0,'complete bounded journal')
            summaries[row['component']]=row
    require(set(summaries)==set(STAGES),'both journals completed')
    for component, summary in summaries.items():
        part=[r for r in rows if r['component']==component]
        require(len(part)==summary['rows'],'journal row count')
        keys=[(r['stage'],r['frame'],r['begin'],r['end']) for r in part];require(len(keys)==len(set(keys)),'duplicate row')
    return rows


def audit(run):
    rows=parse((run/'server.log').read_text(errors='replace'))
    meta=json.loads((run/'capture/native.json').read_text());start=meta['initial']
    capture=json.loads((run/'capture/result.json').read_text())
    # Bound to the original active native session, before cleanup and shutdown.
    events=json.loads((run/'capture/events.json').read_text())
    end=next(e['wall_ns'] for e in events if e['op']=='pause')
    gaps=[r for r in rows if r['stage']=='pump_gap' and r['begin']>=start and r['end']<=end]
    require(gaps,'observed live pump gap')
    gap=max(gaps,key=lambda r:r['end']-r['begin'])
    overlaps=[]
    for r in rows:
        if r['stage'] in ('engine_tick','game_tick','pre_tick','pump_gap'):continue
        overlap=max(0,min(r['end'],gap['end'])-max(r['begin'],gap['begin']))
        if overlap:
            overlaps.append(dict(component=r['component'],stage=r['stage'],frame=r['frame'],begin=r['begin'],end=r['end'],
                                 duration_ns=r['end']-r['begin'],cpu_ns=r['cpu_end']-r['cpu_begin'],overlap_ns=overlap))
    overlaps.sort(key=lambda r:r['overlap_ns'],reverse=True)
    readback=[]
    for line in (run/'server.log').read_text(errors='replace').splitlines():
        if line.startswith('STRATA_READBACK_V1 '):
            r=json.loads(line.split(' ',1)[1]);readback.append(r)
    for r in readback:
        require(not r['error'] and not r['deferred'],'unchanged readback baseline')
        stages=('capture','render','copy','flush','query','worker','ready','lock','send','end')
        require(all(r[a]<=r[b] for a,b in zip(stages,stages[1:])),'readback order')
    return dict(journal_integrity='PASS',scope='one instrumented trial; no continuous driving or GPU internal causal claim',
                driving_acceptance=False,run_status=capture['status'],physical_intervals=capture['completed_physics'],
                journal_rows=len(rows),active_pump_gaps=len(gaps),largest_gap=gap,
                largest_gap_ns=gap['end']-gap['begin'],stage_overlaps=overlaps,readback=readback)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=audit(a.run);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

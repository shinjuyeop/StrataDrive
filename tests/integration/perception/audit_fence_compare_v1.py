"""Join original same-host brackets; retain per-condition failure verdicts."""
import argparse
import csv
import importlib.util
import json
from pathlib import Path

# Separate parser instance: the prior two-component auditor remains unchanged.
spec=importlib.util.spec_from_file_location('fence_outer_reader',Path(__file__).with_name('audit_server_timing_v1.py'))
reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
reader.STAGES=dict(reader.STAGES,engine_fence={'sync_inner','begin_fence','async_loading','fence_wait','sync_game_tasks'},
                  render_fence={'render_begin_fence','route_render_only','route_rhi','route_gpu','render_fence_wait',
                                'task_wait_rhi','task_wait_render','event_wait','wait_game_tasks'})


def require(condition,why):
    if not condition:raise ValueError(why)


def coverage(rows,stage,begin,end):
    spans=sorted((max(begin,r['begin']),min(end,r['end'])) for r in rows if r['stage']==stage and r['end']>begin and r['begin']<end)
    total=0;cursor=begin
    for left,right in spans:
        if right>max(left,cursor):total+=right-max(left,cursor)
        cursor=max(cursor,right)
    return total


def audit(run):
    outer=reader.audit(run);rows=reader.parse((run/'server.log').read_text(errors='replace'))
    result=json.loads((run/'capture/result.json').read_text());sensor=json.loads((run/'capture/sensors.json').read_text())
    condition=result['camera_condition'];require(condition in ('absent','2k') and sensor['camera_condition']==condition,'declared camera condition')
    require(result['rendering_enabled'] is True,'renderer enabled in both conditions')
    require(len(sensor['preparation_calls'])==3 and sensor['preparation']['state']=='READY','identical model preparation')
    if condition=='absent':
        require(not sensor['camera'] and not sensor['model_calls'] and not sensor['raw'] and not outer['readback'] and 'sensor_attributes' not in sensor,'no camera actor/data')
    else:
        attrs=sensor['sensor_attributes'];require(int(attrs['image_size_x'])==2560 and int(attrs['image_size_y'])==1536 and float(attrs['fov'])==90 and float(attrs['sensor_tick'])==.05 and attrs['role_name']=='m7_frame5' and attrs['enable_postprocess_effects'].lower()=='true','original2K camera')
    jobs=[{k:int(v) for k,v in row.items()} for row in csv.DictReader((run/'capture/native.csv').open())]
    fault=next((r['protection'] for r in jobs if r['protection']),0)
    start=json.loads((run/'capture/native.json').read_text())['initial'];end=jobs[-1]['now']
    active=[r for r in rows if start<=r['begin']<=r['end']<=end]
    gaps=[r for r in active if r['stage']=='pump_gap'];require(gaps,'pump gap during native service')
    gap=max(gaps,key=lambda r:r['end']-r['begin']);a,b=gap['begin'],gap['end']
    outer['largest_gap']=gap;outer['largest_gap_ns']=b-a;outer['active_pump_gaps']=len(gaps)
    outer.pop('stage_overlaps') # replaced below with union coverage; exclude cleanup RPCs
    stages=['frame_sync','begin_fence','sync_game_tasks','async_loading','fence_wait','render_fence_wait','task_wait_render','task_wait_rhi','event_wait','wait_game_tasks']
    covered={s:coverage(rows,s,a,b) for s in stages}
    sync=[r for r in rows if r['stage']=='sync_inner' and r['begin']<b and r['end']>a]
    routes=sorted({r['stage'] for r in rows if r['stage'].startswith('route_') and any(s['begin']<=r['begin']<=r['end']<=s['end'] for s in sync)})
    require(covered['event_wait']<=covered['task_wait_render']+covered['task_wait_rhi']<=covered['render_fence_wait']<=covered['fence_wait']<=covered['frame_sync'],'nested interval coverage')
    outer.update(camera_condition=condition,first_protection_ns=fault,armed_observed=any(r['armed'] for r in jobs),
                 binding_frame=int(result['binding']['frame']),native_calls=len(jobs),stage_union_ns=covered,selected_routes=routes,
                 camera_packets=len(sensor['camera']),model_calls=len(sensor['model_calls']),raw_packets=len(sensor['raw']),
                 native_end_ns=end,active_routes=sorted({r['stage'] for r in active if r['stage'].startswith('route_')}),
                 active_stage_max_ns={s:max((r['end']-r['begin'] for r in active if r['stage']==s),default=0) for s in stages})
    return outer


def compare(absent,camera):
    a,b=audit(absent),audit(camera)
    require(a['camera_condition']=='absent' and b['camera_condition']=='2k','declared pair order')
    servers=[json.loads((p/'server.json').read_text()) for p in (absent,camera)]
    require(servers[0]['freeze_sha256']==servers[1]['freeze_sha256'] and servers[0]['server_timing_build_sha256']==servers[1]['server_timing_build_sha256'],'same frozen binaries/sources')
    require(servers[0]['argv']==servers[1]['argv'] and all(s['attempts']==1 for s in servers),'identical renderer/server profile')
    def normalize(argv):
        result=[];skip=False
        for arg in argv:
            if skip:skip=False;continue
            if arg in ('--output','--wall-clock'):skip=True;continue
            if arg=='--camera-absent-control':continue
            result.append(arg)
        return result
    require(normalize(servers[0]['client_argv'])==normalize(servers[1]['client_argv']),'only camera actor differs')
    require(servers[0]['started_utc']<servers[1]['started_utc'],'declared attempt order')
    return dict(integrity='PASS',scope='one ordered diagnostic pair; not randomized performance/quality acceptance',
                driving_acceptance=False,conditions=[a,b],gap_difference_ns=b['largest_gap_ns']-a['largest_gap_ns'],
                event_wait_difference_ns=b['stage_union_ns']['event_wait']-a['stage_union_ns']['event_wait'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('absent',type=Path);p.add_argument('camera',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    report=compare(a.absent,a.camera);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

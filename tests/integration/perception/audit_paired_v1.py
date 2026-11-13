"""Rejoin original physics, actor scenes, renderer readbacks and diagnostic outputs."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import zlib
import numpy as np
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'carla'))
from audit_m7_wall_carla import audit as physical_audit
from audit_control_shadow_v1 import audit as shadow_audit
from physical_ai.perception.scene_capture_v1 import (
    ActorObservation,ReceiptSceneJoiner,catalog_digest,matrix,multiply,quaternion,
)
from physical_ai.perception.scene_mailbox_v1 import SceneBinding,ActorPose,decode
from physical_ai.perception.camera_resolution_v1 import decode as decode_detection
from physical_ai.perception.async_native_2k_v1 import MODEL_SHA256
from paired_fault_v1 import audit_crash_progress,audit_crash_cleanup
from endurance_profile_v1 import limits
from endurance_recording_v1 import RawReader
from evidence_io import json_rows


def require(value,why):
    if not value:raise ValueError(why)


def sha(data):return hashlib.sha256(data).hexdigest()


def audit(root):
    read=lambda p:json.loads((root/p).read_text())
    server=read('server.json');source=read('capture/paired/source.json')
    bounds=limits(server.get('endurance_seconds',0))
    renderer=read('capture/paired/renderer/result.json');data=read('capture/paired/catalog.json')
    catalog=data['catalog'];b=data['binding']
    if bounds['seconds']:
        require(server['condition']=='normal' and server['export_hz']==20 and
            source['endurance_seconds']==renderer['endurance_seconds']==read('capture/result.json')['endurance_seconds']==bounds['seconds'],
            'declared endurance duration and workload')
        require(read('capture/result.json')['binding']['endurance_frames']==bounds['frames'],'extended journal binding')
    for k in ('run','scene_sha256','model_sha256'):b[k]=bytes.fromhex(b[k])
    b['actor_ids']=tuple(b['actor_ids']);binding=SceneBinding(**b)
    require(catalog_digest(catalog)==binding.scene_sha256,'catalog binding')
    require(server['export_hz'] in (20,50) and catalog['export_period_ns']==source['export_period_ns']==1_000_000_000//server['export_hz'],
        'declared bounded observation rate')
    queries=source['query_timings']
    require(all(q['begin_ns']<=q['end_ns'] for q in queries) and
        all(a['end_ns']<=b['begin_ns'] for a,b in zip(queries,queries[1:])) and
        len(source['queries'])==sum(q['frame'] is not None for q in queries),'original receipt query brackets')
    require(read('capture/result.json')['paired_export_hz']==server['export_hz'],'client observation rate identity')
    preparation=catalog['actor_preparation']
    require(preparation==read('capture/result.json')['paired_actor_preparation']
        and preparation['world']==binding.world and preparation['ego_actor']==catalog['ego_id']
        and preparation['native_session_started'] is False and preparation['control_writes']==0,
        'pre-bind actor preparation identity')
    expected=multiply(preparation['ego_matrix'],matrix((8.,3.,1.),(0.,0.,0.,1.)))
    require(max(abs(expected[i][j]-preparation['walker_requested_matrix'][i][j]) for i in range(4) for j in range(4))<=1e-4,
        'walker placed relative to actual SDK ego pose')
    walker=next(x for x in catalog['actors'] if x['id']==preparation['walker_actor'])
    require(walker['blueprint'].startswith('walker.') and max(abs(walker['initial_pose']['position_m'][i]-expected[i][3]) for i in (0,1))<=1e-3,
        'actual walker horizontal position matches declared placement')
    physical=physical_audit(root/'capture');shadow=shadow_audit(root)
    require(physical['status']=='PASS_CASE_ONLY' and physical['receipts']==bounds['frames'],'original native physical acceptance')
    require(shadow['integrity']=='PASS' and shadow['accepted_results']==0 and shadow['model_calls']==0,'no diagnostic native publications')
    require(server['status']=='EXECUTED_REQUIRES_AUDIT' and server['attempts']==1,'finite original run')
    require(server['original_ini_sha256']==server['restored_ini_sha256'],'settings restoration')
    for role,v in server['shutdown'].items():
        crash=role=='renderer' and server['condition']=='stall-crash'
        require(v['server_exit']==(-9 if crash else 130) and not v.get('forced_stop'),'server exit')
        if crash:require(v.get('injected_crash') is True,'declared crash differs from failed graceful shutdown')
    require(not server.get('renderer_injected_forced_stop'),'original renderer exit deadline')
    require(not source['errors'] and not source['cleanup_errors'] and not source['joiner']['failed'],'source capture health')
    require(source['environment_after']==catalog['environment'],'source fixed environment')
    require(not renderer['errors'] and len(renderer['preparation'])==3,'diagnostic model preparation/errors')
    for report in (source,renderer):
        require(report['complete_visual_scene'] is False and report['perception_publications']==0,'visual scene remains unavailable')
    receipts={int(x['receipt']['frame']):x['receipt'] for x in json_rows(root/'capture/trace.jsonl')}
    observations={o['frame']:o for o in source['observations']}
    for receipt in source['queries']:require(receipts[int(receipt['frame'])]==receipt,'cached original receipt unchanged')
    scenes={}
    for e in source['exports']:
        scene=decode(bytes.fromhex(e['packet_hex']),binding);raw=observations[scene.frame]
        o=dict(raw);o['inventory']=tuple(o['inventory'])
        o['actors']=tuple(ActorPose(**{k:tuple(v) if isinstance(v,list) else v for k,v in p.items()}) for p in o['actors'])
        j=ReceiptSceneJoiner(binding,tuple(catalog['world_actor_ids']),catalog['ego_id'],int(receipts[scene.frame]['session']),catalog['geometry'])
        j.add(ActorObservation(**o))
        require(j.join(receipts[scene.frame],e['offered_wall_ns'])==scene,'same-frame source rejoin')
        require(e['acquired_begin_ns']==scene.acquired_begin_ns and e['acquired_end_ns']==scene.acquired_end_ns,'original scene age')
        scenes[scene.frame]=scene
    ticks={};clones={c['source_actor_id']:c for c in renderer['clones']}
    require(set(clones)==set(binding.actor_ids),'complete declared clone mapping')
    for t in renderer['ticks']:
        scene=scenes[t['physical_frame']]
        require(t['scene_sha256']==sha(bytes.fromhex(next(e['packet_hex'] for e in source['exports'] if e['frame']==scene.frame))),'rendered exact scene packet')
        require(scene.acquired_end_ns<=t['apply_begin_ns']<=t['apply_end_ns']<=t['tick_begin_ns']<=t['tick_end_ns'],'application/tick order')
        require(len(t['clone_readback'])==len(scene.actors),'all clones verified')
        for p,row in zip(scene.actors,t['clone_readback']):
            require(row['source_actor_id']==p.actor_id and row['clone_actor_id']==clones[p.actor_id]['clone_actor_id'],'clone identity')
            expected=matrix(p.position_m,p.quaternion_xyzw)
            require(max(abs(expected[i][k]-row['actual_transform_matrix'][i][k]) for i in range(4) for k in range(4))<=1e-4,'actual clone transform')
        ego=next(p for p in scene.actors if p.actor_id==catalog['ego_id']);p=catalog['camera_relative']
        expected=multiply(matrix(ego.position_m,ego.quaternion_xyzw),matrix((p['x'],p['y'],p['z']),quaternion(p['pitch'],p['yaw'],p['roll'])))
        require(max(abs(expected[i][k]-t['camera_world_matrix'][i][k]) for i in range(4) for k in range(4))<=1e-4,'actual camera calibration')
        ticks[t['renderer_frame']]=t
    images={};rgb_hashes=[];folder=root/'capture/paired/renderer'
    reader=RawReader(folder) if bounds['seconds'] else None
    for r in renderer['raw']:
        if reader:raw=reader.read(r)
        else:
            stored=(folder/r['path']).read_bytes();require(sha(stored)==r['stored_sha256'],'stored raw');raw=zlib.decompress(stored)
        require(len(raw)==2560*1536*4 and sha(raw)==r['bgra_sha256'],'raw BGRA')
        require(sha(Image.frombytes('RGB',(2560,1536),raw,'raw','BGRX').tobytes())==r['rgb_sha256'],'RGB exclusion')
        require(r['frame'] not in images,'unique actual camera callback')
        images[r['frame']]=r;rgb_hashes.append(r['rgb_sha256'])
    if reader:reader.close()
    require(len(images)==renderer['recorder']['offered'] and not renderer['recorder']['overflow'] and not renderer['recorder']['errors'],'all raw packets retained')
    mapped={}
    for m in renderer['mapped']:
        t=ticks[m['renderer_frame']];s=scenes[t['physical_frame']];r=images[m['renderer_frame']]
        require(m['renderer_source_ns']==t['renderer_source_ns']==r['source_ns'],'actual renderer frame/time')
        require(m['physical_frame']==s.frame and m['physical_source_ns']==s.source_ns and m['scene_sha256']==t['scene_sha256'],'unaltered physical provenance')
        require(m['original_acquisition_begin_ns']==s.acquired_begin_ns and m['original_acquisition_end_ns']==s.acquired_end_ns,'no scene age renewal')
        require(m['callback_received_ns']==r['received_wall_ns']>=t['tick_begin_ns'] and m['accepted_for_control'] is False,'actual unavailable image')
        mapped[m['renderer_frame']]=m
    starts=[int(r['physics_acquisition_begin_ns']) for r in receipts.values()]
    ends=[int(r['physics_acquisition_end_ns']) for r in receipts.values()]
    overlapping=0;ages=[]
    for call in renderer['inference']:
        m=mapped[call['renderer_frame']]
        require('error' not in call and call['accepted_for_control'] is False,'diagnostic call only')
        require(call['physical_frame']==m['physical_frame'] and call['scene_sha256']==m['scene_sha256'],'inference scene')
        require(call['original_acquisition_ns']==m['original_acquisition_begin_ns'] and call['callback_ns']==m['callback_received_ns']<=call['begin_ns']<=call['end_ns'],'inference original clock')
        require(call['model_sha256']==MODEL_SHA256,'frozen numerical model')
        item=renderer['numeric_raw'][call['raw_index']];path=folder/item['path']
        require(sha(path.read_bytes())==item['sha256'],'original model tensor hash')
        with np.load(path,allow_pickle=False) as values:decoded=decode_detection(dict(values),4)
        expected=[dict(class_id=d.class_id,score=d.score,box=[v*4 for v in d.box]) for d in decoded]
        require(call['detections']==expected,'retained tensors reproduce decoded detections')
        overlapping+=min(starts)<=call['begin_ns']<max(ends)
        ages.append((call['end_ns']-call['original_acquisition_ns'])/1e6)
    require(len(ticks)>=5 and len(mapped)>=3 and overlapping>=2,'actual simultaneous physics/rendering/inference')
    windows=[]
    if bounds['seconds']:
        require(renderer['recorder']['mode']=='bounded-zstd-shards' and renderer['recorder']['stopped']
            and renderer['recorder']['stored_bytes']<=bounds['stored_bytes'],'bounded lossless endurance recording')
        initial=min(starts)
        for second in range(0,bounds['seconds'],5):
            lower=initial+second*1_000_000_000;upper=lower+5_000_000_000
            count=sum(lower<=c['begin_ns']<upper for c in renderer['inference'])
            require(count>0,'inference continued in every five-second window')
            windows.append(dict(begin_seconds=second,inference_calls=count))
    fault_progress=None
    if server['condition']=='normal':
        require(renderer['status']=='EXECUTED_REQUIRES_AUDIT' and not renderer['cleanup_errors'] and source['renderer_client_exit']==0,'normal renderer lifecycle')
        require(not source['events'],'no undeclared fault')
    elif server['condition']=='stall-crash':
        fault_progress=audit_crash_progress(source['events'],starts,server['renderer_exit_observed_ns'])
        crash=source['events'][-1]
        require(server['renderer_injected_crash_ns']==crash['wall_ns'] and server['renderer_injected_exit_code']==-9,'actual declared crash')
        require(source['renderer_client_exit'] in (0,1),'finite renderer client after injected crash')
        if renderer.get('error'):require(renderer['error_wall_ns']>=crash['wall_ns'] and 'RuntimeError' in renderer['error'],'RPC error after declared crash')
        audit_crash_cleanup(renderer.get('dead_server_cleanup'),crash['wall_ns'],renderer['cleanup_begin_ns'],
            [renderer['session']['camera_id'],*[c['clone_actor_id'] for c in renderer['clones']]])
        require(not renderer['cleanup_errors'],'local cleanup after observed renderer death')
    else:
        require(server['condition']=='stall-exit','declared condition')
        events=source['events'];require([e['action'] for e in events]==['SIGSTOP','SIGCONT','SIGINT'],'declared fault actions')
        stop,resume,exit=events
        require(resume['wall_ns']-stop['wall_ns']>=250_000_000,'declared stall duration')
        require(sum(stop['wall_ns']<t<resume['wall_ns'] for t in starts)>10 and sum(t>exit['wall_ns'] for t in starts)>10,'physical progress through renderer faults')
        if renderer.get('error'):require(renderer['error_wall_ns']>=exit['wall_ns'] and 'RuntimeError' in renderer['error'],'RPC error only after declared exit')
        require(server['renderer_exit_observed_ns']-exit['wall_ns']<30_000_000_000,'original injected exit deadline')
    return dict(status='PASS_DIAGNOSTIC_CASE_ONLY',condition=server['condition'],physical=physical,shadow=shadow,
        exported_scenes=len(scenes),renderer_ticks=len(ticks),raw_images=len(images),mapped_images=len(mapped),
        inference_calls=len(renderer['inference']),overlapping_calls=overlapping,
        acquisition_to_result_ms=dict(min=min(ages),median=float(np.median(ages)),p95=float(np.percentile(ages,95)),max=max(ages)),
        accepted_perception_results=0,complete_visual_scene=False,fault_progress=fault_progress,
        endurance_seconds=bounds['seconds'],five_second_windows=windows,rgb_sha256=sorted(set(rgb_hashes)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:result=audit(a.run)
    except Exception as error:result=dict(status='FAIL',error=str(error))
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='rgb_sha256'}))
    raise SystemExit(0 if result['status']=='PASS_DIAGNOSTIC_CASE_ONLY' else 1)

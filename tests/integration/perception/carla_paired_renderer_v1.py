#!/usr/bin/env python3
"""Finite concurrent actor-root rendering and diagnostic inference; no ECU output."""
from dataclasses import asdict
from collections import deque
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
import traceback
import uuid
import zlib

import carla
import numpy as np
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.scene_capture_v1 import catalog_digest, matrix, multiply, quaternion
from physical_ai.perception.scene_mailbox_v1 import SceneBinding, ActorPose, SceneConsumer
from physical_ai.perception.carla_render_adapter_v1 import KinematicRenderer, spawn_clone
from physical_ai.perception.render_provenance_v1 import RenderSession, RenderAssociations, RenderAssociation
from physical_ai.perception.async_native_2k_v1 import BgraPacket
from physical_ai.perception.contract import FrameIdentity
from physical_ai.perception.staged_kernel_2k_v1 import StagedKernelBackend
from paired_scene_capture_v1 import environment
from renderer_lifecycle_v1 import hold,verify_hold
from native_memory_recorder_v1 import MemoryRecorder
from paired_fault_v1 import observed_process_exit
from endurance_profile_v1 import limits
from endurance_recording_v1 import ShardRecorder


def sha(data):return hashlib.sha256(data).hexdigest()


class DiagnosticInference:
    """One numerical owner, one pending latest image; result remains unavailable."""
    def __init__(self,args,world_id,report):
        self.args,self.world_id,self.report=args,world_id,report
        self.max_calls=limits(args.endurance_seconds)['camera_frames']
        self.condition=threading.Condition();self.pending=None;self.closed=False
        self.ready=threading.Event();self.replaced=0;self.raw=[]
        self.thread=threading.Thread(target=self.run,name='paired-diagnostic-inference',daemon=True);self.thread.start()

    def run(self):
        try:
            backend=StagedKernelBackend(self.args.detector,self.args.models,self.args.library,
                'f851fa22a24576d4e76fa2fa8749f3f4517d5ee625b64de390a360fd32fb0721',trace_capacity=max(4096,self.max_calls+3))
            self.report['providers']=backend.detector.session.get_providers()
            if os.environ.get('STRATADRIVE_ORT_PASSIVE_THREADS'):
                options=backend.detector.session.get_session_options()
                self.report['ort_thread_policy']={kind:options.get_session_config_entry(f'session.{kind}_op.allow_spinning') for kind in ('intra','inter')}
            # These private numeric identities never enter a publisher. Actual
            # camera/session provenance stays on RenderedImage and each report.
            gradient=np.empty((1536,2560,4),np.uint8)
            gradient[:,:,:3]=(np.arange(2560,dtype=np.uint16)%256)[None,:,None];gradient[:,:,3]=255
            for i in range(3):
                begin=time.monotonic_ns();backend.infer(BgraPacket(FrameIdentity(42,self.world_id,i+1,0),gradient.tobytes(),begin))
                self.report['preparation'].append(dict(begin_ns=begin,end_ns=time.monotonic_ns()))
            self.ready.set()
            original=backend.detector.raw
            def retained(feed):
                raw=original(feed);self.raw.append({k:v.copy() for k,v in raw.items()});return raw
            backend.detector.raw=retained
            while True:
                with self.condition:
                    self.condition.wait_for(lambda:self.closed or self.pending is not None)
                    if self.closed:break
                    image=self.pending;self.pending=None
                a=image.association;begin=time.monotonic_ns()
                row=dict(renderer_frame=a.renderer_frame,physical_frame=a.scene.frame,
                    original_acquisition_ns=a.scene.acquired_begin_ns,callback_ns=image.received_wall_ns,
                    begin_ns=begin,scene_sha256=a.scene_sha256,accepted_for_control=False,
                    unavailable_reason='complete_visual_scene_unavailable')
                try:
                    result=backend.infer(BgraPacket(FrameIdentity(42,self.world_id,a.renderer_frame,a.renderer_source_ns),
                                                   image.bgra,image.received_wall_ns))
                    row.update(detections=[asdict(d) for d in result.detections],model_sha256=result.model_sha256,
                        raw_index=len(self.raw)-1,preprocess_ns=result.preprocess_ns,inference_ns=result.inference_ns,
                        postprocess_ns=result.postprocess_ns)
                except Exception:row['error']=traceback.format_exc()
                row['end_ns']=time.monotonic_ns();self.report['inference'].append(row)
                if len(self.report['inference'])>=self.max_calls:raise ValueError('bounded diagnostic inference trace')
            self.report['backend_stages']=backend.stages
        except Exception:self.report['errors'].append(traceback.format_exc());self.ready.set()

    def offer(self,image):
        with self.condition:
            if self.closed:raise ValueError('closed diagnostic inference')
            if self.pending is not None:self.replaced+=1
            self.pending=image;self.condition.notify()

    def stop(self):
        with self.condition:self.closed=True;self.pending=None;self.condition.notify()
        self.thread.join(8)
        if self.thread.is_alive():raise TimeoutError('diagnostic inference stop')
        self.report['inference_pending_replaced']=self.replaced


def main(a):
    bounds=limits(a.endurance_seconds)
    wall_hz=int(os.environ.get('STRATADRIVE_RENDERER_WALL_HZ','0'))
    if wall_hz not in (0,10) or (wall_hz and not a.endurance_seconds):raise ValueError('declared renderer wall pacing')
    period=1_000_000_000//wall_hz if wall_hz else 0;next_tick=0
    a.output.mkdir(parents=True,exist_ok=False)
    data=json.loads(a.catalog.read_text());catalog=data['catalog'];b=data['binding']
    for key in ('run','scene_sha256','model_sha256'):b[key]=bytes.fromhex(b[key])
    b['actor_ids']=tuple(b['actor_ids']);binding=SceneBinding(**b)
    if catalog_digest(catalog)!=binding.scene_sha256:raise ValueError('source catalog digest')
    sock=socket.socket(fileno=a.socket_fd);sock.setblocking(False);consumer=SceneConsumer(sock,binding)
    report=dict(schema='m10-paired-renderer-v1',status='FAIL',condition=a.condition,
        mapped=[],ticks=[],raw=[],preparation=[],inference=[],errors=[],cleanup_errors=[],
        complete_visual_scene=False,perception_publications=0,endurance_seconds=a.endurance_seconds)
    client=carla.Client('127.0.0.1',a.port);client.set_timeout(2)
    world=sensor=history=inference=None;clones={};records=deque();consumed=0
    recorder=ShardRecorder(a.output,bounds['camera_frames'],bounds['stored_bytes']) if a.endurance_seconds else MemoryRecorder(a.output/'spill',96)
    lock=threading.Lock();accepting=True;held=None
    try:
        world=client.get_world();road=world.get_map()
        if road.name!=catalog['map'] or sha(road.to_opendrive().encode())!=catalog['xodr_sha256']:
            raise ValueError('renderer map differs from authoritative source')
        if any(x.type_id.startswith(('vehicle.','walker.','sensor.')) for x in world.get_actors()):
            raise ValueError('dedicated empty renderer')
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05;settings.no_rendering_mode=False
        world.apply_settings(settings)
        weather=carla.WeatherParameters()
        for name,value in catalog['environment']['weather'].items():setattr(weather,name,value)
        world.set_weather(weather)
        for light in world.get_actors().filter('traffic.traffic_light'):
            light.set_state(carla.TrafficLightState.Red);light.freeze(True)
        world.tick()
        if environment(world)!=catalog['environment']:raise ValueError('renderer frozen environment mismatch')
        for index,item in enumerate(catalog['actors']):
            bp=world.get_blueprint_library().find(item['blueprint'])
            for name,value in item['attributes'].items():
                if bp.has_attribute(name) and bp.get_attribute(name).is_modifiable:bp.set_attribute(name,value)
            p=item['initial_pose'];p={k:tuple(v) if isinstance(v,list) else v for k,v in p.items()}
            clone=spawn_clone(world,carla,bp,road.get_spawn_points()[index+3],ActorPose(**p))
            clones[item['id']]=clone
            if clone.type_id!=item['blueprint'] or dict(clone.attributes)!=item['attributes']:
                raise ValueError('clone blueprint/attributes differ from source')
        adapter=KinematicRenderer(client,world,carla,binding,clones)
        bp=world.get_blueprint_library().find('sensor.camera.rgb')
        attrs=dict(image_size_x='2560',image_size_y='1536',fov='90',sensor_tick='0.05',
                   role_name='m10_paired_diagnostic',enable_postprocess_effects='True')
        for name,value in attrs.items():bp.set_attribute(name,value)
        pose=catalog['camera_relative']
        sensor=world.spawn_actor(bp,carla.Transform(carla.Location(pose['x'],pose['y'],pose['z']),
            carla.Rotation(pose['pitch'],pose['yaw'],pose['roll'])),attach_to=clones[catalog['ego_id']])
        for name,value in attrs.items():
            actual=sensor.attributes[name]
            if name in ('role_name','enable_postprocess_effects'):
                if actual.lower()!=value.lower():raise ValueError('camera configuration readback')
            elif float(actual)!=float(value):raise ValueError('camera configuration readback')
        calibration=dict(attributes=dict(sensor.attributes),relative=pose)
        session=RenderSession(binding,uuid.uuid4().bytes,world.id,sensor.id,bytes.fromhex(sha(json.dumps(calibration,sort_keys=True).encode())))
        report['session']=dict(instance=session.renderer_instance.hex(),world=world.id,camera_id=sensor.id,
                               calibration=calibration,calibration_sha256=session.calibration_sha256.hex())
        report['clones']=[dict(source_actor_id=k,clone_actor_id=v.id,blueprint=v.type_id,attributes=dict(v.attributes)) for k,v in clones.items()]
        history=RenderAssociations(session)
        inference=DiagnosticInference(a,world.id,report)
        if not inference.ready.wait(30) or report['errors']:raise RuntimeError('diagnostic model preparation')
        def callback(image):
            begin=time.monotonic_ns()
            with lock:
                if not accepting:return
                row=dict(frame=image.frame,source_ns=round(image.timestamp*1e9),
                    received_wall_ns=begin,width=image.width,height=image.height)
                raw=bytes(image.raw_data)
                saved=recorder.offer(row,raw)
                if len(records)>=8:
                    report['errors'].append('bounded callback association queue full; raw retained')
                elif saved:records.append((row,raw))
                else:report['errors'].append('camera capacity exceeded; overflow retained')
        sensor.listen(callback)
        def drain():
            nonlocal consumed
            with lock:pending=list(records);records.clear();consumed+=len(pending)
            for row,raw in pending:
                image=history.consume(renderer_instance=session.renderer_instance,renderer_world=world.id,
                    camera_id=sensor.id,bgra=raw,**row)
                if image is not None:
                    x=image.association
                    report['mapped'].append(dict(renderer_frame=x.renderer_frame,renderer_source_ns=x.renderer_source_ns,
                        physical_frame=x.scene.frame,physical_source_ns=x.scene.source_ns,
                        original_acquisition_begin_ns=x.scene.acquired_begin_ns,
                        original_acquisition_end_ns=x.scene.acquired_end_ns,scene_sha256=x.scene_sha256,
                        callback_received_ns=image.received_wall_ns,accepted_for_control=False))
                    inference.offer(image)
        report['renderer_wall_hz']=wall_hz
        for _ in range(8):
            if period:time.sleep(max(0,(next_tick-time.monotonic_ns())/1e9))
            next_tick=time.monotonic_ns()+period;world.tick();drain()
        (a.output/'ready.json').write_text(json.dumps(dict(ready=True,world=world.id,camera=sensor.id))+'\n')
        deadline=time.monotonic()+bounds['renderer_seconds']
        while time.monotonic()<deadline:
            if report['errors'] or (a.endurance_seconds and recorder.failed()):raise RuntimeError('camera/inference diagnostic error')
            if period and time.monotonic_ns()<next_tick:
                time.sleep(.001);drain();continue
            scene=consumer.take(time.monotonic_ns())
            if consumer.closed:break
            if scene is None:time.sleep(.001);drain();continue
            begin=time.monotonic_ns();adapter.apply(scene);end=time.monotonic_ns()
            start=time.monotonic_ns();next_tick=start+period
            frame=world.tick();snapshot=world.get_snapshot();finish=time.monotonic_ns()
            if snapshot.frame!=frame:raise ValueError('actual renderer tick identity')
            readback=adapter.verify(scene,snapshot)
            ego=next(p for p in scene.actors if p.actor_id==catalog['ego_id'])
            expected_camera=multiply(matrix(ego.position_m,ego.quaternion_xyzw),
                matrix((pose['x'],pose['y'],pose['z']),quaternion(pose['pitch'],pose['yaw'],pose['roll'])))
            camera_matrix=sensor.get_transform().get_matrix()
            camera_error=max(abs(expected_camera[i][j]-camera_matrix[i][j]) for i in range(4) for j in range(4))
            if camera_error>1e-4:raise ValueError('same-frame camera calibration readback')
            association=RenderAssociation(session,scene,frame,round(snapshot.timestamp.elapsed_seconds*1e9),begin,end,start,finish)
            history.record(association)
            report['ticks'].append(dict(renderer_frame=frame,renderer_source_ns=association.renderer_source_ns,
                physical_frame=scene.frame,scene_sha256=association.scene_sha256,
                apply_begin_ns=begin,apply_end_ns=end,tick_begin_ns=start,tick_end_ns=finish,clone_readback=readback,
                camera_world_matrix=camera_matrix,camera_max_error=camera_error))
            consumer.release();drain()
        else:raise TimeoutError('paired renderer finite horizon')
        drain();report['status']='EXECUTED_REQUIRES_AUDIT'
    except Exception:
        report['error']=traceback.format_exc();report['error_wall_ns']=time.monotonic_ns()
        # Parent audit, not this exception handler, decides whether an RPC error
        # occurred after its declared renderer-exit injection.
    finally:
        report['cleanup_begin_ns']=time.monotonic_ns()
        dead=observed_process_exit(a.server_pidfd) if a.condition=='stall-crash' else None
        consumer.close()
        if inference:
            try:inference.stop()
            except Exception:report['cleanup_errors'].append(traceback.format_exc())
        if sensor and dead is None:
            try:sensor.stop()
            except Exception:report['cleanup_errors'].append(traceback.format_exc())
        with lock:accepting=False
        actors=[actor for actor in [sensor,*reversed(list(clones.values()))] if actor]
        if dead is not None:
            report['dead_server_cleanup']=dict(observed_exit_ns=dead,
                skipped_actor_ids=[actor.id for actor in actors],
                skipped_operations=['sensor.stop','actor.destroy','world.hold'])
        for actor in ([] if dead is not None else actors):
            if actor:
                try:
                    if not actor.destroy():raise ValueError('renderer actor destroy failed')
                except Exception:report['cleanup_errors'].append(traceback.format_exc())
        if world and dead is None:
            try:held=hold(world)
            except Exception:report['cleanup_errors'].append(traceback.format_exc())
        if not recorder.close():report['cleanup_errors'].append('raw recorder stop')
        report['recorder']=recorder.report()
        records.clear()
        if a.endurance_seconds:report['raw']=report['recorder']['records']
        for index,(row,raw) in enumerate([] if a.endurance_seconds else recorder.iter_raw()):
            path=f'{index:03d}-{row["frame"]}.bgra.z';stored=zlib.compress(raw,1);(a.output/path).write_bytes(stored)
            rgb=Image.frombytes('RGB',(2560,1536),raw,'raw','BGRX').tobytes()
            report['raw'].append(dict(**row,path=path,stored_sha256=sha(stored),bgra_sha256=sha(raw),rgb_sha256=sha(rgb)))
        if inference:
            report['numeric_raw']=[]
            for i,raw in enumerate(inference.raw):
                path=a.output/f'numeric-{i:03d}.npz';np.savez_compressed(path,**raw)
                report['numeric_raw'].append(dict(index=i,path=path.name,sha256=sha(path.read_bytes())))
        if held:
            try:report['quiescent_cleanup']=verify_hold(world,held)
            except Exception:report['cleanup_errors'].append(traceback.format_exc())
        report['consumer']=dict(received=consumer.received,expired=consumer.expired)
        os.close(a.server_pidfd)
        if report['cleanup_errors'] and report['status']=='EXECUTED_REQUIRES_AUDIT':report['status']='FAIL'
        (a.output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('status','error') if k in report}))
    return 0 if report['status']=='EXECUTED_REQUIRES_AUDIT' else 1


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--catalog',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--socket-fd',type=int,required=True);p.add_argument('--port',type=int,choices=(2300,),required=True)
    p.add_argument('--server-pidfd',type=int,required=True)
    p.add_argument('--endurance-seconds',type=int,choices=(0,30,300),default=0)
    p.add_argument('--condition',choices=('normal','stall-exit','stall-crash'),required=True)
    for name in ('detector','models','library'):p.add_argument('--'+name,type=Path,required=True)
    raise SystemExit(main(p.parse_args()))

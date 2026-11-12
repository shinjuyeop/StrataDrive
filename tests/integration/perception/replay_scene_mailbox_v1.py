"""Retained physical kinematics through the IPC prototype; no live renderer."""
import argparse
import hashlib
import json
from pathlib import Path
import uuid

from physical_ai.perception.scene_mailbox_v1 import (
    ActorPose,SceneBinding,SceneSnapshot,ScenePublisher,SceneConsumer,encode,socket_pair,
)


def replay(capture):
    result=json.loads((capture/'result.json').read_text());sensors=json.loads((capture/'sensors.json').read_text())
    binding=result['binding'];actor=int(binding['actor'])
    context=dict(scope='retained ego kinematics only; full render scene is not verified',map='Town03_Opt',
                 actor_ids=[actor],run=binding['run'],model_sha256=binding['model_sha256'])
    scene_hash=hashlib.sha256(json.dumps(context,sort_keys=True).encode()).digest()
    trusted=SceneBinding(42,uuid.UUID(binding['run']).bytes,sensors['source_clock'],int(binding['physics']['generation']),
                         result['model_step_ns'],scene_hash,bytes.fromhex(binding['model_sha256']),(actor,))
    snapshots=[]
    for line in (capture/'trace.jsonl').read_text().splitlines():
        row=json.loads(line);r=row['receipt'];p=r['physics']
        assert r['run']==binding['run'] and r['actor']==binding['actor'] and r['physics_generation']==binding['physics']['generation']
        assert r['interval_work_valid'] and r['inputs_cleared_after_physics'] and row['settlement'] is not None
        snapshots.append(SceneSnapshot(trusted,int(r['frame']),round(r['simulation_end_seconds']*1e9),
                         int(r['physics_acquisition_begin_ns']),int(r['physics_acquisition_end_ns']),
                         (ActorPose(actor,tuple(p['body_world_position_m']),tuple(p['body_quaternion_xyzw']),
                                    tuple(p['com_velocity_world_m_s']),tuple(p['angular_velocity_world_rad_s'])),)))
    assert len(snapshots)==400 and result['execution_profile']=='owner5ms'
    a,b=socket_pair();publisher=ScenePublisher(a,trusted);consumer=SceneConsumer(b,trusted)
    try:
        first,last=snapshots[0],snapshots[-1]
        assert publisher.offer(first,first.acquired_end_ns)
        assert consumer.take(first.acquired_end_ns)==first
        first_bytes=encode(consumer.active)
        for value in snapshots[1:]:assert publisher.offer(value,value.acquired_end_ns)
        assert publisher.sent==1 and publisher.pending==last and publisher.replaced==398
        assert encode(consumer.active)==first_bytes
        assert consumer.current(last.acquired_end_ns) is None # original first scene is now expired
        publisher.pump(last.acquired_end_ns)
        assert consumer.take(last.acquired_end_ns)==last
        assert encode(consumer.active)==encode(last)
        return dict(status='PASS',scope='original400-receipt IPC replay with paused consumer; no live renderer/physics concurrency claim',
                    source_snapshots=400,sent=publisher.sent,replaced_pending=publisher.replaced,
                    expired_active=consumer.expired,maximum_inflight=1,maximum_pending=1,
                    first_frame=first.frame,last_frame=last.frame,
                    first_acquisition_ns=first.acquired_begin_ns,last_acquisition_ns=last.acquired_begin_ns,
                    original_first_sha256=hashlib.sha256(first_bytes).hexdigest(),
                    original_last_sha256=hashlib.sha256(encode(last)).hexdigest(),
                    all_original_acquisition_ns=[s.acquired_begin_ns for s in snapshots],
                    render_scene_complete=False,driving_acceptance=False)
    finally:publisher.close();consumer.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('capture',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=replay(a.capture);a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='all_original_acquisition_ns'},indent=2))

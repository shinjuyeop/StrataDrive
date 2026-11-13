import copy
from dataclasses import replace
import math
import unittest
import uuid

from physical_ai.perception.scene_capture_v1 import (
    ActorObservation, ReceiptSceneJoiner, matrix, multiply, inverse, quaternion,
)
from physical_ai.perception.scene_mailbox_v1 import ActorPose, SceneBinding

BINDING=SceneBinding(42,bytes(range(16)),77,1,5_000_000,b's'*32,b'm'*32,(86,87))
BASE=1_000_000_000


def transform(position):
    return dict(translation_m=position,quaternion_xyzw=[0.,0.,0.,1.],scale=[1.,1.,1.])


def joiner():
    # The rigid body origin is one metre above the actor root.
    geometry=dict(valid=True,generation='1',body_world=transform([0.,0.,1.]),actor_world=transform([0.,0.,0.]))
    return ReceiptSceneJoiner(BINDING,(1,86,87),86,123,geometry)


def observation(frame):
    poses=tuple(ActorPose(i,(frame*.01,0.,0.),(0.,0.,0.,1.),(0.,)*3,(0.,)*3) for i in (86,87))
    return ActorObservation(77,frame,frame*5_000_000,5_000_000,
        BASE+frame*5_000_000+100,BASE+frame*5_000_000+200,(1,86,87),poses)


def receipt(frame):
    return dict(run=BINDING.run.hex(),session='123',actor='86',physics_generation='1',
        model_sha256=BINDING.model_sha256.hex(),model_step_ns='5000000',interval_work_valid=True,
        inputs_cleared_after_physics=True,frame=str(frame),simulation_end_seconds=frame*.005,
        physics_acquisition_begin_ns=str(BASE+frame*5_000_000),
        physics_acquisition_end_ns=str(BASE+frame*5_000_000+50),
        physics=dict(body_world_position_m=[frame*.01,0.,1.],body_quaternion_xyzw=[0.,0.,0.,1.]))


class SceneCaptureTests(unittest.TestCase):
    def test_unreal_uppercase_hyphenated_uuid_keeps_the_same_identity(self):
        j=joiner();o=observation(10);j.add(o);r=receipt(10)
        r['run']=str(uuid.UUID(bytes=BINDING.run)).upper()
        self.assertEqual(j.join(r,o.callback_end_ns).binding,BINDING)

    def test_join_preserves_original_time_and_body_to_actor_offset(self):
        j=joiner();o=observation(10);j.add(o)
        value=j.join(receipt(10),o.callback_end_ns+9_000_000)
        self.assertEqual(value.acquired_begin_ns,BASE+50_000_000)
        self.assertEqual(value.acquired_end_ns,o.callback_end_ns)
        self.assertEqual(value.actors,o.actors)
        self.assertTrue(value.fresh(value.acquired_begin_ns+99_999_999))
        self.assertFalse(value.fresh(value.acquired_begin_ns+100_000_000))
        self.assertIsNone(j.join(receipt(10),o.callback_end_ns+20_000_000))

    def test_exact_frame_missing_and_eviction_do_not_extrapolate(self):
        j=joiner()
        for i in range(1,67):j.add(observation(i))
        self.assertEqual(len(j.observations),64)
        self.assertEqual(j.evicted,2)
        self.assertIsNone(j.join(receipt(1),BASE+1_000_000_000))
        self.assertIsNone(j.join(receipt(67),BASE+1_000_000_000))
        self.assertEqual(j.join(receipt(66),BASE+1_000_000_000).frame,66)

    def test_receipt_corruptions_latch_instead_of_renewing_or_accepting(self):
        changes=[('run','f'*32),('actor','87'),('physics_generation','2'),('session','124'),
            ('model_sha256','f'*64),('model_step_ns','10000000'),('interval_work_valid',1),
            ('inputs_cleared_after_physics',False),('simulation_end_seconds',.051),
            ('physics_acquisition_end_ns',str(BASE+50_000_201))]
        bads=[]
        for k,v in changes:
            bad=receipt(10);bad[k]=v;bads.append(bad)
        bad=receipt(10);del bad['run'];bads.append(bad)
        bad=receipt(10);bad['physics']['body_world_position_m'][2]=0;bads.append(bad)
        bad=receipt(10);bad['physics']['body_world_position_m'][0]=float('nan');bads.append(bad)
        for bad in bads:
            with self.subTest(bad=bad):
                j=joiner();j.add(observation(10))
                with self.assertRaises(ValueError):j.join(bad,BASE+60_000_000)
                self.assertTrue(j.failed)
                with self.assertRaises(ValueError):j.join(receipt(10),BASE+60_000_000)

    def test_dynamic_inventory_world_or_time_drift_rejects(self):
        base=observation(11)
        for bad in (replace(base,world=78),replace(base,inventory=(1,2,86,87)),
                    replace(base,step_ns=10_000_000),replace(base,source_ns=base.source_ns+5000),
                    observation(10)):
            j=joiner();j.add(observation(10))
            with self.assertRaises(ValueError):j.add(bad)
            self.assertTrue(j.failed)

    def test_rigid_composition_and_carla_rotation_signs(self):
        m=matrix((1.,2.,3.),quaternion(0.,90.,0.))
        self.assertAlmostEqual(m[0][1],-1.)
        self.assertAlmostEqual(m[1][0],1.)
        self.assertAlmostEqual(matrix((0.,)*3,quaternion(90.,0.,0.))[2][0],1.)
        result=multiply(m,inverse(m))
        for i in range(4):
            for k in range(4):self.assertAlmostEqual(result[i][k],float(i==k))


if __name__=='__main__':unittest.main()

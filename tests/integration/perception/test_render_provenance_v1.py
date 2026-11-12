from dataclasses import replace
import math
import random
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from physical_ai.perception.scene_mailbox_v1 import ActorPose, SceneBinding, SceneSnapshot
from physical_ai.perception.render_provenance_v1 import (
    WIDTH, HEIGHT, MAX_TICK_ASSOCIATIONS, RenderSession, RenderAssociation,
    RenderAssociations, RenderedImage,
)
from physical_ai.perception.carla_render_adapter_v1 import carla_rotation, KinematicRenderer, spawn_clone
from physical_ai.perception.ipc_2k_v1 import encode as encode_perception

BASE = 1_000_000_000
BINDING = SceneBinding(42, b'p'*16, 77, 1, 5_000_000, b's'*32, b'm'*32, (86,))
SESSION = RenderSession(BINDING, b'r'*16, 77, 91, b'c'*32)  # IDs may collide between servers.
RAW = bytes(WIDTH * HEIGHT * 4)


def scene(frame=1):
    return SceneSnapshot(BINDING, frame, frame * 5_000_000, BASE + frame * 1000,
                         BASE + frame * 1000 + 1,
                         (ActorPose(86, (1., 2., 3.), (0., 0., 0., 1.), (0., 0., 0.), (0., 0., 0.)),))


def association(frame=10, physical=None):
    at = BASE + frame * 10_000
    return RenderAssociation(SESSION, physical or scene(), frame, frame * 10_000_000,
                             at, at + 1, at + 2, at + 100)


def callback(a, **changes):
    values = dict(renderer_instance=a.session.renderer_instance, renderer_world=a.session.renderer_world,
                  camera_id=a.session.camera_id, frame=a.renderer_frame, source_ns=a.renderer_source_ns,
                  received_wall_ns=a.tick_begin_ns + 1, width=WIDTH, height=HEIGHT, bgra=RAW)
    values.update(changes)
    return values


class RenderProvenanceTests(unittest.TestCase):
    def test_separate_clock_identity_and_callback_before_rpc_return(self):
        history = RenderAssociations(SESSION); a = association(); history.record(a)
        image = history.consume(**callback(a))
        self.assertIs(image.association, a)
        self.assertEqual(image.association.scene.source_ns, 5_000_000)
        self.assertEqual(image.association.renderer_source_ns, 100_000_000)
        self.assertLess(image.received_wall_ns, a.tick_end_ns)
        self.assertIsNone(history.consume(**callback(a)))

    def test_late_callback_never_refreshes_original_scene(self):
        a = association()
        image = RenderedImage(a, BASE + 101_000_000, WIDTH, HEIGHT, RAW)
        self.assertEqual(image.unavailable_reason(scene().source_ns, BASE + 101_000_000,
                                                  BASE + 101_000_000), 'original_scene_expired')

    def test_exclusive_scene_source_callback_and_state_expiry(self):
        a = association(); image = RenderedImage(a, a.tick_begin_ns + 1, WIDTH, HEIGHT, RAW)
        now = scene().acquired_begin_ns + 99_999_999
        self.assertEqual(image.unavailable_reason(scene().source_ns, now, now), 'complete_scene_export_unavailable')
        self.assertEqual(image.unavailable_reason(scene().source_ns, now+1, now+1), 'original_scene_expired')
        self.assertEqual(image.unavailable_reason(scene().source_ns+100_000_000, a.tick_end_ns, a.tick_end_ns), 'physical_source_expired')
        self.assertEqual(image.unavailable_reason(scene().source_ns, a.tick_end_ns-100_000_000, a.tick_end_ns), 'actual_state_expired')
        self.assertEqual(image.unavailable_reason(scene().source_ns-1, a.tick_end_ns, a.tick_end_ns), 'physical_source_future')
        self.assertEqual(image.unavailable_reason(scene().source_ns, a.tick_end_ns+1, a.tick_end_ns), 'clock_order')

    def test_incomplete_scene_cannot_be_enabled_by_a_flag_or_old_ipc(self):
        a = association(); image = RenderedImage(a, a.tick_end_ns, WIDTH, HEIGHT, RAW)
        self.assertEqual(image.unavailable_reason(scene().source_ns, a.tick_end_ns, a.tick_end_ns), 'complete_scene_export_unavailable')
        with self.assertRaises(TypeError):
            image.unavailable_reason(scene().source_ns, a.tick_end_ns, a.tick_end_ns, complete=True)
        with self.assertRaises(ValueError):
            encode_perception(image, sequence=1, epoch=42, source_clock=77, wall_clock=9, state_frame=1, sender_wall_ns=BASE)

    def test_bounded_history_drops_unmapped_old_callbacks(self):
        history = RenderAssociations(SESSION)
        for frame in range(10, 30):
            history.record(association(frame))
        self.assertEqual(len(history._pending), MAX_TICK_ASSOCIATIONS)
        self.assertEqual(history.evicted, 12)
        self.assertIsNone(history.consume(**callback(association(10))))
        self.assertIsNotNone(history.consume(**callback(association(29))))

    def test_wrong_camera_or_renderer_closes_mapping_even_with_same_world_id(self):
        for changes in (dict(renderer_instance=b'x'*16), dict(renderer_world=78), dict(camera_id=92), dict(source_ns=1)):
            history = RenderAssociations(SESSION); a = association(); history.record(a)
            with self.assertRaises(ValueError):
                history.consume(**callback(a, **changes))
            self.assertTrue(history.closed)
            self.assertFalse(history._pending)

    def test_no_frame_prediction_or_scene_rewrite(self):
        for bad in (association(10), association(9),
                    replace(association(11), scene=replace(scene(), acquired_end_ns=BASE+1002)),
                    association(11, replace(scene(2), source_ns=1))):
            history = RenderAssociations(SESSION); history.record(association())
            with self.assertRaises(ValueError):
                history.record(bad)
            self.assertTrue(history.closed)

    def test_original_source_gaps_are_allowed_and_retained(self):
        history = RenderAssociations(SESSION); history.record(association())
        newer = association(11, scene(20)); history.record(newer)
        self.assertEqual(history.consume(**callback(newer)).association.scene, scene(20))

    def test_invalid_layout_and_application_order_rejected(self):
        a = association()
        for values in (dict(apply_begin_ns=BASE), dict(tick_begin_ns=a.apply_begin_ns),
                       dict(renderer_frame=True), dict(renderer_source_ns=0)):
            with self.assertRaises(ValueError): replace(a, **values)
        for changes in (dict(width=640), dict(bgra=RAW[:-1]), dict(received_wall_ns=a.tick_begin_ns-1)):
            history = RenderAssociations(SESSION); history.record(a)
            with self.assertRaises(ValueError): history.consume(**callback(a, **changes))
        with self.assertRaises(ValueError): replace(SESSION, renderer_instance=BINDING.run)

    def test_close_discards_inflight_associations(self):
        history = RenderAssociations(SESSION); a = association(); history.record(a); history.close()
        self.assertIsNone(history.consume(**callback(a)))


def carla_matrix(rotation):
    p,y,r = (math.radians(x) for x in rotation)
    cp,sp,cy,sy,cr,sr = math.cos(p),math.sin(p),math.cos(y),math.sin(y),math.cos(r),math.sin(r)
    return ((cp*cy, cy*sp*sr-sy*cr, -cy*sp*cr-sy*sr),
            (cp*sy, sy*sp*sr+cy*cr, -sy*sp*cr+cy*sr),
            (sp, -cp*sr, cp*cr))


class RenderAdapterTests(unittest.TestCase):
    def test_spawn_collision_is_avoided_before_applying_unmodified_settled_pose(self):
        world, carla, blueprint, spawn_pose = Mock(), Mock(), Mock(), object()
        clone = world.spawn_actor.return_value
        def spawn(bp, pose):
            if pose is not spawn_pose: raise RuntimeError('Spawn failed because of collision at spawn position')
            return clone
        world.spawn_actor.side_effect = spawn
        result = spawn_clone(world, carla, blueprint, spawn_pose, scene().actors[0])
        self.assertIs(result, clone)
        self.assertEqual([x[0] for x in clone.mock_calls], ['set_simulate_physics','set_transform'])
        clone.set_simulate_physics.assert_called_once_with(False)
        carla.Location.assert_called_once_with(*scene().actors[0].position_m)
        world.tick.assert_not_called()
        clone.set_transform.side_effect = RuntimeError('application rejected')
        with self.assertRaises(RuntimeError): spawn_clone(world, carla, blueprint, spawn_pose, scene().actors[0])
        clone.destroy.assert_called_once()

    def test_quaternion_conversion_preserves_carla_matrix_including_gimbal_lock(self):
        rng = random.Random(42)
        quaternions = [(0.,0.,0.,1.), (0.,math.sqrt(.5),0.,math.sqrt(.5)),
                       (0.,-math.sqrt(.5),0.,math.sqrt(.5))]
        for _ in range(100):
            q = [rng.uniform(-1,1) for _ in range(4)]; n = math.sqrt(sum(x*x for x in q))
            quaternions.append(tuple(x/n for x in q))
        for x,y,z,w in quaternions:
            actual = carla_matrix(carla_rotation((x,y,z,w)))
            expected = ((1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)),
                        (2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)),
                        (2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)))
            for row, target in zip(actual, expected):
                for value, expected_value in zip(row, target):
                    self.assertAlmostEqual(value, expected_value, places=7)

    def adapter(self):
        carla = Mock(); client = Mock(); clone = Mock(id=1001)
        adapter = KinematicRenderer(client, SimpleNamespace(id=77), carla, BINDING, {86:clone})
        client.apply_batch_sync.return_value = [Mock(has_error=lambda:False)]
        return adapter, client, carla, clone

    def test_clone_mapping_disables_physics_and_does_not_tick_source(self):
        adapter, client, carla, clone = self.adapter(); adapter.apply(scene())
        clone.set_simulate_physics.assert_called_once_with(False)
        self.assertEqual(carla.command.ApplyTransform.call_args.args[0], 1001)
        self.assertIs(client.apply_batch_sync.call_args.args[1], False)
        with self.assertRaises(ValueError):
            KinematicRenderer(client, None, carla, BINDING, {87:clone})

    def test_partial_apply_failure_latches_renderer(self):
        adapter, client, carla, clone = self.adapter()
        client.apply_batch_sync.return_value = [Mock(has_error=lambda:True)]
        with self.assertRaises(ValueError): adapter.apply(scene())
        self.assertTrue(adapter.closed)

    def test_actual_transform_is_retained_and_drift_rejected(self):
        identity = [[1.,0.,0.,0.],[0.,1.,0.,0.],[0.,0.,1.,0.],[0.,0.,0.,1.]]
        adapter, client, carla, clone = self.adapter()
        carla.Transform.return_value.get_matrix.return_value = identity
        snap = Mock(id=77)
        snap.find.return_value.get_transform.return_value.get_matrix.return_value = identity
        result = adapter.verify(scene(), snap)
        self.assertEqual(result[0]['actual_transform_matrix'], identity)
        bad = [row[:] for row in identity]; bad[0][3] = .01
        snap.find.return_value.get_transform.return_value.get_matrix.return_value = bad
        with self.assertRaises(ValueError): adapter.verify(scene(), snap)
        self.assertTrue(adapter.closed)


if __name__ == '__main__': unittest.main()

from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from renderer_lifecycle_v1 import hold, verify_hold


class RendererLifecycleTests(unittest.TestCase):
    def world(self):
        world = Mock(id=77)
        world.get_settings.return_value = SimpleNamespace(synchronous_mode=True,fixed_delta_seconds=.05)
        world.get_snapshot.return_value = SimpleNamespace(id=77,frame=100,timestamp=SimpleNamespace(elapsed_seconds=5.))
        return world

    def test_holds_actual_final_frame_without_mutation_or_implicit_tick(self):
        world=self.world(); held=hold(world,lambda:1000)
        result=verify_hold(world,held,lambda:2000)
        self.assertEqual((result['frame'],result['source_ns']),(100,5_000_000_000))
        self.assertTrue(result['frame_unchanged'])
        world.apply_settings.assert_not_called(); world.tick.assert_not_called()

    def test_rejects_advanced_world_and_clock_regression(self):
        for field,value in (('id',78),('frame',101)):
            world=self.world(); held=hold(world,lambda:1000)
            setattr(world.get_snapshot.return_value,field,value)
            with self.assertRaises(ValueError): verify_hold(world,held,lambda:2000)
        world=self.world();held=hold(world,lambda:1000)
        with self.assertRaises(ValueError): verify_hold(world,held,lambda:999)

    def test_refuses_async_or_different_step_instead_of_reconfiguring(self):
        for settings in (SimpleNamespace(synchronous_mode=False,fixed_delta_seconds=.05),
                         SimpleNamespace(synchronous_mode=True,fixed_delta_seconds=.01)):
            world=self.world();world.get_settings.return_value=settings
            with self.assertRaises(ValueError):hold(world)
            world.apply_settings.assert_not_called()


if __name__=='__main__':unittest.main()

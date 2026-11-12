import unittest
from unittest.mock import Mock
from control_shadow_capture_v1 import Capture


class ShadowCleanupTests(unittest.TestCase):
    def setUp(self):
        self.capture = Capture.__new__(Capture)
        self.capture.sensor = Mock(id=87)
        self.capture.world = Mock()
        self.capture.report = {}

    def test_live_native_ownership_prevents_destroy_request(self):
        with self.assertRaisesRegex(RuntimeError, "closed native ownership"):
            self.capture.destroy()
        self.capture.world.get_actor.assert_not_called()
        self.capture.sensor.destroy.assert_not_called()

    def test_parent_close_already_removed_camera(self):
        self.capture.world.get_actor.return_value = None
        self.capture.destroy(ownership_released=True)
        self.capture.sensor.destroy.assert_not_called()
        self.assertEqual(self.capture.report["camera_cleanup"], "absent after parent close")

    def test_remaining_camera_destroyed_after_owner_close(self):
        self.capture.sensor.destroy.return_value = True
        self.capture.destroy(ownership_released=True)
        self.capture.sensor.destroy.assert_called_once_with()

    def test_failed_destroy_is_still_reported(self):
        self.capture.sensor.destroy.return_value = False
        with self.assertRaisesRegex(RuntimeError, "failed after ownership release"):
            self.capture.destroy(ownership_released=True)


if __name__ == "__main__":
    unittest.main()

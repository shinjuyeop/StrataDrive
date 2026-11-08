import unittest
from physical_ai.perception.camera import CameraClock, BgraCameraIngress
from physical_ai.perception.contract import WIDTH, HEIGHT, LIFETIME_NS
from physical_ai.perception.worker import LatestFrameWorker
from test_perception import FakeBackend


class CameraTests(unittest.TestCase):
    attributes = dict(
        image_size_x="640", image_size_y="384", fov="90", sensor_tick="0.05"
    )

    def setUp(self):
        self.clock = CameraClock(7)
        self.clock.update(1, 50_000_000)
        self.wall = 1_000_000_000
        self.backend = FakeBackend()
        self.worker = LatestFrameWorker(self.backend, self.clock.now, lambda: self.wall)
        self.assertTrue(self.worker.start_session(1, 7, 0))
        self.ingress = BgraCameraIngress(
            self.worker, 1, 7, self.attributes, lambda: self.wall
        )
        self.raw = bytearray([1, 2, 3, 255]) * WIDTH * HEIGHT
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.ingress.close()
        self.backend.release.set()
        self.assertTrue(self.worker.close())

    def offer(self, number=1, stamp=0.05, raw=None):
        return self.ingress.offer(
            number, stamp, WIDTH, HEIGHT, self.raw if raw is None else raw
        )

    def test_copy_rgb_order_and_source_identity(self):
        self.assertTrue(self.offer())
        self.raw[:] = bytes(len(self.raw))
        packet, accepted = self.ingress.pump(self.clock)
        self.assertTrue(accepted)
        self.assertEqual(packet.camera().rgb[:6], bytes([3, 2, 1, 3, 2, 1]))
        self.assertEqual(packet.identity.source_ns, 50_000_000)
        self.assertEqual(packet.received_wall_ns, self.wall)

    def test_early_callback_waits_for_observed_tick_and_latest_only(self):
        self.assertTrue(self.offer(2, 0.06))
        self.assertIsNone(self.ingress.pump(self.clock))
        self.assertTrue(self.offer(3, 0.07))
        self.clock.update(2, 60_000_000)
        self.clock.update(3, 70_000_000)
        packet, accepted = self.ingress.pump(self.clock)
        self.assertTrue(accepted)
        self.assertEqual(packet.identity.frame, 3)
        self.assertEqual(self.ingress.status()["counters"]["overwritten"], 1)

    def test_forged_timestamp_cannot_be_replaced_with_snapshot_timestamp(self):
        self.assertTrue(self.offer(stamp=0.049))
        self.assertFalse(self.ingress.pump(self.clock)[1])
        self.assertEqual(self.worker.status()["counters"]["submitted"], 0)

    def test_ingress_wait_counts_toward_original_wall_budget(self):
        self.offer()
        self.wall += LIFETIME_NS
        self.assertFalse(self.ingress.pump(self.clock)[1])

    def test_invalid_camera_clears_pending_and_inflight(self):
        self.offer()
        self.ingress.pump(self.clock)
        self.assertTrue(self.backend.entered.wait(2))
        self.assertFalse(self.offer(2, 0.06, b"broken"))
        self.backend.release.set()
        self.assertTrue(self.worker.drain())
        self.assertIsNone(self.worker.snapshot())
        self.assertEqual(self.worker.status()["counters"]["obsolete"], 1)

    def test_replay_nonfinite_timestamp_and_layout_rejected(self):
        self.assertTrue(self.offer())
        self.assertFalse(self.offer())
        for stamp in (float("nan"), float("inf"), -1, True):
            self.assertFalse(self.offer(2, stamp))
        self.assertFalse(self.ingress.offer(2, 0.06, True, HEIGHT, self.raw))
        self.assertFalse(self.offer(2, 0.06, b""))

    def test_close_drops_pending_and_future_callbacks(self):
        self.offer()
        self.ingress.close()
        self.assertFalse(self.offer(2, 0.06))
        self.assertIsNone(self.ingress.pump(self.clock))
        self.assertEqual(self.ingress.status()["counters"]["cancelled"], 1)

    def test_receipt_clock_exception_invalidates_instead_of_escaping_callback(self):
        self.offer()

        def unavailable():
            raise RuntimeError("clock unavailable")

        self.ingress._wall_now = unavailable
        self.assertFalse(self.offer(2, 0.06))
        self.assertIsNone(self.ingress.pump(self.clock))
        self.assertEqual(self.worker.status()["counters"]["invalidated"], 1)

    def test_clock_failure_latches_and_old_history_is_bounded(self):
        for n in range(2, 140):
            self.clock.update(n, 40_000_000 + n * 10_000_000)
        self.assertTrue(self.offer())
        self.assertFalse(self.ingress.pump(self.clock)[1])
        with self.assertRaises(ValueError):
            self.clock.update(141, 1_450_000_000)
        with self.assertRaises(ValueError):
            self.clock.now()
        with self.assertRaises(ValueError):
            self.clock.update(140, 1_440_000_000)

    def test_calibration_mismatch_does_not_create_ingress(self):
        for attrs in (
            {},
            dict(self.attributes, fov="100"),
            dict(self.attributes, sensor_tick="nan"),
        ):
            with self.assertRaises(ValueError):
                BgraCameraIngress(self.worker, 1, 7, attrs)


if __name__ == "__main__":
    unittest.main()

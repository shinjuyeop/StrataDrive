import unittest

from physical_ai.perception.contract import LIFETIME_NS
from physical_ai.perception.preparation import PREPARATION_BUDGET_NS, probe_frame
from physical_ai.perception.worker import LatestFrameWorker
from physical_ai.perception.yolox import image_health
from test_perception import frame, result, FakeBackend


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.wall = 1_000_000_000
        self.source = 50_000_000
        self.backend = FakeBackend()
        self.worker = LatestFrameWorker(
            self.backend,
            lambda: self.source,
            lambda: self.wall,
            require_preparation=True,
        )
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.backend.release.set()
        self.assertTrue(self.worker.close())

    def begin(self):
        self.assertTrue(self.worker.prepare())
        self.assertTrue(self.backend.entered.wait(2))

    def finish(self):
        self.backend.release.set()
        self.assertTrue(self.worker.drain())
        return self.worker.status()["preparation"]

    def test_probe_is_deterministic_nonflat_and_not_sensor_input(self):
        self.assertEqual(probe_frame(1).rgb, probe_frame(2).rgb)
        self.assertGreater(image_health(probe_frame(1))["luma_std"], 2)

    def test_explicit_preparation_then_explicit_init_and_no_probe_publication(self):
        self.assertFalse(self.worker.wait_ready(0))
        self.assertFalse(self.worker.start_session(1, 7, 0))
        self.assertFalse(self.worker.submit(frame()))
        self.begin()
        self.assertFalse(self.worker.start_session(1, 7, 0))
        self.assertFalse(self.worker.wait_ready(0))
        self.assertIsNone(self.worker.snapshot())
        report = self.finish()
        self.assertEqual(report["state"], "READY")
        self.assertEqual(len(report["calls"]), 3)
        self.assertEqual(self.worker.status()["counters"]["started"], 0)
        self.assertFalse(self.worker.prepare())
        self.assertTrue(self.worker.wait_ready(0))
        self.assertIsNone(self.worker.snapshot())
        self.assertTrue(self.worker.start_session(1, 7, 0))
        self.assertTrue(self.worker.submit(frame()))
        self.assertTrue(self.worker.drain())
        self.assertIsNotNone(self.worker.snapshot())

    def test_cold_cost_is_preserved_and_allowed_only_inside_startup_budget(self):
        self.begin()
        self.wall += 300_000_000
        report = self.finish()
        self.assertEqual(report["state"], "READY")
        self.assertEqual(report["calls"][0]["elapsed_wall_ns"], 300_000_000)
        self.assertEqual(
            report["finished_wall_ns"] - report["started_wall_ns"], 300_000_000
        )

    def test_deadline_latches_while_backend_stuck_and_late_completion_cannot_reopen(
        self,
    ):
        self.begin()
        self.wall += PREPARATION_BUDGET_NS
        self.assertFalse(self.worker.wait_ready(0))
        self.assertEqual(self.worker.status()["preparation"]["state"], "FAILED")
        self.assertTrue(self.worker.status()["busy"])
        self.assertFalse(self.worker.start_session(1, 7, 0))
        report = self.finish()
        self.assertEqual(report["state"], "FAILED")
        self.assertEqual(len(report["calls"]), 1)
        self.assertFalse(self.worker.prepare())

    def test_slow_settled_call_fails_instead_of_averaging_away(self):
        calls = []

        def infer(camera):
            calls.append(camera)
            self.wall += LIFETIME_NS
            return result(camera)

        self.backend.infer = infer
        self.assertTrue(self.worker.prepare())
        self.assertTrue(self.worker.drain())
        self.assertFalse(self.worker.wait_ready(0))
        self.assertEqual(len(calls), 2)
        self.assertEqual(
            self.worker.status()["preparation"]["error"], "settled probe deadline"
        )

    def test_failure_and_identity_rewrite_fail_closed(self):
        self.backend.rewrite = True
        self.begin()
        report = self.finish()
        self.assertEqual(report["state"], "FAILED")
        self.assertIn("identity", report["error"])
        self.assertFalse(self.worker.start_session(1, 7, 0))

    def test_clock_regression_during_prepare_is_latched(self):
        self.begin()
        self.wall -= 1
        self.assertEqual(self.worker.status()["preparation"]["state"], "FAILED")
        self.wall += 1
        self.assertEqual(self.finish()["state"], "FAILED")

    def test_close_during_probe_records_late_return_without_ready(self):
        self.begin()
        self.assertFalse(self.worker.close(0))
        self.assertEqual(self.worker.status()["preparation"]["state"], "CANCELLED")
        self.assertFalse(self.worker.status()["stopped"])
        self.assertEqual(self.finish()["state"], "CANCELLED")
        self.assertFalse(self.worker.wait_ready(0))

    def test_status_returns_copy(self):
        self.begin()
        self.finish()["calls"].clear()
        self.assertEqual(len(self.worker.status()["preparation"]["calls"]), 3)


class WallIngressTests(unittest.TestCase):
    def test_receipt_queue_plus_inference_reaches_deadline_even_when_source_paused(
        self,
    ):
        wall = [1_000_000_000]
        backend = FakeBackend()
        worker = LatestFrameWorker(backend, lambda: 50_000_000, lambda: wall[0])
        self.addCleanup(worker.close)
        self.addCleanup(backend.release.set)
        self.assertTrue(worker.start_session(1, 7, 0))
        self.assertTrue(
            worker.submit(frame(), received_wall_ns=wall[0] - LIFETIME_NS + 1)
        )
        self.assertTrue(backend.entered.wait(2))
        wall[0] += 1
        backend.release.set()
        self.assertTrue(worker.drain())
        self.assertIsNone(worker.snapshot())
        self.assertEqual(worker.status()["counters"]["late"], 1)

    def test_receipt_time_includes_queue_and_snapshot_expires_when_source_pauses(self):
        wall = [1_000_000_000]
        backend = FakeBackend()
        worker = LatestFrameWorker(backend, lambda: 50_000_000, lambda: wall[0])
        self.addCleanup(worker.close)
        self.addCleanup(backend.release.set)
        self.assertTrue(worker.start_session(1, 7, 0))
        backend.release.set()
        receipt = wall[0] - LIFETIME_NS + 1
        self.assertTrue(worker.submit(frame(), received_wall_ns=receipt))
        self.assertTrue(worker.drain())
        self.assertIsNotNone(worker.snapshot())
        wall[0] += 1
        self.assertIsNone(worker.snapshot())

    def test_old_future_and_boolean_receipt_are_rejected(self):
        worker = LatestFrameWorker(None, lambda: 50_000_000, lambda: 1_000_000_000)
        self.addCleanup(worker.close)
        self.assertTrue(worker.start_session(1, 7, 0))
        for stamp in (900_000_000, 1_000_000_001, True, -1):
            self.assertFalse(worker.submit(frame(), received_wall_ns=stamp))

    def test_adapter_invalidation_obsoletes_inflight_result_and_new_frame_recovers(
        self,
    ):
        backend = FakeBackend()
        source = [50_000_000]
        worker = LatestFrameWorker(backend, lambda: source[0])
        self.addCleanup(worker.close)
        self.addCleanup(backend.release.set)
        self.assertTrue(worker.start_session(1, 7, 0))
        self.assertTrue(worker.submit(frame()))
        self.assertTrue(backend.entered.wait(2))
        worker.invalidate("camera malformed")
        backend.release.set()
        self.assertTrue(worker.drain())
        self.assertIsNone(worker.snapshot())
        self.assertEqual(worker.status()["counters"]["obsolete"], 1)
        source[0] += 50_000_000
        self.assertTrue(worker.submit(frame(2, source[0])))
        self.assertTrue(worker.drain())
        self.assertIsNotNone(worker.snapshot())

"""Native preparation isolates probes and keeps cold costs on the same owner."""

from dataclasses import replace
import threading
import unittest
from unittest.mock import patch

import numpy as np
import test_async_native_v1 as original

from physical_ai.perception.async_native_v1 import NativeResult, WIDTH, HEIGHT
from physical_ai.perception.camera import CameraClock
from physical_ai.perception.native_startup_v1 import (
    PreparedNativePerception,
    synthetic_bgra,
)


class NativeStartupTests(unittest.TestCase):
    raw = bytes(WIDTH * HEIGHT * 4)

    def make(self, infer=None):
        self.clock = CameraClock(77)
        self.clock.update(1, 10_000_000)
        self.wall = 1_000_000_000
        self.calls, self.thread_ids = [], []
        self.entered, self.release = threading.Event(), threading.Event()
        self.release.set()
        owner = self

        class Backend:
            def infer(self, packet):
                owner.calls.append(packet)
                owner.thread_ids.append(threading.get_ident())
                if infer:
                    return infer(packet, len(owner.calls))
                return NativeResult(packet.identity)

        worker = PreparedNativePerception(Backend(), self.clock, lambda: self.wall)
        self.addCleanup(lambda: (self.release.set(), worker.close()))
        patched = patch(
            "physical_ai.perception.native_startup_v1.synthetic_bgra",
            return_value=self.raw,
        )
        patched.start()
        self.addCleanup(patched.stop)
        return worker

    def test_preparation_is_not_sensor_publication_and_owner_is_reused(self):
        w = self.make()
        self.assertFalse(w.start_session(1, 10_000_000))
        self.assertFalse(w.offer(1, 0.01, WIDTH, HEIGHT, self.raw))
        self.assertIsNone(w.snapshot())
        self.assertTrue(w.prepare())
        self.assertTrue(w.wait_prepared(2))
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(w.status()["counters"]["started"], 0)
        self.assertIsNone(w.snapshot())
        self.assertFalse(w.prepare())
        self.assertTrue(w.start_session(1, 10_000_000))
        self.assertTrue(w.offer(1, 0.01, WIDTH, HEIGHT, self.raw))
        self.assertTrue(w.drain())
        self.assertEqual(len(set(self.thread_ids)), 1)
        self.assertEqual(w.snapshot().identity.clock_instance, 77)
        self.assertEqual(w.preparation_status()["state"], "READY")
        self.assertEqual(len(w.decision_trace()["rows"]), 1)

    def test_cold_cost_is_recorded_but_settled_calls_must_be_below100ms(self):
        def infer(packet, n):
            self.wall += 400_000_000 if n == 1 else 50_000_000
            return NativeResult(packet.identity)

        w = self.make(infer)
        self.assertTrue(w.prepare())
        self.assertTrue(w.wait_prepared(2))
        report = w.preparation_status()
        self.assertEqual(
            [r["elapsed_wall_ns"] for r in report["calls"]],
            [400_000_000, 50_000_000, 50_000_000],
        )
        self.assertFalse(any(r["published"] for r in report["calls"]))

    def test_exact_settled_deadline_fails_without_retry(self):
        def infer(packet, n):
            self.wall += 100_000_000 if n == 2 else 1
            return NativeResult(packet.identity)

        w = self.make(infer)
        self.assertTrue(w.prepare())
        self.assertFalse(w.wait_prepared(2))
        self.assertEqual(w.preparation_status()["state"], "FAILED")
        self.assertFalse(w.prepare())
        self.assertFalse(w.start_session(1, 10_000_000))
        self.assertEqual(len(self.calls), 2)

    def test_timeout_late_completion_cannot_restore_ready(self):
        def infer(packet, n):
            self.entered.set()
            self.release.wait(5)
            return NativeResult(packet.identity)

        w = self.make(infer)
        self.release.clear()
        self.assertTrue(w.prepare())
        self.assertTrue(self.entered.wait(2))
        self.assertTrue(w.status()["preparation_busy"])
        self.wall += 10_000_000_000
        self.assertEqual(w.preparation_status()["state"], "FAILED")
        self.assertFalse(w.close(0.01))
        self.release.set()
        self.assertTrue(w.close(2))
        self.assertEqual(w.preparation_status()["state"], "FAILED")
        self.assertEqual(len(w.preparation_status()["calls"]), 1)
        self.assertIsNone(w.snapshot())

    def test_exception_identity_and_clock_regression_fail_closed(self):
        for kind in ("exception", "identity", "clock"):

            def infer(packet, n):
                if kind == "exception":
                    raise RuntimeError("injected preparation failure")
                if kind == "identity":
                    return NativeResult(replace(packet.identity, frame=99))
                self.wall -= 1
                return NativeResult(packet.identity)

            with self.subTest(kind=kind):
                w = self.make(infer)
                self.assertTrue(w.prepare())
                self.assertFalse(w.wait_prepared(2))
                self.assertEqual(w.preparation_status()["state"], "FAILED")
                self.assertFalse(w.prepare())
                self.assertTrue(w.close())

    def test_cancel_before_request_stops_without_backend_calls(self):
        w = self.make()
        self.assertTrue(w.close())
        self.assertFalse(w.prepare())
        self.assertEqual(w.preparation_status()["state"], "CANCELLED")
        self.assertEqual(self.calls, [])

    def test_native_gradient_matches_rgb_xy_definition(self):
        data = np.frombuffer(synthetic_bgra(), np.uint8).reshape(HEIGHT, WIDTH, 4)
        for y, x in ((0, 0), (255, 256), (1200, 3000), (HEIGHT - 1, WIDTH - 1)):
            self.assertEqual(
                data[y, x].tolist(), [(x + y) % 256, y % 256, x % 256, 255]
            )


# Exercise all21 existing sensor/session/clock/overload tests after preparation.


class PreparedAdmissionTests(original.AsyncNativeTests):
    def setUp(self):
        self.clock = CameraClock(77)
        self.clock.update(1, 10_000_000)
        self.wall = 1_000_000_000
        self.backend = original.Backend()
        self.backend.release.set()
        patcher = patch(
            "physical_ai.perception.native_startup_v1.synthetic_bgra",
            return_value=self.raw,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.worker = PreparedNativePerception(
            self.backend, self.clock, lambda: self.wall
        )
        self.addCleanup(self.cleanup)
        self.assertTrue(self.worker.prepare())
        self.assertTrue(self.worker.wait_prepared(2))
        self.backend.calls.clear()
        self.backend.entered.clear()
        self.backend.release.clear()
        self.assertTrue(self.worker.start_session(1, 10_000_000))
        self.frame = 1


if __name__ == "__main__":
    unittest.main()

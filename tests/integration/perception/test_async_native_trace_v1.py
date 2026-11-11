"""Reuse every V1 admission test against the traced owner, then audit causes."""

import unittest

import test_async_native_v1 as original
from physical_ai.perception.async_native_trace_v1 import TracedNativePerception
from physical_ai.perception.camera import CameraClock
from physical_ai.perception.contract import LIFETIME_NS


class TracedNativeTests(original.AsyncNativeTests):
    def setUp(self):
        self.clock = CameraClock(77)
        self.clock.update(1, 10_000_000)
        self.wall = 1_000_000_000
        self.backend = original.Backend()
        self.worker = TracedNativePerception(
            self.backend, self.clock, lambda: self.wall
        )
        self.assertTrue(self.worker.start_session(1, 10_000_000))
        self.frame = 1
        self.addCleanup(self.cleanup)

    def test_source_only_receipt_only_and_both_causes_are_exact(self):
        self.begin()
        self.advance(11, wall=False)
        self.backend.release.set()
        self.assertTrue(self.worker.drain())
        row = self.worker.decision_trace()["rows"][0]
        self.assertEqual(
            (row["outcome"], row["source_expired"], row["receipt_expired"]),
            ("late", True, False),
        )
        self.backend.entered.clear()
        self.backend.release.clear()
        self.begin()
        self.wall += LIFETIME_NS
        self.backend.release.set()
        self.assertTrue(self.worker.drain())
        row = self.worker.decision_trace()["rows"][1]
        self.assertEqual(
            (row["outcome"], row["source_expired"], row["receipt_expired"]),
            ("late", False, True),
        )
        self.advance(12, wall=False)
        self.backend.entered.clear()
        self.backend.release.clear()
        self.begin()
        self.advance(22)
        self.backend.release.set()
        self.assertTrue(self.worker.drain())
        row = self.worker.decision_trace()["rows"][2]
        self.assertEqual(
            (row["outcome"], row["source_expired"], row["receipt_expired"]),
            ("late", True, True),
        )

    def test_trace_overflow_is_counted_without_changing_publication(self):
        self.worker._trace_capacity = 1
        self.backend.release.set()
        for number in (1, 6):
            self.advance(number)
            self.assertTrue(self.offer())
            self.assertTrue(self.worker.drain())
        self.assertEqual(self.worker.status()["counters"]["published"], 2)
        trace = self.worker.decision_trace()
        self.assertEqual((len(trace["rows"]), trace["overflow"]), (1, 1))
        trace["rows"][0]["outcome"] = "mutated"
        self.assertEqual(
            self.worker.decision_trace()["rows"][0]["outcome"], "published"
        )


if __name__ == "__main__":
    unittest.main()

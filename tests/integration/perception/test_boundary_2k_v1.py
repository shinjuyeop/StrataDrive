"""Publication must preserve callback receipt through asynchronous completion."""

from dataclasses import replace
import threading
import unittest
from unittest.mock import patch

from physical_ai.perception.async_native_2k_v1 import NativeResult, WIDTH, HEIGHT
from physical_ai.perception.async_native_v1 import NativeResult as FourKResult
from physical_ai.perception.boundary_2k_v1 import (
    BoundaryObservation, BoundaryWorldPerception, Publication, ReplayCursor, frame_line,
)
from physical_ai.perception.contract import FrameIdentity
from physical_ai.perception.world_async_v1 import ObservedWorldClock


class PublicationTests(unittest.TestCase):
    def test_wrong_type_clock_and_renewed_expiry_rejected(self):
        p = Publication(NativeResult(FrameIdentity(1, 77, 5, 50_000_000)), 88, 1_000_000_000, 1_100_000_000)
        p.validate()
        for bad in (replace(p, wall_clock=0), replace(p, wall_clock=True),
                    replace(p, received_wall_ns=p.received_wall_ns + 1),
                    replace(p, wall_expires_ns=p.wall_expires_ns + 1),
                    replace(p, result=FourKResult(p.result.identity))):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                bad.validate()

    def test_cursor_polls_same_result_and_never_republishes_after_gap(self):
        p = Publication(NativeResult(FrameIdentity(1, 77, 5, 50_000_000)), 88, 1_000_000_000, 1_100_000_000)
        observation = BoundaryObservation(p, 50_000_000, 1_010_000_000, 1_005_000_000)
        cursor = ReplayCursor()
        self.assertTrue(cursor.line(observation).startswith("F "))
        self.assertTrue(cursor.line(observation).startswith("P "))
        self.assertTrue(cursor.line(replace(observation, publication=None)).startswith("U "))
        self.assertTrue(cursor.line(observation).startswith("P "))
        # Changed same-frame payload reaches the receiver's replay rejection.
        changed = replace(p, result=replace(p.result, inference_ns=1))
        self.assertTrue(cursor.line(replace(observation, publication=changed)).startswith("F "))
        with self.assertRaises(ValueError):
            cursor.line(replace(observation, source_ns=None))
        fields = frame_line(p, observation.source_ns, observation.wall_ns, observation.state_received_wall_ns).split()
        self.assertEqual(fields[10:14], ["50000000", "150000000", "1000000000", "1100000000"])


class BoundaryOwnerTests(unittest.TestCase):
    raw = bytes(WIDTH * HEIGHT * 4)

    def setUp(self):
        self.wall = 1_000_000_000
        self.entered, self.release = threading.Event(), threading.Event()
        self.release.set()
        self.calls = []
        self.fail = False
        parent = self

        class Backend:
            def infer(self, packet):
                parent.calls.append(packet)
                if packet.identity.clock_instance == 77:
                    parent.entered.set()
                    if not parent.release.wait(2):
                        raise TimeoutError("test backend release")
                    if parent.fail:
                        raise RuntimeError("injected backend fault")
                return NativeResult(packet.identity)

        self.worker = BoundaryWorldPerception(Backend(), ObservedWorldClock(77), 88, lambda: self.wall)
        self.addCleanup(lambda: (self.release.set(), self.worker.close()))
        with patch("physical_ai.perception.native_startup_2k_v1.synthetic_bgra", return_value=self.raw):
            self.assertTrue(self.worker.prepare())
            self.assertTrue(self.worker.wait_prepared(2))
        self.assertIsNone(self.worker.boundary_observation().publication)
        self.state(5)
        self.assertTrue(self.worker.start_observed_session(1))

    def state(self, frame):
        self.assertEqual(self.worker.observe_snapshot(77, frame, frame * 10_000_000, 10_000_000, self.wall), "accepted")

    def offer(self, frame=5):
        self.assertTrue(self.worker.offer(frame, frame * .01, WIDTH, HEIGHT, self.raw))

    def test_original_receipt_is_not_backend_completion_or_consumer_read(self):
        self.release.clear()
        self.offer()
        self.assertTrue(self.entered.wait(2))
        original = self.wall
        self.wall += 40_000_000
        self.state(9)
        self.release.set()
        self.assertTrue(self.worker.drain())
        self.wall += 10_000_000
        sample = self.worker.boundary_observation()
        sample.publication.validate()
        self.assertEqual(sample.publication.received_wall_ns, original)
        self.assertEqual(sample.publication.wall_expires_ns, original + 100_000_000)
        self.assertEqual(sample.publication.result.identity.source_ns, 50_000_000)
        self.assertEqual(sample.state_received_wall_ns, original + 40_000_000)
        self.assertEqual(sample.source_ns, 90_000_000)
        self.assertEqual(sample.wall_ns, original + 50_000_000)
        self.assertEqual(self.worker.boundary_observation().publication, sample.publication)

    def test_slow_backend_does_not_block_state_or_snapshot_and_late_output_is_absent(self):
        self.release.clear()
        self.offer()
        self.assertTrue(self.entered.wait(2))
        for frame in range(6, 16):
            self.wall += 10_000_000
            self.state(frame)
            self.assertIsNone(self.worker.boundary_observation().publication)
        self.release.set()
        self.assertTrue(self.worker.drain())
        self.assertIsNone(self.worker.boundary_observation().publication)
        self.assertEqual(self.worker.status()["counters"]["late"], 1)

    def test_session_change_obsoletes_inflight_completion(self):
        self.release.clear()
        self.offer()
        self.assertTrue(self.entered.wait(2))
        self.assertTrue(self.worker.start_observed_session(2))
        self.release.set()
        self.assertTrue(self.worker.drain())
        self.assertIsNone(self.worker.boundary_observation().publication)
        self.assertEqual(self.worker.status()["counters"]["obsolete"], 1)

    def test_error_and_close_clear_previous_publication(self):
        self.offer()
        self.assertTrue(self.worker.drain())
        self.assertIsNotNone(self.worker.boundary_observation().publication)
        self.fail = True
        self.wall += 10_000_000
        self.state(6)
        self.offer(6)
        self.assertTrue(self.worker.drain())
        self.assertIsNone(self.worker.boundary_observation().publication)
        self.assertEqual(self.worker.status()["counters"]["errors"], 1)
        self.assertTrue(self.worker.close())
        self.assertIsNone(self.worker.boundary_observation().publication)

    def test_exact_wall_expiry_with_fresh_state_does_not_extend_source(self):
        self.offer()
        self.assertTrue(self.worker.drain())
        self.wall += 99_999_999
        self.state(6)
        self.assertIsNotNone(self.worker.boundary_observation().publication)
        self.wall += 1
        self.assertIsNone(self.worker.boundary_observation().publication)


if __name__ == "__main__":
    unittest.main()

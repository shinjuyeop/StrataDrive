"""Actual snapshot identity, missing observations, state silence and dual expiry."""

import threading
import unittest
from unittest.mock import patch

from physical_ai.perception.async_native_v1 import NativeResult, WIDTH, HEIGHT
from physical_ai.perception.contract import FrameIdentity
from physical_ai.perception.world_async_v1 import (
    ObservedWorldClock,
    WorldAsyncPerception,
)


class ClockTests(unittest.TestCase):
    def setUp(self):
        self.clock = ObservedWorldClock(77)

    def put(self, frame, **kw):
        args = dict(
            instance=77,
            frame=frame,
            source_ns=frame * 10_000_000,
            delta_ns=10_000_000,
            received_wall_ns=frame * 1_000_000,
            wall=1_000_000_000,
        )
        args.update(kw)
        return self.clock.observe(**args)

    def test_gaps_are_counted_not_filled(self):
        self.put(1)
        self.put(5)
        self.assertEqual(self.clock.now(), 50_000_000)
        self.assertEqual(self.clock.status()["counters"]["missing"], 3)
        self.assertFalse(self.clock.matches(FrameIdentity(1, 77, 3, 30_000_000)))
        self.assertTrue(self.clock.matches(FrameIdentity(1, 77, 5, 50_000_000)))
        self.assertIsNone(self.clock.matches(FrameIdentity(1, 77, 6, 60_000_000)))

    def test_duplicate_reordered_do_not_refresh_state(self):
        self.put(4)
        before = self.clock.status()
        self.assertEqual(self.put(4, received_wall_ns=9_000_000), "duplicate")
        self.assertEqual(self.put(3, received_wall_ns=9_000_000), "reordered")
        self.assertEqual(
            self.clock.status()["received_wall_ns"], before["received_wall_ns"]
        )
        self.assertFalse(self.clock.matches(FrameIdentity(1, 77, 3, 30_000_000)))

    def test_bad_world_time_delta_receipt_latches(self):
        for bad in (
            dict(instance=78),
            dict(source_ns=1),
            dict(delta_ns=20_000_000),
            dict(received_wall_ns=2_000_000_000),
            dict(frame=True),
        ):
            with self.subTest(bad=bad):
                self.clock = ObservedWorldClock(77)
                self.put(1)
                with self.assertRaises(ValueError):
                    self.put(2, **bad) if "frame" not in bad else self.put(True)
                with self.assertRaises(ValueError):
                    self.put(3)
                with self.assertRaises(ValueError):
                    self.clock.now()

    def test_bounded_actual_snapshot_cache(self):
        for frame in range(1, 140):
            self.put(frame)
        self.assertFalse(self.clock.matches(FrameIdentity(1, 77, 1, 10_000_000)))
        self.assertTrue(self.clock.matches(FrameIdentity(1, 77, 139, 1_390_000_000)))
        self.assertFalse(self.clock.matches(FrameIdentity(1, 78, 139, 1_390_000_000)))
        self.assertFalse(self.clock.matches(FrameIdentity(1, 77, 139, 1_390_002_000)))


class OwnerTests(unittest.TestCase):
    raw = bytes(WIDTH * HEIGHT * 4)

    def setUp(self):
        self.wall = 1_000_000_000
        self.clock = ObservedWorldClock(77)
        self.calls = []
        self.entered, self.release = threading.Event(), threading.Event()
        self.release.set()
        owner = self

        class Backend:
            def infer(self, packet):
                owner.calls.append(packet)
                if packet.identity.clock_instance == 77:
                    owner.entered.set()
                    owner.release.wait(2)
                return NativeResult(packet.identity)

        self.worker = WorldAsyncPerception(Backend(), self.clock, lambda: self.wall)
        self.addCleanup(lambda: (self.release.set(), self.worker.close()))
        with patch(
            "physical_ai.perception.native_startup_v1.synthetic_bgra",
            return_value=self.raw,
        ):
            self.assertTrue(self.worker.prepare())
            self.assertTrue(self.worker.wait_prepared(2))

    def state(self, frame):
        return self.worker.observe_snapshot(
            77, frame, frame * 10_000_000, 10_000_000, self.wall
        )

    def start(self):
        self.assertEqual(self.state(1), "accepted")
        self.assertTrue(self.worker.start_observed_session(1))

    def offer(self, frame):
        return self.worker.offer(frame, frame * 0.01, WIDTH, HEIGHT, self.raw)

    def test_uninitialized_observation_and_offer_do_not_poison_first_state(self):
        self.assertIsNone(self.worker.observation()["source_ns"])
        self.assertFalse(self.offer(1))
        self.assertFalse(self.worker.status()["clock_fault"])
        self.start()
        self.assertTrue(self.offer(1))
        self.assertTrue(self.worker.drain())
        self.assertIsNotNone(self.worker.snapshot())

    def test_atomic_sample_uses_original_state_and_result(self):
        self.start()
        self.assertTrue(self.offer(1))
        self.assertTrue(self.worker.drain())
        sample = self.worker.observation()
        self.assertEqual(sample["state"]["source_ns"], sample["source_ns"])
        self.assertEqual(sample["result"].identity.source_ns, sample["source_ns"])
        self.assertEqual(sample["state"]["received_wall_ns"], self.wall)
        self.assertFalse(self.worker.start_observed_session(1))
        self.assertTrue(self.worker.start_observed_session(2))
        self.assertIsNone(self.worker.snapshot())

    def test_exact_state_silence_invalidates_and_fresh_state_does_not_revive(self):
        self.start()
        self.offer(1)
        self.worker.drain()
        self.wall += 100_000_000
        self.assertIsNone(self.worker.snapshot())
        self.assertTrue(self.worker.world_status()["stale"])
        self.assertFalse(self.worker.status()["clock_fault"])
        self.assertFalse(self.offer(2))
        self.assertEqual(self.state(2), "accepted")
        self.assertIsNone(self.worker.snapshot())
        self.assertTrue(self.offer(2))
        self.assertTrue(self.worker.drain())
        self.assertEqual(self.worker.snapshot().identity.frame, 2)

    def test_state_silence_obsoletes_active_completion(self):
        self.start()
        self.release.clear()
        self.offer(1)
        self.assertTrue(self.entered.wait(2))
        self.wall += 100_000_000
        self.assertIsNone(self.worker.snapshot())
        self.state(2)
        self.release.set()
        self.assertTrue(self.worker.drain())
        self.assertIsNone(self.worker.snapshot())
        self.assertEqual(self.worker.status()["counters"]["obsolete"], 1)

    def test_source_deadline_still_expires_with_fresh_wall_state(self):
        self.start()
        self.offer(1)
        self.worker.drain()
        self.wall += 1_000_000
        self.state(11)
        self.assertIsNone(self.worker.snapshot())
        self.assertFalse(self.worker.world_status()["stale"])

    def test_original_receipt_expiry_not_renewed_by_snapshots(self):
        self.start()
        self.offer(1)
        self.worker.drain()
        self.wall += 100_000_000
        self.state(2)
        self.assertIsNone(self.worker.snapshot())

    def test_future_image_waits_for_actual_matching_snapshot(self):
        self.start()
        self.assertTrue(self.offer(5))
        self.assertFalse(self.entered.wait(0.03))
        self.state(5)
        self.assertTrue(self.worker.drain())
        self.assertEqual(self.worker.snapshot().identity.frame, 5)

    def test_skipped_image_snapshot_never_fabricated(self):
        self.start()
        self.assertTrue(self.offer(3))
        self.state(5)
        self.assertTrue(self.worker.drain())
        self.assertEqual(len(self.calls), 3)  # only synthetic preparation
        self.assertIsNone(self.worker.snapshot())

    def test_bad_world_latches_across_new_state_and_session(self):
        self.start()
        self.assertEqual(
            self.worker.observe_snapshot(78, 2, 20_000_000, 10_000_000, self.wall),
            "fault",
        )
        self.assertEqual(self.state(3), "fault")
        self.assertFalse(self.worker.start_observed_session(2))
        self.assertFalse(self.offer(3))
        self.assertTrue(self.worker.status()["clock_fault"])

    def test_duplicate_does_not_extend_state_lifetime(self):
        self.start()
        self.wall += 100_000_000
        self.assertEqual(self.state(1), "duplicate")
        self.assertTrue(self.worker.world_status()["stale"])
        self.assertFalse(self.worker.start_observed_session(2))

    def test_stopped_owner_cannot_resume(self):
        self.start()
        self.assertTrue(self.worker.close())
        self.assertEqual(self.state(2), "stopped")
        self.assertFalse(self.offer(2))
        self.assertFalse(self.worker.start_observed_session(2))
        self.assertIsNone(self.worker.snapshot())


if __name__ == "__main__":
    unittest.main()

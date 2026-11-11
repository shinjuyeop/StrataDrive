"""Native async admission, bounded overload and independent state/control progress."""

from dataclasses import replace
import threading
import unittest
import numpy as np

from physical_ai.perception.async_native_v1 import (
    AsyncNativePerception,
    BgraPacket,
    NativeDetection,
    NativeResult,
    WIDTH,
    HEIGHT,
    PinnedNativeBackend,
)
from physical_ai.perception.camera import CameraClock
from physical_ai.perception.contract import FrameIdentity, LIFETIME_NS, PerceptionResult


class Backend:
    def __init__(self):
        self.entered, self.release = threading.Event(), threading.Event()
        self.calls = []
        self.transform = lambda packet: NativeResult(packet.identity)

    def infer(self, packet):
        self.calls.append(packet)
        self.entered.set()
        if not self.release.wait(10):
            raise TimeoutError("test backend remained blocked")
        return self.transform(packet)


class AsyncNativeTests(unittest.TestCase):
    raw = bytes(WIDTH * HEIGHT * 4)

    def setUp(self):
        self.clock = CameraClock(77)
        self.clock.update(1, 10_000_000)
        self.wall = 1_000_000_000
        self.backend = Backend()
        self.worker = AsyncNativePerception(self.backend, self.clock, lambda: self.wall)
        self.assertTrue(self.worker.start_session(1, 10_000_000))
        self.frame = 1
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.backend.release.set()
        self.assertTrue(self.worker.close())
        c = self.worker.status()["counters"]
        self.assertEqual(c["offered"], c["accepted"] + c["rejected"])
        self.assertEqual(
            c["accepted"],
            sum(
                c[k] for k in ("started", "overwritten", "cancelled", "expired_pending")
            ),
        )
        self.assertEqual(c["started"], c["completed"])
        self.assertEqual(
            c["completed"],
            sum(c[k] for k in ("published", "late", "errors", "obsolete")),
        )

    def advance(self, target, *, wall=True):
        for number in range(self.frame + 1, target + 1):
            if wall:
                self.wall += 10_000_000
            self.assertTrue(self.worker.observe_tick(number, number * 10_000_000))
        self.frame = target

    def offer(self, number=None, stamp=None, raw=None):
        number = self.frame if number is None else number
        return self.worker.offer(
            number,
            number / 100 if stamp is None else stamp,
            WIDTH,
            HEIGHT,
            self.raw if raw is None else raw,
        )

    def begin(self):
        self.assertTrue(self.offer())
        self.assertTrue(self.backend.entered.wait(2))

    def test_latest_pending_replaces_older_frame_without_cancelling_active_call(self):
        self.begin()
        self.advance(6)
        self.assertTrue(self.offer())
        self.advance(11)
        self.assertTrue(self.offer())
        self.assertEqual(len(self.backend.calls), 1)
        self.assertTrue(self.worker.status()["pending"])
        self.backend.release.set()
        self.assertTrue(self.worker.drain())
        self.assertEqual([p.identity.frame for p in self.backend.calls], [1, 11])
        c = self.worker.status()["counters"]
        self.assertEqual((c["overwritten"], c["late"], c["published"]), (1, 1, 1))
        self.assertEqual(self.worker.snapshot().identity.frame, 11)

    def test_state_and_control_progress_while_backend_is_blocked(self):
        self.begin()
        done = threading.Event()
        observations = []

        def other_owners():
            for number in range(2, 102):
                observations.append(
                    self.worker.observe_tick(number, number * 10_000_000)
                )
                if number % 2 == 0:
                    observations.append(self.worker.snapshot() is None)
            done.set()

        owner = threading.Thread(target=other_owners, daemon=True)
        owner.start()
        self.assertTrue(done.wait(2), "state/control waited for blocked inference")
        owner.join(2)
        self.assertTrue(all(observations))
        self.assertEqual(len(observations), 150)
        self.assertFalse(self.backend.release.is_set())
        self.assertTrue(self.worker.status()["busy"])

    def test_receipt_expiry_is_exclusive_even_when_simulation_is_paused(self):
        self.backend.release.set()
        self.assertTrue(self.offer())
        self.assertTrue(self.worker.drain())
        original = self.worker.snapshot()
        self.assertEqual(original.identity.source_ns, 10_000_000)
        self.wall += LIFETIME_NS - 1
        self.assertIs(self.worker.snapshot(), original)
        self.wall += 1
        self.assertIsNone(self.worker.snapshot())

    def test_late_completion_does_not_get_a_new_acquisition_or_lifetime(self):
        self.begin()
        self.wall += LIFETIME_NS
        self.backend.release.set()
        self.assertTrue(self.worker.drain())
        self.assertIsNone(self.worker.snapshot())
        self.assertEqual(self.worker.status()["counters"]["late"], 1)

    def test_simulation_age_expires_even_if_wall_clock_does_not_advance(self):
        self.begin()
        self.advance(11, wall=False)
        self.backend.release.set()
        self.assertTrue(self.worker.drain())
        self.assertIsNone(self.worker.snapshot())
        self.assertEqual(self.worker.status()["counters"]["late"], 1)

    def test_expired_pending_packet_never_invokes_the_model(self):
        self.begin()
        self.advance(2)
        self.assertTrue(self.offer())
        self.wall += LIFETIME_NS
        self.backend.release.set()
        self.assertTrue(self.worker.drain())
        self.assertEqual(len(self.backend.calls), 1)
        self.assertEqual(self.worker.status()["counters"]["expired_pending"], 1)

    def test_new_session_discards_old_completion_but_accepts_new_result(self):
        self.begin()
        self.assertTrue(self.worker.start_session(2, 10_000_000))
        self.advance(2)
        self.assertTrue(self.offer())
        self.backend.release.set()
        self.assertTrue(self.worker.drain())
        result = self.worker.snapshot()
        self.assertEqual((result.identity.epoch, result.identity.frame), (2, 2))
        self.assertEqual(self.worker.status()["counters"]["obsolete"], 1)

    def test_malformed_callback_invalidates_inflight_and_new_valid_frame_recovers(self):
        self.begin()
        self.assertFalse(self.offer(2, raw=b"broken"))
        self.backend.release.set()
        self.assertTrue(self.worker.drain())
        self.assertIsNone(self.worker.snapshot())
        self.assertEqual(self.worker.status()["counters"]["obsolete"], 1)
        self.advance(2)
        self.assertTrue(self.offer())
        self.assertTrue(self.worker.drain())
        self.assertEqual(self.worker.snapshot().identity.frame, 2)

    def test_future_callback_waits_for_actual_matching_world_snapshot(self):
        self.assertTrue(self.offer(2))
        self.assertFalse(self.backend.entered.wait(0.03))
        self.advance(2)
        self.assertTrue(self.backend.entered.wait(2))
        self.assertEqual(self.backend.calls[0].identity.source_ns, 20_000_000)

    def test_forged_future_timestamp_is_rejected_after_tick_without_rewriting_it(self):
        self.assertTrue(self.offer(2, 0.019))
        self.advance(2)
        self.assertTrue(self.worker.drain())
        self.assertEqual(self.backend.calls, [])
        self.assertEqual(self.worker.status()["counters"]["cancelled"], 1)

    def test_future_callback_expires_by_receipt_when_world_does_not_progress(self):
        self.assertTrue(self.offer(2))
        self.wall += LIFETIME_NS
        self.assertTrue(self.worker.drain())
        self.assertEqual(self.backend.calls, [])
        self.assertEqual(self.worker.status()["counters"]["expired_pending"], 1)

    def test_callback_owns_mutable_sdk_storage_and_original_receipt(self):
        raw = bytearray(self.raw)
        raw[:4] = bytes([1, 2, 3, 255])
        receipt = self.wall
        self.assertTrue(self.offer(raw=raw))
        raw[:4] = bytes(4)
        self.assertTrue(self.backend.entered.wait(2))
        packet = self.backend.calls[0]
        self.assertEqual(packet.bgra[:4], bytes([1, 2, 3, 255]))
        self.assertEqual(packet.received_wall_ns, receipt)

    def test_result_schema_model_and_original_identity_cannot_be_forged(self):
        transforms = (
            lambda p: replace(NativeResult(p.identity), model_sha256="0" * 64),
            lambda p: replace(NativeResult(p.identity), width=640),
            lambda p: NativeResult(
                replace(p.identity, source_ns=p.identity.source_ns + 1)
            ),
            lambda p: PerceptionResult(p.identity, (), 0, 0, 0),
        )
        self.backend.release.set()
        for n, transform in enumerate(transforms, 1):
            self.backend.transform = transform
            self.advance(n)
            self.assertTrue(self.offer())
            self.assertTrue(self.worker.drain())
            self.assertIsNone(self.worker.snapshot())
        self.assertEqual(self.worker.status()["counters"]["errors"], len(transforms))

    def test_backend_exception_is_unavailable_then_can_recover(self):
        def failure(packet):
            raise RuntimeError("injected model error")

        self.backend.transform = failure
        self.backend.release.set()
        self.assertTrue(self.offer())
        self.assertTrue(self.worker.drain())
        self.assertIsNone(self.worker.snapshot())
        self.backend.transform = lambda p: NativeResult(p.identity)
        self.advance(2)
        self.assertTrue(self.offer())
        self.assertTrue(self.worker.drain())
        self.assertIsNotNone(self.worker.snapshot())
        self.assertEqual(self.worker.status()["counters"]["errors"], 1)

    def test_clock_regression_latches_and_cannot_be_cleared_by_new_epoch(self):
        self.begin()
        self.wall -= 1
        self.assertIsNone(self.worker.snapshot())
        self.wall += 1
        self.assertFalse(self.worker.start_session(2, 10_000_000))
        self.assertFalse(self.offer(2))
        self.backend.release.set()
        self.assertTrue(self.worker.drain())
        self.assertTrue(self.worker.status()["clock_fault"])
        self.assertIsNone(self.worker.snapshot())

    def test_bad_world_tick_latches_without_waiting_for_backend(self):
        self.begin()
        self.assertFalse(self.worker.observe_tick(3, 30_000_000))
        self.assertTrue(self.worker.status()["clock_fault"])
        self.assertFalse(self.worker.start_session(2, 10_000_000))

    def test_close_reports_unstopped_backend_and_discards_its_later_completion(self):
        self.begin()
        self.assertFalse(self.worker.close(timeout=0.001))
        self.assertFalse(self.worker.status()["stopped"])
        self.assertFalse(self.offer(2))
        self.backend.release.set()
        self.assertTrue(self.worker.close())
        self.assertTrue(self.worker.status()["stopped"])
        self.assertIsNone(self.worker.snapshot())
        self.assertEqual(self.worker.status()["counters"]["obsolete"], 1)

    def test_callback_replay_layout_boolean_and_nonfinite_timestamp_rejected(self):
        for stamp in (True, -1, float("nan"), float("inf")):
            self.assertFalse(self.offer(1, stamp))
        self.assertFalse(self.worker.offer(1, 0.01, 640, 384, self.raw))
        self.assertFalse(self.worker.offer(True, 0.01, WIDTH, HEIGHT, self.raw))
        self.assertTrue(self.offer())
        self.assertTrue(self.backend.entered.wait(2))
        self.assertFalse(self.offer())

    def test_native_boxes_are_typed_and_never_masquerade_as_legacy640_result(self):
        detection = NativeDetection(0, 0.9, (1000.0, 100.0, 2000.0, 2000.0))
        result = NativeResult(FrameIdentity(1, 77, 1, 10_000_000), (detection,))
        result.validate()
        for bad in (
            replace(detection, class_id=True),
            replace(detection, score=0.59),
            replace(detection, box=(0.0, 0.0, 4000.0, 2304.0)),
            replace(detection, box=(True, 0.0, 100.0, 100.0)),
        ):
            with self.assertRaises(ValueError):
                bad.validate()
        with self.assertRaises(ValueError):
            BgraPacket(result.identity, b"wrong", 1).validate()

    def test_native_backend_preserves_bgra_channels_dimensions_and_native_coordinates(
        self,
    ):
        raw = bytearray(self.raw)
        raw[:4] = bytes([1, 2, 3, 255])
        observed = []

        class Detector:
            def prepare(self, frame):
                frame.validate()
                observed.append((frame.width, frame.height, frame.rgb[:3]))
                return "feed"

            def raw(self, feed):
                self.feed = feed
                labels = np.zeros((1, 300), np.int64)
                boxes = np.zeros((1, 300, 4), np.float32)
                scores = np.zeros((1, 300), np.float32)
                boxes[0, 0] = [600, 120, 1200, 1200]
                scores[0, 0] = 0.9
                return dict(labels=labels, boxes=boxes, scores=scores)

        backend = object.__new__(PinnedNativeBackend)
        backend.detector = Detector()
        packet = BgraPacket(FrameIdentity(1, 77, 1, 10_000_000), bytes(raw), self.wall)
        result = backend.infer(packet)
        self.assertEqual(observed, [(WIDTH, HEIGHT, bytes([3, 2, 1]))])
        self.assertEqual(result.identity, packet.identity)
        self.assertEqual(result.detections[0].box, (600, 120, 1200, 1200))

    def test_session_enable_cannot_be_backdated(self):
        self.advance(2)
        self.assertFalse(self.worker.start_session(2, 10_000_000))
        self.assertTrue(self.worker.start_session(2, 20_000_000))


if __name__ == "__main__":
    unittest.main()

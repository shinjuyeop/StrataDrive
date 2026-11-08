import dataclasses
import threading
import unittest
import numpy as np

from physical_ai.perception.contract import (
    CameraFrame,
    FrameIdentity,
    Detection,
    PerceptionResult,
    WIDTH,
    HEIGHT,
    LIFETIME_NS,
    profile,
    execution_profile,
)
from physical_ai.perception.yolox import preprocess, postprocess, image_health
from physical_ai.perception.tracking import ImageTracker
from physical_ai.perception.worker import LatestFrameWorker


def frame(number=1, source=50_000_000, epoch=1, clock=7):
    return CameraFrame(
        FrameIdentity(epoch, clock, number, source), bytes(WIDTH * HEIGHT * 3)
    )


def result(camera=None, detections=()):
    return PerceptionResult((camera or frame()).identity, tuple(detections), 0, 0, 0)


def raw_box(raw, anchor=0, box=(20, 20, 40, 40), cls=2, score=0.9):
    # Anchor0 and1 lie at (0,0)/(1,0), stride8.
    x1, y1, x2, y2 = box
    raw[0, anchor, :4] = (
        (x1 + x2) / 16 - anchor,
        (y1 + y2) / 16,
        np.log((x2 - x1) / 8),
        np.log((y2 - y1) / 8),
    )
    raw[0, anchor, 4] = 1
    raw[0, anchor, 5 + cls] = score


class DecodeTests(unittest.TestCase):
    def test_execution_profile_is_explicit_and_never_autoselects_gpu(self):
        self.assertIsNone(execution_profile("cpu"))
        self.assertEqual(execution_profile("cuda")["use_tf32"], "0")
        self.assertEqual(execution_profile("cuda")["disable_cpu_ep_fallback"], "1")
        with self.assertRaises(ValueError):
            execution_profile("auto")

    def test_result_rejects_boolean_scores_coordinates_and_hash_change(self):
        for detection in (
            Detection(2, True, (1.0, 2.0, 3.0, 4.0)),
            Detection(2, 0.8, (True, 2.0, 3.0, 4.0)),
        ):
            with self.assertRaises(ValueError):
                detection.validate()
        with self.assertRaises(ValueError):
            dataclasses.replace(result(), model_sha256="0" * 64).validate()

    def test_obvious_information_loss_is_not_a_valid_empty_scene(self):
        for value in (0, 128, 255):
            with (
                self.subTest(value=value),
                self.assertRaisesRegex(ValueError, "information"),
            ):
                image_health(
                    dataclasses.replace(
                        frame(), rgb=bytes([value]) * WIDTH * HEIGHT * 3
                    )
                )
        values = np.tile(np.arange(WIDTH, dtype=np.uint16) % 256, (HEIGHT, 1)).astype(
            np.uint8
        )
        rgb = np.repeat(values[:, :, None], 3, axis=2).tobytes()
        self.assertGreater(
            image_health(dataclasses.replace(frame(), rgb=rgb))["luma_std"], 2
        )

    def test_profile_and_rgb_padding(self):
        self.assertEqual(profile()["camera"]["width"], 640)
        camera = dataclasses.replace(frame(), rgb=bytes([255, 10, 20]) * WIDTH * HEIGHT)
        tensor, scale = preprocess(camera)
        self.assertEqual(tensor.shape, (1, 3, 640, 640))
        self.assertEqual(tensor.dtype, np.float32)
        self.assertTrue(tensor.flags.c_contiguous)
        self.assertEqual(scale, 1)
        np.testing.assert_array_equal(tensor[0, :, 0, 0], [255, 10, 20])
        np.testing.assert_array_equal(tensor[0, :, 384, 0], [114, 114, 114])

    def test_reject_frame_layout_and_identity(self):
        for camera in (
            dataclasses.replace(frame(), rgb=b""),
            dataclasses.replace(frame(), width=320),
            dataclasses.replace(frame(), rgb=bytearray(WIDTH * HEIGHT * 3)),
            frame(epoch=0),
            frame(clock=0),
            frame(source=2**64 - 1),
            frame(number=True),
        ):
            with self.subTest(camera=camera.identity), self.assertRaises(ValueError):
                preprocess(camera)

    def test_empty_normal_is_valid(self):
        self.assertEqual(postprocess(np.zeros((1, 8400, 85), np.float32)), ())
        result().validate()

    def test_decode_original_pixels_and_class_nms(self):
        raw = np.zeros((1, 8400, 85), np.float32)
        raw_box(raw)
        raw_box(raw, 1, score=0.8)
        detected = postprocess(raw)
        self.assertEqual(len(detected), 1)
        np.testing.assert_allclose(detected[0].box, [20, 20, 40, 40], atol=1e-5)
        raw[0, 1, 7] = 0
        raw[0, 1, 5] = 0.8
        self.assertEqual(len(postprocess(raw)), 2)

    def test_scores_multiply_and_unsupported_classes_do_not_leak(self):
        raw = np.zeros((1, 8400, 85), np.float32)
        raw_box(raw, cls=4)
        self.assertEqual(postprocess(raw), ())
        raw_box(raw)
        raw[0, 0, 9] = 0
        raw[0, 0, 4] = 0.3
        self.assertEqual(postprocess(raw), ())

    def test_clip_padding_and_zero_area(self):
        raw = np.zeros((1, 8400, 85), np.float32)
        raw_box(raw, box=(-10, -10, 100, 450))
        np.testing.assert_allclose(postprocess(raw)[0].box, [0, 0, 100, 384], atol=1e-5)
        raw_box(raw, box=(10, 400, 30, 500))
        self.assertEqual(postprocess(raw), ())

    def test_shape_type_nonfinite_confidence_and_decode_overflow(self):
        for field, value in (
            (0, np.nan),
            (0, np.inf),
            (2, 1000),
            (2, -1000),
            (4, -0.1),
            (84, 1.1),
        ):
            raw = np.zeros((1, 8400, 85), np.float32)
            raw[0, 0, field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                postprocess(raw)
        for raw in (
            np.zeros((1, 8400, 85), np.float64),
            np.zeros((8400, 85), np.float32),
        ):
            with self.assertRaises(ValueError):
                postprocess(raw)

    def test_overload_is_unavailable_not_truncation(self):
        raw = np.zeros((1, 8400, 85), np.float32)
        raw[0, :1001, 4:6] = 1
        with self.assertRaisesRegex(ValueError, "candidate"):
            postprocess(raw)
        raw = np.zeros((1, 8400, 85), np.float32)
        raw[0, :101, 4:6] = 1
        raw[0, :101, 2:4] = -2
        with self.assertRaisesRegex(ValueError, "detection"):
            postprocess(raw)


class TrackingTests(unittest.TestCase):
    detection = Detection(2, 0.8, (10.0, 10.0, 40.0, 40.0))

    def test_history_bound_and_observed_only(self):
        tracker = ImageTracker()
        for n in range(1, 13):
            tracks = tracker.update(result(frame(n, n * 50_000_000), [self.detection]))
        self.assertEqual(tracks[0].track_id, 1)
        self.assertEqual(len(tracks[0].observations), 10)
        self.assertEqual(tracks[0].observations[0].frame, 3)
        self.assertEqual(tracker.update(result(frame(13, 650_000_000))), ())
        self.assertEqual(
            tracker.update(result(frame(14, 700_000_000), [self.detection]))[
                0
            ].track_id,
            2,
        )

    def test_session_gap_replay_and_classes(self):
        tracker = ImageTracker()
        tracker.update(result(detections=[self.detection]))
        with self.assertRaises(ValueError):
            tracker.update(result(detections=[self.detection]))
        tracks = tracker.update(result(frame(4, 200_000_001), [self.detection]))
        self.assertEqual(tracks[0].track_id, 2)
        tracks = tracker.update(
            result(
                frame(5, 250_000_001), [dataclasses.replace(self.detection, class_id=0)]
            )
        )
        self.assertEqual(tracks[0].track_id, 3)
        self.assertEqual(
            tracker.update(result(frame(epoch=2, clock=8), [self.detection]))[
                0
            ].track_id,
            1,
        )
        with self.assertRaises(ValueError):
            tracker.update(result(frame(epoch=1), [self.detection]))

    def test_one_to_one_assignment(self):
        tracker = ImageTracker()
        tracker.update(result(detections=[self.detection]))
        tracks = tracker.update(
            result(frame(2, 100_000_000), [self.detection, self.detection])
        )
        self.assertEqual([t.track_id for t in tracks], [1, 2])


class FakeBackend:
    def __init__(self):
        self.entered = threading.Event()
        self.release = threading.Event()
        self.failure = False
        self.rewrite = False

    def infer(self, camera):
        self.entered.set()
        if not self.release.wait(5):
            raise TimeoutError("test backend gate")
        if self.failure:
            raise RuntimeError("injected")
        if self.rewrite:
            camera = dataclasses.replace(
                camera,
                identity=dataclasses.replace(
                    camera.identity, source_ns=camera.identity.source_ns + 1
                ),
            )
        return result(camera)


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.source = 50_000_000
        self.wall = 1_000_000_000
        self.backend = FakeBackend()
        self.worker = LatestFrameWorker(
            self.backend, lambda: self.source, lambda: self.wall
        )
        self.addCleanup(self.cleanup)
        self.assertTrue(self.worker.start_session(1, 7, 0))

    def cleanup(self):
        self.backend.release.set()
        self.assertTrue(self.worker.close())

    def begin(self, camera=None):
        self.assertTrue(self.worker.submit(camera or frame()))
        self.assertTrue(self.backend.entered.wait(2))

    def finish(self):
        self.backend.release.set()
        self.assertTrue(self.worker.drain())

    def test_valid_empty_then_expires_without_timestamp_renewal(self):
        self.begin()
        self.finish()
        self.assertEqual(self.worker.snapshot().detections, ())
        self.source = 150_000_000
        self.assertIsNone(self.worker.snapshot())

    def test_latest_queue_overwrites_exactly_one_pending(self):
        self.begin()
        self.source = 100_000_000
        self.assertTrue(self.worker.submit(frame(2, self.source)))
        self.source = 150_000_000
        self.assertTrue(self.worker.submit(frame(3, self.source)))
        self.finish()
        self.assertEqual(self.worker.snapshot().identity.frame, 3)
        counts = self.worker.status()["counters"]
        self.assertEqual(
            (
                counts["submitted"],
                counts["started"],
                counts["overwritten"],
                counts["late"],
                counts["published"],
            ),
            (3, 2, 1, 1, 1),
        )

    def test_wall_deadline_without_simulation_advance(self):
        self.begin()
        self.wall += LIFETIME_NS
        self.finish()
        self.assertIsNone(self.worker.snapshot())
        self.assertEqual(self.worker.status()["counters"]["late"], 1)

    def test_source_deadline_without_wall_advance(self):
        self.begin()
        self.source += LIFETIME_NS
        self.finish()
        self.assertIsNone(self.worker.snapshot())
        self.assertEqual(self.worker.status()["counters"]["late"], 1)

    def test_backend_failure_and_identity_rewrite_are_unavailable(self):
        self.backend.failure = True
        self.begin()
        self.finish()
        self.assertIsNone(self.worker.snapshot())
        self.assertEqual(self.worker.status()["counters"]["errors"], 1)
        self.backend.failure = False
        self.backend.rewrite = True
        self.source = 100_000_000
        self.assertTrue(self.worker.submit(frame(2, self.source)))
        self.assertTrue(self.worker.drain())
        self.assertIsNone(self.worker.snapshot())
        self.assertEqual(self.worker.status()["counters"]["errors"], 2)

    def test_new_session_discards_inflight_completion(self):
        self.begin()
        self.assertTrue(self.worker.start_session(2, 7, self.source))
        self.finish()
        self.assertIsNone(self.worker.snapshot())
        self.assertEqual(self.worker.status()["counters"]["obsolete"], 1)
        self.assertTrue(self.worker.submit(frame(epoch=2)))
        self.assertTrue(self.worker.drain())
        self.assertEqual(self.worker.snapshot().identity.epoch, 2)

    def test_rejected_init_keeps_current_and_cannot_backdate_new_session(self):
        self.begin()
        self.finish()
        self.assertFalse(self.worker.start_session(2, 7, self.source - 1))
        self.assertIsNotNone(self.worker.snapshot())
        self.assertTrue(self.worker.start_session(2, 7, self.source))
        self.assertFalse(self.worker.submit(frame(2, self.source - 1, epoch=2)))

    def test_clock_regression_latches_until_new_session(self):
        self.begin()
        self.source -= 1
        self.finish()
        self.source = 100_000_000
        self.assertFalse(self.worker.submit(frame(2, self.source)))
        self.assertTrue(self.worker.status()["clock_fault"])
        self.assertTrue(self.worker.start_session(2, 7, self.source))
        self.assertTrue(self.worker.submit(frame(2, self.source, epoch=2)))
        self.assertTrue(self.worker.drain())
        self.assertIsNotNone(self.worker.snapshot())

    def test_stop_timeout_does_not_claim_backend_stopped(self):
        self.begin()
        self.assertFalse(self.worker.close(timeout=0))
        self.assertTrue(self.worker.status()["stop_requested"])
        self.assertFalse(self.worker.status()["stopped"])
        self.finish()
        self.assertTrue(self.worker.close())
        self.assertTrue(self.worker.status()["stopped"])
        self.assertIsNone(self.worker.snapshot())
        self.assertEqual(self.worker.status()["counters"]["obsolete"], 1)

    def test_invalid_identity_future_duplicate_rejected(self):
        for camera in (frame(epoch=2), frame(clock=8), frame(source=self.source + 1)):
            self.assertFalse(self.worker.submit(camera))
        self.begin()
        self.finish()
        self.assertFalse(self.worker.submit(frame()))
        self.assertIsNone(self.worker.snapshot())

    def test_invalid_new_submission_cannot_be_overwritten_by_inflight_success(self):
        self.begin()
        self.assertFalse(self.worker.submit(frame(2, 100_000_000, epoch=2)))
        self.finish()
        self.assertIsNone(self.worker.snapshot())
        self.assertEqual(self.worker.status()["counters"]["obsolete"], 1)

    def test_clock_unavailable_latches_and_worker_survives(self):
        self.begin()
        original = self.worker._source_now

        def broken():
            raise RuntimeError("injected clock loss")

        self.worker._source_now = broken
        self.finish()
        self.assertIsNone(self.worker.snapshot())
        self.assertFalse(self.worker.start_session(2, 7, 0))
        self.worker._source_now = original
        self.assertIsNone(self.worker.snapshot())
        self.assertTrue(self.worker.start_session(2, 7, self.source))
        self.assertTrue(self.worker.submit(frame(epoch=2)))
        self.assertTrue(self.worker.drain())
        self.assertIsNotNone(self.worker.snapshot())

    def test_clock_failure_during_init_also_closes_old_availability(self):
        self.begin()
        self.finish()
        self.wall -= 1
        self.assertFalse(self.worker.start_session(2, 7, self.source))
        self.wall += 1
        self.assertIsNone(self.worker.snapshot())
        self.assertTrue(self.worker.status()["clock_fault"])
        self.assertTrue(self.worker.start_session(2, 7, self.source))


if __name__ == "__main__":
    unittest.main()

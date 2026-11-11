import tempfile
import unittest
import threading
from pathlib import Path
from native_raw_recorder_v1 import RawRecorder


class NativeRecorderTests(unittest.TestCase):
    def test_overflow_is_explicit_and_preserves_emergency_frame(self):
        entered, release = threading.Event(), threading.Event()

        class BlockedFirst(RawRecorder):
            def _write(self, row, raw):
                if row["frame"] == 1:
                    entered.set()
                    release.wait(2)
                super()._write(row, raw)

        with tempfile.TemporaryDirectory() as tmp:
            recorder = BlockedFirst(Path(tmp) / "raw", 1)
            recorder.offer(dict(frame=1), b"one")
            self.assertTrue(entered.wait(1))
            recorder.offer(dict(frame=2), b"two")
            try:
                self.assertFalse(recorder.offer(dict(frame=3), b"emergency"))
            finally:
                release.set()
            self.assertTrue(recorder.close(1))
            self.assertEqual(recorder.report()["overflow"], [3])
            self.assertEqual(len(recorder.report()["records"]), 3)
            self.assertEqual((Path(tmp) / "raw/3.bgra").read_bytes(), b"emergency")

    def test_exact_bytes_and_bounded_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            recorder = RawRecorder(Path(tmp) / "raw", 2)
            self.assertTrue(recorder.offer(dict(frame=1, source_ns=10), b"original"))
            self.assertTrue(recorder.close())
            report = recorder.report()
            self.assertEqual((report["offered"], len(report["records"])), (1, 1))
            self.assertEqual((Path(tmp) / "raw/1.bgra").read_bytes(), b"original")
            self.assertEqual(report["errors"], [])
            with self.assertRaises(ValueError):
                recorder.offer(dict(frame=2), b"late")

    def test_duplicate_frame_never_overwrites_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            recorder = RawRecorder(Path(tmp) / "raw", 2)
            recorder.offer(dict(frame=1), b"first")
            recorder.offer(dict(frame=1), b"second")
            self.assertTrue(recorder.close())
            self.assertEqual(len(recorder.report()["errors"]), 1)
            self.assertEqual((Path(tmp) / "raw/1.bgra").read_bytes(), b"first")

    def test_full_queue_close_timeout_can_be_retried(self):
        entered, release = threading.Event(), threading.Event()

        class BlockedRecorder(RawRecorder):
            def _write(self, row, raw):
                entered.set()
                release.wait(2)
                super()._write(row, raw)

        with tempfile.TemporaryDirectory() as tmp:
            recorder = BlockedRecorder(Path(tmp) / "raw", 1)
            recorder.offer(dict(frame=1), b"one")
            self.assertTrue(entered.wait(1))
            recorder.offer(dict(frame=2), b"two")
            try:
                self.assertFalse(recorder.close(0.001))
                self.assertFalse(recorder.sentinel_queued)
            finally:
                release.set()
            self.assertTrue(recorder.close(1))
            self.assertEqual(len(recorder.report()["records"]), 2)


if __name__ == "__main__":
    unittest.main()

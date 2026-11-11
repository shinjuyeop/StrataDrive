from pathlib import Path
import tempfile
import unittest
from native_memory_recorder_v1 import MemoryRecorder


class NativeMemoryRecorderTests(unittest.TestCase):
    def test_no_disk_or_extra_copy_in_normal_measurement_then_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = MemoryRecorder(Path(tmp) / "spill", 2)
            raw = b"original"
            self.assertTrue(r.offer(dict(frame=1), raw))
            self.assertIs(r.pending[0][1], raw)
            self.assertEqual(list((Path(tmp) / "spill").iterdir()), [])
            with self.assertRaises(ValueError):
                next(r.iter_raw())
            self.assertTrue(r.close())
            self.assertEqual(r.report()["disk_frames_during_measurement"], 0)
            self.assertEqual(list(r.iter_raw()), [(dict(frame=1), raw)])
            self.assertEqual(len(r.pending), 0)
            with self.assertRaises(ValueError):
                r.offer(dict(frame=2), raw)

    def test_overflow_fails_but_preserves_every_extra_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = MemoryRecorder(Path(tmp) / "spill", 1)
            self.assertTrue(r.offer(dict(frame=1), b"one"))
            self.assertFalse(r.offer(dict(frame=2), b"two"))
            self.assertTrue(r.close())
            report = r.report()
            self.assertEqual(report["peak_memory_frames"], 1)
            self.assertEqual(report["overflow"], [2])
            self.assertEqual(report["disk_frames_during_measurement"], 1)
            self.assertEqual([raw for _, raw in r.iter_raw()], [b"one", b"two"])

    def test_capacity_and_packet_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            for invalid in (0, 241, True):
                with self.assertRaises(ValueError):
                    MemoryRecorder(Path(tmp) / "bad", invalid)
            r = MemoryRecorder(Path(tmp) / "spill", 1)
            try:
                for row, raw in (
                    (dict(frame=True), b"x"),
                    (dict(frame=0), b"x"),
                    (dict(frame=1), bytearray(b"x")),
                ):
                    with self.assertRaises(ValueError):
                        r.offer(row, raw)
            finally:
                self.assertTrue(r.close())


if __name__ == "__main__":
    unittest.main()

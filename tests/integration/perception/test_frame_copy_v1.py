"""Independent snapshots, finite admission, concurrency and owner lifetime."""

import gc
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
import weakref

from physical_ai.perception.frame_copy_v1 import SnapshotPool

SIZE = 3840 * 2304 * 4


class Owner:
    def __init__(self, value):
        self.raw = bytearray([value]) * SIZE


class FrameCopyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="strata-frame-copy-test-")
        cls.addClassCleanup(cls.temp.cleanup)
        override = os.environ.get("STRATA_FRAME_COPY_TEST_LIBRARY")
        if override:
            cls.library = Path(override)
            cls.digest = hashlib.sha256(cls.library.read_bytes()).hexdigest()
            return
        out = Path(cls.temp.name) / "build"
        subprocess.run(
            [
                sys.executable,
                "tools/carla/m10_readback_v1/build_frame_copy.py",
                "--output",
                str(out),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        cls.library = next(out.glob("*.so"))
        cls.digest = hashlib.sha256(cls.library.read_bytes()).hexdigest()

    def pool(self, n=2):
        p = SnapshotPool(self.library, self.digest, n)
        self.addCleanup(p.close)
        return p

    def test_bytes_survive_owner_and_pool_and_never_change(self):
        pool = self.pool()
        owner = Owner(31)
        ref = weakref.ref(owner)
        view = memoryview(owner.raw).toreadonly()
        first = pool.copy(view, owner)
        digest = hash(first)  # A later copy must not mutate already hashed bytes.
        owner.raw[:] = bytes([71]) * SIZE
        second = pool.copy(view, owner)
        self.assertIs(type(first), bytes)
        self.assertIsNot(first, second)
        self.assertEqual(first, bytes([31]) * SIZE)
        self.assertEqual(second, bytes([71]) * SIZE)
        self.assertEqual(hash(first), digest)
        self.assertEqual(pool.stats()["completed"], 2)
        pool.close()
        view.release()
        del view, owner
        gc.collect()
        self.assertIsNone(ref())
        self.assertEqual(first[-1], 31)
        self.assertEqual(second[-1], 71)

    def test_rejects_layout_without_reserving(self):
        pool = self.pool(1)
        owner = Owner(0)
        good = memoryview(owner.raw).toreadonly()
        bad = [
            b"",
            memoryview(b""),
            memoryview(owner.raw),
            good[::2],
            good.cast("I"),
            good.cast("B", (2304, 3840 * 4)),
        ]
        for view in bad:
            with self.subTest(view_type=type(view)):
                with self.assertRaises(ValueError):
                    pool.copy(view, owner)
        with self.assertRaises(ValueError):
            pool.copy(good, None)
        self.assertEqual(pool.stats()["reserved"], 0)
        pool.copy(good, owner)
        with self.assertRaises(BufferError):
            pool.copy(good, owner)
        self.assertEqual(pool.stats()["completed"], 1)

    def test_capacity_and_pin_and_closed_pool(self):
        for count in (False, 0, 121, 1.5):
            with self.assertRaises(ValueError):
                SnapshotPool(self.library, self.digest, count)
        with self.assertRaises(ValueError):
            SnapshotPool(self.library, "0" * 64, 1)
        pool = self.pool(1)
        pool.close()
        pool.close()
        with self.assertRaises(ValueError):
            pool.stats()
        with self.assertRaises(ValueError):
            pool.copy(memoryview(b""), object())

    def test_concurrent_reservations_are_unique_and_bounded(self):
        pool = self.pool(4)
        owners = [Owner(i + 1) for i in range(8)]
        barrier = threading.Barrier(8)
        results, errors = [], []
        lock = threading.Lock()

        def run(owner):
            barrier.wait()
            try:
                result = pool.copy(memoryview(owner.raw).toreadonly(), owner)
                with lock:
                    results.append((owner.raw[0], result))
            except BufferError:
                with lock:
                    errors.append("full")

        jobs = [threading.Thread(target=run, args=(o,)) for o in owners]
        for job in jobs:
            job.start()
        for job in jobs:
            job.join(10)
        self.assertTrue(all(not j.is_alive() for j in jobs))
        self.assertEqual((len(results), len(errors)), (4, 4))
        self.assertEqual(len({id(x) for _, x in results}), 4)
        for value, result in results:
            self.assertEqual(result, bytes([value]) * SIZE)
        self.assertEqual(pool.stats()["reserved"], pool.stats()["completed"])


if __name__ == "__main__":
    unittest.main()

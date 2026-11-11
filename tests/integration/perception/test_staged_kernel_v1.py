import hashlib
from pathlib import Path
import unittest

import numpy as np

from physical_ai.perception.async_native_v1 import BgraPacket
from physical_ai.perception.contract import FrameIdentity
from physical_ai.perception.native_kernel_v1 import NativeResize
from physical_ai.perception.native_startup_v1 import synthetic_bgra
from physical_ai.perception.staged_kernel_v1 import prepare_staged


class StagedKernelTests(unittest.TestCase):
    def test_exact_feed_and_health_and_separate_stage_clocks(self):
        path = Path("build/m10-native-kernel-v1/libstrata_resize_v1.so")
        resize = NativeResize(path, hashlib.sha256(path.read_bytes()).hexdigest())
        packet = BgraPacket(FrameIdentity(1, 2, 3, 30_000_000), synthetic_bgra(), 1)
        original = resize.prepare(packet)
        row = {}
        staged = prepare_staged(resize, packet, row)
        self.assertEqual(original[1:3], staged[1:3])
        for name in original[0]:
            np.testing.assert_array_equal(original[0][name], staged[0][name])
        self.assertEqual(list(row), ["begin", "gray", "health", "resize", "tensor"])
        self.assertEqual(list(row.values()), sorted(row.values()))


if __name__ == "__main__":
    unittest.main()

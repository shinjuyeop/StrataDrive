"""Native resize ABI boundaries and full-frame exact Pillow/tensor comparisons."""

import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import numpy as np
from PIL import Image

from physical_ai.perception.async_native_2k_v1 import BgraPacket
from physical_ai.perception.contract import FrameIdentity
from physical_ai.perception.native_kernel_2k_v1 import NativeResize
from physical_ai.perception.camera_resolution_v1 import NativeFrame, prepare
from physical_ai.perception.native_preprocess_v1 import health_gray
import cv2


def prepare_packet(packet):
    rgb = Image.frombytes("RGB", (2560, 1536), packet.bgra, "raw", "BGRX").tobytes()
    frame = NativeFrame(packet.identity, 2560, 1536, rgb)
    values, fallback = health_gray(
        cv2.cvtColor(
            np.frombuffer(packet.bgra, np.uint8).reshape(1536, 2560, 4),
            cv2.COLOR_BGRA2GRAY,
        )
    )
    return prepare(frame), values, fallback


class NativeKernelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="strata-native-resize-test-")
        cls.addClassCleanup(cls.temp.cleanup)
        override = os.environ.get("STRATA_RESIZE_2K_TEST_LIBRARY")
        if override:
            library = Path(override)
            os.environ["OMP_WAIT_POLICY"] = "PASSIVE"
            cls.resize = NativeResize(
                library, hashlib.sha256(library.read_bytes()).hexdigest()
            )
            return
        library = Path(cls.temp.name) / "resize.so"
        source = (
            Path(__file__).resolve().parents[3]
            / "physical_ai/perception/native_resize_2k_v1.cpp"
        )
        subprocess.run(
            [
                "g++",
                "-std=c++17",
                "-O3",
                "-fPIC",
                "-shared",
                "-fopenmp",
                "-ffp-contract=off",
                "-Wall",
                "-Wextra",
                "-Werror",
                str(source),
                "-o",
                str(library),
            ],
            check=True,
        )
        # Set before this library's first parallel region; tests never enable GPU.
        os.environ["OMP_WAIT_POLICY"] = "PASSIVE"
        cls.resize = NativeResize(
            library, hashlib.sha256(library.read_bytes()).hexdigest()
        )

    def compare(self, raw):
        expected = np.asarray(
            Image.frombytes("RGB", (2560, 1536), raw, "raw", "BGRX").resize(
                (960, 960), Image.Resampling.BILINEAR
            )
        )
        for threads in (1, 4):
            self.resize.threads = threads
            np.testing.assert_array_equal(self.resize.resize(raw), expected)

    def test_seeded_noise_alpha_and_boundary_impulses(self):
        rng = np.random.default_rng(9731)
        raw = rng.integers(0, 256, (1536, 2560, 4), dtype=np.uint8)
        self.compare(raw.tobytes())
        raw.fill(0)
        raw[:, 0, :3] = 255
        raw[0, :, 1] = 255
        raw[-1, :, 2] = 255
        raw[:, -1, 0] = 255
        raw[1100:1103, 1800:1803, :3] = 255
        self.compare(raw.tobytes())

    def test_constant_extremes_checkerboard_and_full_tensor(self):
        raw = np.empty((1536, 2560, 4), np.uint8)
        for value in (0, 255):
            raw.fill(value)
            self.compare(raw.tobytes())
        raw[::2, ::2] = [0, 255, 17, 1]
        raw[1::2, 1::2] = [255, 0, 231, 254]
        data = raw.tobytes()
        self.compare(data)
        packet = BgraPacket(FrameIdentity(1, 77, 1, 10_000_000), data, 1)
        old = prepare_packet(packet)
        new = self.resize.prepare(packet)
        for key in old[0]:
            np.testing.assert_array_equal(old[0][key], new[0][key])
        self.assertEqual(old[1:3], new[1:3])

    def test_rejects_layout_null_abi_and_invalid_threads(self):
        for raw in (b"", bytearray(2560 * 1536 * 4)):
            with self.assertRaises(ValueError):
                self.resize.resize(raw)
        self.assertEqual(self.resize.call(None, 0, None, 0, None, 0, 4), 1)
        before = self.resize.output.copy()
        self.resize.threads = 5
        with self.assertRaises(ValueError):
            self.resize.resize(bytes(2560 * 1536 * 4))
        np.testing.assert_array_equal(before, self.resize.output)
        self.resize.threads = 4


if __name__ == "__main__":
    unittest.main()

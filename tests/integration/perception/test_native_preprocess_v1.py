"""Exact image/tensor equivalence and unchanged image-loss boundary decisions."""

import unittest
import cv2
import numpy as np
from PIL import Image

from physical_ai.perception.async_native_v1 import BgraPacket, WIDTH, HEIGHT
from physical_ai.perception.camera_resolution_v1 import NativeFrame, health, prepare
from physical_ai.perception.contract import FrameIdentity
from physical_ai.perception.native_preprocess_v1 import health_gray, prepare_packet


class NativePreprocessTests(unittest.TestCase):
    def test_full_native_tensor_and_rgb_ignore_alpha_exactly(self):
        x = np.arange(WIDTH, dtype=np.uint16)
        y = np.arange(HEIGHT, dtype=np.uint16)[:, None]
        bgra = np.empty((HEIGHT, WIDTH, 4), np.uint8)
        bgra[:, :, 0] = (x * 3 + y) % 256
        bgra[:, :, 1] = (x + y * 7) % 256
        bgra[:, :, 2] = (x * 11 + y * 3) % 256
        bgra[:, :, 3] = (x * 17 + y) % 256
        identity = FrameIdentity(1, 7, 1, 10_000_000)
        raw = bgra.tobytes()
        rgb = bgra[:, :, 2::-1].copy().tobytes()
        self.assertEqual(
            Image.frombytes("RGB", (WIDTH, HEIGHT), raw, "raw", "BGRX").tobytes(), rgb
        )
        frame = NativeFrame(identity, WIDTH, HEIGHT, rgb)
        reference = prepare(frame)
        feed, values, fallback, _, _ = prepare_packet(BgraPacket(identity, raw, 1))
        np.testing.assert_array_equal(feed["images"], reference["images"])
        np.testing.assert_array_equal(
            feed["orig_target_sizes"], reference["orig_target_sizes"]
        )
        self.assertTrue(feed["images"].flags.c_contiguous)
        self.assertFalse(fallback)
        for k, value in health(frame).items():
            self.assertAlmostEqual(values[k], value, places=10)

    def test_exact_std_boundary_retains_original_reduction(self):
        gray = np.tile(np.array([128, 132], np.uint8), (128, 128))
        values, fallback = health_gray(gray)
        self.assertTrue(fallback)
        self.assertEqual(values["luma_std"], float(gray.std()))
        gray[0, 1] = 131
        self.assertLess(gray.std(), 2)
        with self.assertRaisesRegex(ValueError, "information"):
            health_gray(gray)
        gray[0, 1] = 133
        self.assertGreater(health_gray(gray)[0]["luma_std"], 2)

    def test_exact98_percent_black_and_white_boundaries(self):
        for value in (0, 255):
            gray = np.full((100, 100), value, np.uint8)
            gray.flat[:200] = 128
            values, _ = health_gray(gray)
            key = "near_black_fraction" if value == 0 else "near_white_fraction"
            self.assertEqual(values[key], 0.98)
            gray.flat[199] = value
            with self.assertRaisesRegex(ValueError, "information"):
                health_gray(gray)

    def test_flat_loss_and_invalid_arrays_are_not_a_valid_empty_scene(self):
        for value in (0, 128, 255):
            with self.assertRaisesRegex(ValueError, "information"):
                health_gray(np.full((40, 40), value, np.uint8))
        for array in (
            np.zeros((2, 2), np.float32),
            np.zeros(5, np.uint8),
            np.zeros((0, 0), np.uint8),
        ):
            with self.assertRaises(ValueError):
                health_gray(array)

    def test_all_rgb_codes_have_identical_grayscale_in_bgra_and_rgb_paths(self):
        # Exhaustive16,777,216 colors in256 bounded chunks; alpha is irrelevant.
        gb = np.arange(65536, dtype=np.uint32)
        bgra = np.empty((256, 256, 4), np.uint8)
        bgra[:, :, 0] = (gb % 256).reshape(256, 256)
        bgra[:, :, 1] = (gb // 256).reshape(256, 256)
        bgra[:, :, 3] = 17
        for r in range(256):
            bgra[:, :, 2] = r
            rgb = bgra[:, :, 2::-1].copy()
            np.testing.assert_array_equal(
                cv2.cvtColor(bgra, cv2.COLOR_BGRA2GRAY),
                cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY),
            )


if __name__ == "__main__":
    unittest.main()

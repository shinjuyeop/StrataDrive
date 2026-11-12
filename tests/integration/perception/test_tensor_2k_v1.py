import threading
import unittest
import numpy as np
from physical_ai.perception.tensor_2k_v1 import TensorWorkspace


class TensorWorkspaceTests(unittest.TestCase):
    def test_all_byte_values_equal_original_float32_division(self):
        image = np.resize(np.arange(256, dtype=np.uint8), (960, 960, 3))
        got = TensorWorkspace().convert(image)
        want = np.ascontiguousarray(
            np.asarray(image, np.float32).transpose(2, 0, 1)[None] / 255.0
        )
        np.testing.assert_array_equal(got["images"], want)
        self.assertTrue(got["images"].flags.c_contiguous)
        self.assertEqual(got["images"].dtype, np.float32)
        np.testing.assert_array_equal(got["orig_target_sizes"], [[2560, 1536]])

    def test_reuse_overwrites_every_element_without_input_alias(self):
        ws = TensorWorkspace()
        rng = np.random.default_rng(41)
        address = ws.images.ctypes.data
        for _ in range(5):
            image = rng.integers(0, 256, (960, 960, 3), dtype=np.uint8)
            result = ws.convert(image)["images"]
            self.assertEqual(result.ctypes.data, address)
            self.assertFalse(np.shares_memory(image, result))
            np.testing.assert_array_equal(
                result,
                np.ascontiguousarray(
                    np.asarray(image, np.float32).transpose(2, 0, 1)[None] / 255.0
                ),
            )
            image[:] = 0
            self.assertGreater(float(result.max()), 0)

    def test_other_thread_cannot_overwrite_inference_input(self):
        ws = TensorWorkspace()
        image = np.full((960, 960, 3), 17, np.uint8)
        ws.convert(image)
        errors = []

        def work():
            try:
                ws.convert(np.full_like(image, 255))
            except ValueError as e:
                errors.append(str(e))

        worker = threading.Thread(target=work)
        worker.start()
        worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertTrue(np.all(ws.images == np.float32(17) / np.float32(255)))

    def test_reject_wrong_layout_and_dtype(self):
        ws = TensorWorkspace()
        for image in [
            None,
            np.zeros((3, 960, 960), np.uint8),
            np.zeros((960, 960, 3), np.float32),
        ]:
            with self.assertRaises(ValueError):
                ws.convert(image)


if __name__ == "__main__":
    unittest.main()

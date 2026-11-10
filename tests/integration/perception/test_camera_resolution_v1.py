"""Native camera scale, support, lossless bytes and model coordinate regression."""

from pathlib import Path
import hashlib
import tempfile
import unittest
import zlib
import numpy as np

from physical_ai.perception.contract import FrameIdentity
from physical_ai.perception.camera_resolution_v1 import (
    NativeFrame,
    NativeDataset,
    prepare,
    canonical,
    unpack,
    scale_of,
)
from camera_resolution_v1_common import annotate, write_new
from quality_annotation import visible_boxes_v2


class CameraResolutionTests(unittest.TestCase):
    def test_angular_support_matches_old_policy_and_native_pixels_are_preserved(self):
        a = np.zeros((384, 640, 4), np.uint8)
        a[20:25, 10:15] = [0, 7, 12, 255]
        old, _ = visible_boxes_v2(a.tobytes())
        included, _ = annotate(a.tobytes(), 640, 384)
        self.assertEqual(
            [
                {k: v for k, v in o.items() if not k.startswith("native_")}
                for o in included
            ],
            old,
        )
        b = np.repeat(np.repeat(a, 2, axis=0), 2, axis=1)
        inc, exc = annotate(b.tobytes(), 1280, 768)
        self.assertEqual(inc[0]["box"], old[0]["box"])
        self.assertEqual(inc[0]["native_visible_pixels"], 100)
        b[40, 20] = 0
        inc, exc = annotate(b.tobytes(), 1280, 768)
        self.assertEqual(inc, [])
        self.assertEqual(exc[0]["native_visible_pixels"], 99)

    def test_lossless_packet_rejects_corruption_and_extra_compressed_stream(self):
        raw = bytes(640 * 384 * 4)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            p = root / "raw.z"
            data = zlib.compress(raw, 1)
            p.write_bytes(data)
            packet = dict(
                path=p.name,
                compression="zlib-1",
                stored_bytes=len(data),
                stored_sha256=hashlib.sha256(data).hexdigest(),
                raw_bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest(),
            )
            self.assertEqual(unpack(root, packet, 640, 384), raw)
            p.write_bytes(data + zlib.compress(b"x"))
            packet.update(
                stored_bytes=p.stat().st_size,
                stored_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
            )
            with self.assertRaises(ValueError):
                unpack(root, packet, 640, 384)

    def test_actual_native_dimensions_reach_model_without640_downsample(self):
        x = np.arange(1280, dtype=np.uint16) % 256
        rgb = (
            np.broadcast_to(x.astype(np.uint8)[None, :, None], (768, 1280, 3))
            .copy()
            .tobytes()
        )
        frame = NativeFrame(FrameIdentity(1, 1, 1, 1), 1280, 768, rgb)
        result = prepare(frame)
        self.assertEqual(result["images"].shape, (1, 3, 960, 960))
        self.assertEqual(result["orig_target_sizes"].tolist(), [[1280, 768]])
        self.assertEqual(scale_of(3840, 2304), 6)
        with self.assertRaises(ValueError):
            scale_of(1280, 720)

    def test_canonical_mapping_preserves_native_raw_and_holdout_is_denied(self):
        raw = dict(
            boxes=np.array([[[0, 0, 3840, 2304]]], np.float32),
            labels=np.array([[0]], np.int64),
            scores=np.array([[0.9]], np.float32),
        )
        normalized = canonical(raw, 6)
        self.assertEqual(normalized["boxes"].tolist(), [[[0, 0, 640, 384]]])
        self.assertEqual(raw["boxes"][0, 0, 2], 3840)
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "rgb.json"
            write_new(
                p,
                dict(schema="m10-highres-rgb-only-v1", partition="holdout", frames=[]),
            )
            with self.assertRaises(ValueError):
                NativeDataset(p)

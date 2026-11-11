"""Equivalent native4K preprocessing with direct BGRX decoding and exact counts.

The model, PIL bilinear resize, tensor arithmetic and async admission are unchanged.
Only CPU data conversion and image-health statistics are implemented differently.
"""

import math
import time

import cv2
import numpy as np
import PIL
from PIL import Image

from .async_native_v1 import (
    BgraPacket,
    HEIGHT,
    WIDTH,
    NativeDetection,
    NativeResult,
    PinnedNativeBackend,
)
from .camera_resolution_v1 import decode

REVISION = "m10-native-preprocess-v1"
CV_THREADS = 4


def health_gray(gray):
    """Float32 histogram counts are exact for fewer than2**24 uint8 pixels.

    Integer moments avoid a full float64 image and cancellation. At the std=2
    boundary use the original NumPy reduction, preserving its rounding decision.
    Black/white fractions use the same integer counts and binary64 division.
    """
    if gray.dtype != np.uint8 or gray.ndim != 2 or not 0 < gray.size < 2**24:
        raise ValueError("bounded uint8 gray image required")
    histogram = cv2.calcHist([gray], [0], None, [256], [0, 256]).reshape(256)
    if (
        not np.isfinite(histogram).all()
        or np.any(histogram < 0)
        or np.any(histogram != np.floor(histogram))
    ):
        raise ValueError("exact image histogram required")
    counts = histogram.astype(np.int64)
    n = int(counts.sum())
    if n != gray.size:
        raise ValueError("complete original pixel denominator required")
    # Python integers keep moment arithmetic exact, including count*sum_sq.
    total = sum(i * int(count) for i, count in enumerate(counts))
    square = sum(i * i * int(count) for i, count in enumerate(counts))
    numerator = n * square - total * total
    if numerator < 0:
        raise ValueError("negative image variance")
    std = math.sqrt(numerator / (n * n))
    fallback = abs(std - 2.0) <= 1e-9
    if fallback:
        std = float(gray.std())
    values = dict(
        luma_std=std,
        near_black_fraction=int(counts[:6].sum()) / n,
        near_white_fraction=int(counts[250:].sum()) / n,
    )
    if (
        values["luma_std"] < 2
        or values["near_black_fraction"] > 0.98
        or values["near_white_fraction"] > 0.98
    ):
        raise ValueError("image information unavailable")
    return values, fallback


def prepare_packet(packet):
    if type(packet) is not BgraPacket:
        raise ValueError("native BGRA packet type")
    packet.validate()
    before = time.monotonic_ns()
    # PIL's RGB image has the same pixels as RGB channel reordering/fromarray.
    # The raw BGRX decoder ignores alpha, exactly like the frozen RGB path.
    image = Image.frombytes("RGB", (WIDTH, HEIGHT), packet.bgra, "raw", "BGRX")
    converted = time.monotonic_ns()
    bgra = np.frombuffer(packet.bgra, np.uint8).reshape(HEIGHT, WIDTH, 4)
    gray = cv2.cvtColor(bgra, cv2.COLOR_BGRA2GRAY)
    values, fallback = health_gray(gray)
    resized = image.resize((960, 960), Image.Resampling.BILINEAR)
    tensor = np.asarray(resized, np.float32).transpose(2, 0, 1)[None] / 255.0
    feed = dict(
        images=np.ascontiguousarray(tensor),
        orig_target_sizes=np.array([[WIDTH, HEIGHT]], np.int64),
    )
    return feed, values, fallback, converted - before, time.monotonic_ns() - converted


class FastNativeBackend(PinnedNativeBackend):
    def __init__(self, model, manifest, execution="cuda"):
        if (
            cv2.__version__ != "4.11.0"
            or PIL.__version__ != "11.3.0"
            or np.__version__ != "1.23.5"
        ):
            raise ValueError("validated native preprocessing library versions required")
        # Set once before producer/consumer threads are enabled, never per image.
        cv2.setNumThreads(CV_THREADS)
        super().__init__(model, manifest, execution)

    def infer(self, packet):
        feed, _, _, convert_ns, preprocess_ns = prepare_packet(packet)
        before = time.monotonic_ns()
        raw = self.detector.raw(feed)
        inferred = time.monotonic_ns()
        detections = tuple(
            NativeDetection(d.class_id, d.score, tuple(v * 6 for v in d.box))
            for d in decode(raw, 6)
        )
        result = NativeResult(
            packet.identity,
            detections,
            convert_ns,
            preprocess_ns,
            inferred - before,
            time.monotonic_ns() - inferred,
        )
        result.validate()
        return result

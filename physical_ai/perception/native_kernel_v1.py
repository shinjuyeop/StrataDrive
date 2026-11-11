"""Fixed native4K CPU resize; model tensor bytes must match frozen Pillow input."""

import ctypes
import os
import time

import cv2
import numpy as np

from .async_native_v1 import BgraPacket, HEIGHT, WIDTH, NativeDetection, NativeResult
from .camera_resolution_v1 import decode
from .contract import sha256_file
from .native_preprocess_v1 import FastNativeBackend, health_gray


class NativeResize:
    def __init__(self, library, digest, threads=4):
        if type(threads) is not int or not 1 <= threads <= 4:
            raise ValueError("one to four CPU resize threads")
        if (
            sha256_file(library) != digest
            or os.environ.get("OMP_WAIT_POLICY") != "PASSIVE"
        ):
            raise ValueError("pinned native library and passive OpenMP wait required")
        self.library = ctypes.CDLL(str(library))  # CDLL releases GIL during call.
        self.call = self.library.strata_resize_bgra_v1
        self.call.argtypes = [ctypes.c_void_p, ctypes.c_size_t] * 3 + [ctypes.c_int]
        self.call.restype = ctypes.c_int
        self.threads = threads
        self.scratch = np.empty((HEIGHT, 960, 3), np.uint8)
        self.output = np.empty((960, 960, 3), np.uint8)

    def resize(self, raw):
        if type(raw) is not bytes or len(raw) != WIDTH * HEIGHT * 4:
            raise ValueError("exact immutable native BGRA required")
        # The bytes pointer remains alive for the complete synchronous C call.
        source = ctypes.c_char_p(raw)
        code = self.call(
            source,
            len(raw),
            self.scratch.ctypes.data,
            self.scratch.nbytes,
            self.output.ctypes.data,
            self.output.nbytes,
            self.threads,
        )
        if code:
            raise ValueError(f"native resize failed: {code}")
        return self.output  # Single inference owner; borrowed until next resize.

    def prepare(self, packet):
        if type(packet) is not BgraPacket:
            raise ValueError("native packet type")
        packet.validate()
        before = time.monotonic_ns()
        bgra = np.frombuffer(packet.bgra, np.uint8).reshape(HEIGHT, WIDTH, 4)
        values, fallback = health_gray(cv2.cvtColor(bgra, cv2.COLOR_BGRA2GRAY))
        resized = self.resize(packet.bgra)
        tensor = np.asarray(resized, np.float32).transpose(2, 0, 1)[None] / 255.0
        feed = dict(
            images=np.ascontiguousarray(tensor),
            orig_target_sizes=np.array([[WIDTH, HEIGHT]], np.int64),
        )
        return feed, values, fallback, time.monotonic_ns() - before


class KernelNativeBackend(FastNativeBackend):
    def __init__(self, model, manifest, library, digest):
        self.resize = NativeResize(library, digest)
        super().__init__(model, manifest, "cuda")

    def infer(self, packet):
        feed, _, _, preprocess_ns = self.resize.prepare(packet)
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
            0,
            preprocess_ns,
            inferred - before,
            time.monotonic_ns() - inferred,
        )
        result.validate()
        return result

"""Unchanged4K preprocessing/model arithmetic with separate monotonic stage times."""

from dataclasses import asdict
import threading
import time

import cv2
import numpy as np

from .async_native_2k_v1 import BgraPacket, HEIGHT, WIDTH, NativeDetection, NativeResult
from .camera_resolution_v1 import decode
from .native_kernel_2k_v1 import KernelNativeBackend
from .native_preprocess_v1 import health_gray


def prepare_staged(resize, packet, row):
    if type(packet) is not BgraPacket:
        raise ValueError("native packet type")
    packet.validate()
    row["begin"] = time.monotonic_ns()
    bgra = np.frombuffer(packet.bgra, np.uint8).reshape(HEIGHT, WIDTH, 4)
    gray = cv2.cvtColor(bgra, cv2.COLOR_BGRA2GRAY)
    row["gray"] = time.monotonic_ns()
    values, fallback = health_gray(gray)
    row["health"] = time.monotonic_ns()
    resized = resize.resize(packet.bgra)
    row["resize"] = time.monotonic_ns()
    tensor = np.asarray(resized, np.float32).transpose(2, 0, 1)[None] / 255.0
    feed = dict(
        images=np.ascontiguousarray(tensor),
        orig_target_sizes=np.array([[WIDTH, HEIGHT]], np.int64),
    )
    row["tensor"] = time.monotonic_ns()
    return feed, values, fallback


class StagedKernelBackend(KernelNativeBackend):
    def __init__(self, *args):
        self.stages = []
        super().__init__(*args)

    def infer(self, packet):
        if len(self.stages) >= 4096:
            raise ValueError("bounded backend stage trace")
        row = dict(
            identity=asdict(packet.identity), owner_thread_id=threading.get_ident()
        )
        try:
            feed, _, _ = prepare_staged(self.resize, packet, row)
            raw = self.detector.raw(feed)
            row["inference"] = time.monotonic_ns()
            detections = tuple(
                NativeDetection(d.class_id, d.score, tuple(v * 4 for v in d.box))
                for d in decode(raw, 4)
            )
            row["decode"] = time.monotonic_ns()
            result = NativeResult(
                packet.identity,
                detections,
                0,
                row["tensor"] - row["begin"],
                row["inference"] - row["tensor"],
                row["decode"] - row["inference"],
            )
            result.validate()
            return result
        except Exception as error:
            row["error"] = str(error)
            raise
        finally:
            row["end"] = time.monotonic_ns()
            self.stages.append(row)

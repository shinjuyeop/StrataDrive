"""Single-owner reusable NCHW workspace; byte-exact float32 division."""

import threading
import time
from dataclasses import asdict
import cv2
import numpy as np
from .async_native_2k_v1 import BgraPacket, HEIGHT, WIDTH, NativeDetection, NativeResult
from .camera_resolution_v1 import decode
from .native_preprocess_v1 import health_gray
from .staged_kernel_2k_v1 import StagedKernelBackend


class TensorWorkspace:
    """Borrowed until the next call; only the synchronous inference owner may use it."""

    def __init__(self):
        self.owner = None
        self.images = np.empty((1, 3, 960, 960), np.float32)
        self.sizes = np.array([[WIDTH, HEIGHT]], np.int64)

    def convert(self, resized):
        if (
            not isinstance(resized, np.ndarray)
            or resized.dtype != np.uint8
            or resized.shape != (960, 960, 3)
        ):
            raise ValueError("exact resized uint8 HWC image required")
        owner = threading.get_ident()
        if self.owner is None:
            self.owner = owner
        if self.owner != owner:
            raise ValueError("single synchronous tensor owner required")
        np.divide(
            resized.transpose(2, 0, 1)[None],
            np.float32(255),
            out=self.images,
            dtype=np.float32,
        )
        return dict(images=self.images, orig_target_sizes=self.sizes)

    def prepare(self, resize, packet, row):
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
        feed = self.convert(resized)
        row["tensor"] = time.monotonic_ns()
        return feed, values, fallback


class TensorKernelBackend(StagedKernelBackend):
    def __init__(self, *args):
        self.workspace = TensorWorkspace()
        super().__init__(*args)

    def infer(self, packet):
        if len(self.stages) >= 4096:
            raise ValueError("bounded backend stage trace")
        row = dict(
            identity=asdict(packet.identity), owner_thread_id=threading.get_ident()
        )
        try:
            feed, _, _ = self.workspace.prepare(self.resize, packet, row)
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

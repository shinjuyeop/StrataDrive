"""Bounded BGRA sensor ingress and an observed simulation clock.

No CARLA import, actor state, ground truth, or inference on a camera callback.
The tick owner pumps the latest image after recording actual world snapshots.
"""

from collections import OrderedDict
from dataclasses import dataclass
import math
import threading
import time
import numpy as np
from .contract import CameraFrame, FrameIdentity, WIDTH, HEIGHT, uint


class CameraClock:
    """One tick owner; readers never extrapolate or rewrite acquisition time."""

    def __init__(self, clock_instance):
        if not uint(clock_instance, positive=True):
            raise ValueError("camera clock instance")
        self.instance = clock_instance
        self._lock = threading.Lock()
        self._frames = OrderedDict()
        self._now = self._frame = 0
        self._failed = False

    def update(self, frame, source_ns):
        with self._lock:
            if (
                self._failed
                or not uint(frame, positive=True)
                or not uint(source_ns)
                or (
                    self._frames
                    and (
                        frame != self._frame + 1
                        or abs(source_ns - self._now - 10_000_000) > 1000
                    )
                )
            ):
                self._failed = True
                raise ValueError("camera tick sequence/period")
            self._frame, self._now = frame, source_ns
            self._frames[frame] = source_ns
            if len(self._frames) > 128:
                self._frames.popitem(last=False)

    def now(self):
        with self._lock:
            if self._failed or not self._frames:
                raise ValueError("camera clock unavailable")
            return self._now

    def matches(self, identity):
        """None means callback arrived before its corresponding tick completed."""
        with self._lock:
            if self._failed or identity.clock_instance != self.instance:
                return False
            if identity.frame > self._frame:
                return None
            stamp = self._frames.get(identity.frame)
            return stamp is not None and abs(stamp - identity.source_ns) <= 1000


@dataclass(frozen=True)
class ReceivedImage:
    identity: FrameIdentity
    bgra: bytes
    received_wall_ns: int

    def camera(self):
        pixels = np.frombuffer(self.bgra, dtype=np.uint8).reshape(HEIGHT, WIDTH, 4)
        return CameraFrame(self.identity, pixels[:, :, 2::-1].tobytes())


class BgraCameraIngress:
    def __init__(
        self, worker, epoch, clock_instance, attributes, wall_now=time.monotonic_ns
    ):
        FrameIdentity(epoch, clock_instance, 1, 0).validate()
        expected = {
            "image_size_x": 640,
            "image_size_y": 384,
            "fov": 90,
            "sensor_tick": 0.05,
        }
        if any(float(attributes.get(k, "nan")) != v for k, v in expected.items()):
            raise ValueError("camera calibration/profile mismatch")
        self._worker, self._epoch, self._clock = worker, epoch, clock_instance
        self._wall_now = wall_now
        self._lock = threading.Lock()
        self._pending = None
        self._closed = False
        self._last_frame = self._last_source = self._last_wall = 0
        self._counts = dict(
            received=0,
            accepted=0,
            overwritten=0,
            malformed=0,
            submitted=0,
            rejected=0,
            cancelled=0,
            after_close=0,
        )

    def offer(self, frame, timestamp_seconds, width, height, raw_bgra):
        """Camera callback: bounded copy, no GPU/GT/file IO or waiting for inference."""
        with self._lock:
            self._counts["received"] += 1
            if self._closed:
                self._counts["after_close"] += 1
                return False
            try:
                wall = self._wall_now()
                if not uint(wall) or wall < self._last_wall:
                    raise ValueError("camera receipt clock")
                self._last_wall = wall
                if (
                    type(timestamp_seconds) not in (float, int)
                    or not math.isfinite(timestamp_seconds)
                    or timestamp_seconds < 0
                ):
                    raise ValueError("camera timestamp")
                identity = FrameIdentity(
                    self._epoch, self._clock, frame, round(timestamp_seconds * 1e9)
                )
                identity.validate()
                if (
                    type(width) is not int
                    or type(height) is not int
                    or (width, height) != (WIDTH, HEIGHT)
                    or type(raw_bgra) not in (bytes, bytearray)
                    or len(raw_bgra) != WIDTH * HEIGHT * 4
                ):
                    raise ValueError("camera BGRA layout")
                if frame <= self._last_frame or (
                    self._last_frame and identity.source_ns <= self._last_source
                ):
                    raise ValueError("camera acquisition replay/regression")
                self._last_frame, self._last_source = frame, identity.source_ns
                if self._pending is not None:
                    self._counts["overwritten"] += 1
                self._pending = ReceivedImage(identity, bytes(raw_bgra), wall)
                self._counts["accepted"] += 1
                return True
            except Exception as error:
                self._counts["malformed"] += 1
                if self._pending is not None:
                    self._counts["cancelled"] += 1
                    self._pending = None
                self._worker.invalidate(str(error))
                return False

    def pump(self, clock):
        """Tick owner hands off at most one RGB frame; no inference or drain waits."""
        with self._lock:
            packet = self._pending
            if self._closed or packet is None:
                return None
            matched = clock.matches(packet.identity)
            if matched is None:
                return None
            self._pending = None
            if not matched:
                self._counts["rejected"] += 1
                self._worker.invalidate(
                    "camera timestamp not observed in world snapshot"
                )
                return (packet, False)
            admitted = self._worker.submit(
                packet.camera(), received_wall_ns=packet.received_wall_ns
            )
            self._counts["submitted" if admitted else "rejected"] += 1
            return (packet, admitted)

    def close(self):
        with self._lock:
            self._closed = True
            if self._pending is not None:
                self._counts["cancelled"] += 1
                self._pending = None
            self._worker.invalidate("camera ingress closed")

    def status(self):
        with self._lock:
            return dict(
                counters=dict(self._counts),
                pending=self._pending is not None,
                closed=self._closed,
            )

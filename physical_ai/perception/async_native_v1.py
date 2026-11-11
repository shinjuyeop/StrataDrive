"""Opt-in native4K perception owner; no control, simulator tick or GT authority.

The SDK offers an immutable BGRA packet. All image work runs on this owner,
outside the short mailbox lock. State/control owners only read a snapshot.
This version does not publish to the frozen YOLOX-S/C++640 result interface.
"""

from dataclasses import asdict, dataclass
import math
import threading
import time

from .camera_resolution_v1 import NativeDetector, NativeFrame, decode
from .contract import CLASSES, FrameIdentity, LIFETIME_NS, MAX_DETECTIONS, uint
from .resolution_car_v1 import VECTOR

WIDTH, HEIGHT = 3840, 2304
MODEL_SHA256 = "b865ac0f2597afd6fcb9e887ed7738e98e7690ecb4d5cebf42724a3e6b384884"
CANDIDATE = "dfine-m-960-car-v1-camera4k-v1"
SCHEMA = "m10-async-native-perception-v1"


@dataclass(frozen=True)
class BgraPacket:
    identity: FrameIdentity
    bgra: bytes
    received_wall_ns: int

    def validate(self):
        if type(self.identity) is not FrameIdentity:
            raise ValueError("native camera identity type")
        self.identity.validate()
        if (
            type(self.bgra) is not bytes
            or len(self.bgra) != WIDTH * HEIGHT * 4
            or not uint(self.received_wall_ns)
        ):
            raise ValueError("immutable native4K BGRA packet required")


@dataclass(frozen=True)
class NativeDetection:
    class_id: int
    score: float
    box: tuple[float, float, float, float]

    def validate(self):
        if (
            type(self.class_id) is not int
            or self.class_id not in CLASSES
            or type(self.score) not in (int, float)
            or not math.isfinite(self.score)
            or not dict(zip(CLASSES, VECTOR))[self.class_id] <= self.score <= 1
            or type(self.box) is not tuple
            or len(self.box) != 4
            or any(
                type(v) not in (int, float) or not math.isfinite(v) for v in self.box
            )
        ):
            raise ValueError("native detection contract")
        x1, y1, x2, y2 = self.box
        if not (0 <= x1 < x2 <= WIDTH and 0 <= y1 < y2 <= HEIGHT):
            raise ValueError("box outside native4K image")


@dataclass(frozen=True)
class NativeResult:
    identity: FrameIdentity
    detections: tuple[NativeDetection, ...] = ()
    convert_ns: int = 0
    preprocess_ns: int = 0
    inference_ns: int = 0
    postprocess_ns: int = 0
    width: int = WIDTH
    height: int = HEIGHT
    model_sha256: str = MODEL_SHA256
    candidate: str = CANDIDATE
    schema: str = SCHEMA

    @property
    def expires_ns(self):
        return self.identity.source_ns + LIFETIME_NS

    def validate(self):
        if type(self.identity) is not FrameIdentity:
            raise ValueError("native result identity type")
        self.identity.validate()
        if (
            type(self.width) is not int
            or type(self.height) is not int
            or (self.width, self.height) != (WIDTH, HEIGHT)
            or self.model_sha256 != MODEL_SHA256
            or self.candidate != CANDIDATE
            or self.schema != SCHEMA
            or type(self.detections) is not tuple
            or len(self.detections) > MAX_DETECTIONS
            or not all(
                uint(v)
                for v in (
                    self.convert_ns,
                    self.preprocess_ns,
                    self.inference_ns,
                    self.postprocess_ns,
                )
            )
        ):
            raise ValueError("native result provenance/layout")
        for detection in self.detections:
            if type(detection) is not NativeDetection:
                raise ValueError("native detection type")
            detection.validate()


class PinnedNativeBackend:
    """Initialize before enabling producers. No warmup or cold-call exclusion."""

    def __init__(self, model, manifest, execution="cuda"):
        from .contract import sha256_file

        if sha256_file(model) != MODEL_SHA256:
            raise ValueError("fixed4K/960 model required")
        self.detector = NativeDetector(960, model, manifest, execution)

    def infer(self, packet):
        import numpy as np

        packet.validate()
        before = time.monotonic_ns()
        rgb = np.frombuffer(packet.bgra, np.uint8).reshape(HEIGHT, WIDTH, 4)
        frame = NativeFrame(
            packet.identity, WIDTH, HEIGHT, rgb[:, :, 2::-1].copy().tobytes()
        )
        converted = time.monotonic_ns()
        feed = self.detector.prepare(frame)
        prepared = time.monotonic_ns()
        raw = self.detector.raw(feed)
        inferred = time.monotonic_ns()
        # The frozen decoder checks all300 queries and the complete0.35 list
        # before filtering. Convert its canonical boxes back to native pixels.
        detections = tuple(
            NativeDetection(d.class_id, d.score, tuple(v * 6 for v in d.box))
            for d in decode(raw, 6)
        )
        result = NativeResult(
            packet.identity,
            detections,
            converted - before,
            prepared - converted,
            inferred - prepared,
            time.monotonic_ns() - inferred,
        )
        result.validate()
        return result


@dataclass
class Counters:
    offered: int = 0
    accepted: int = 0
    rejected: int = 0
    overwritten: int = 0
    cancelled: int = 0
    expired_pending: int = 0
    started: int = 0
    completed: int = 0
    published: int = 0
    late: int = 0
    errors: int = 0
    obsolete: int = 0
    invalidated: int = 0


class AsyncNativePerception:
    """One active call, one pending packet, one immutable result.

    ``clock`` is an observed CameraClock. Its sole tick owner calls
    observe_tick(); the perception thread never advances simulation time.
    Acquisition+100ms AND receipt+100ms are exclusive deadlines. Completion
    never renews either one. A backend hang cannot be forcibly cancelled.
    """

    def __init__(self, backend, clock, wall_now=time.monotonic_ns):
        self._backend, self._clock, self._wall_now = backend, clock, wall_now
        self._condition = threading.Condition()
        self._counts = Counters()
        self._epoch = self._generation = self._enable = 0
        self._last_frame = self._last_acquisition = 0
        self._last_source = self._last_wall = 0
        self._pending = self._current = None
        self._current_wall_expiry = 0
        self._busy = self._stopped = self._clock_fault = False
        self._last_error = None
        self._thread = threading.Thread(
            target=self._run, name="m10-native4k-perception", daemon=True
        )
        self._thread.start()

    def _invalidate(self, reason):
        self._generation += 1
        self._counts.invalidated += 1
        self._current = None
        self._last_error = str(reason)
        if self._pending is not None:
            self._counts.cancelled += 1
            self._pending = None
        self._condition.notify_all()

    def invalidate(self, reason):
        with self._condition:
            self._invalidate(reason)

    def _now(self):
        try:
            source, wall = self._clock.now(), self._wall_now()
            if (
                self._clock_fault
                or not uint(source)
                or not uint(wall)
                or source < self._last_source
                or wall < self._last_wall
            ):
                raise ValueError("clock regression/type or latched fault")
        except Exception as error:
            if not self._clock_fault:
                self._clock_fault = True
                self._invalidate("clock unavailable/regression")
            raise ValueError("clock unavailable/regression") from error
        self._last_source, self._last_wall = source, wall
        return source, wall

    def observe_tick(self, frame, source_ns):
        """Only the world/state owner calls this; never waits for inference."""
        with self._condition:
            if self._stopped:
                return False
            try:
                self._clock.update(frame, source_ns)
                self._now()
            except Exception:
                if not self._clock_fault:
                    self._clock_fault = True
                    self._invalidate("invalid observed world tick")
                return False
            self._condition.notify_all()
            return True

    def start_session(self, epoch, enable_ns):
        with self._condition:
            try:
                source, _ = self._now()
                if (
                    self._stopped
                    or not uint(epoch, 2**32 - 1, True)
                    or epoch <= self._epoch
                    or not uint(enable_ns)
                    or enable_ns != source
                ):
                    return False
            except ValueError:
                return False
            self._invalidate("new native perception session")
            self._epoch, self._enable = epoch, enable_ns
            self._last_frame = self._last_acquisition = 0
            self._last_error = None
            return True

    def offer(self, frame, timestamp_seconds, width, height, raw_bgra):
        """SDK callback. Copy mutable storage outside the mailbox lock.

        No color conversion, image health scan, model, disk IO or inference wait.
        Passing existing immutable bytes may avoid a copy; receipt still starts
        here, before validation/copy. SDK transport before this entry is separate.
        """
        try:
            received = self._wall_now()
            with self._condition:
                epoch, generation = self._epoch, self._generation
            if (
                not uint(received)
                or type(timestamp_seconds) not in (float, int)
                or not math.isfinite(timestamp_seconds)
                or timestamp_seconds < 0
                or type(width) is not int
                or type(height) is not int
                or (width, height) != (WIDTH, HEIGHT)
                or type(raw_bgra) not in (bytes, bytearray)
                or len(raw_bgra) != WIDTH * HEIGHT * 4
            ):
                raise ValueError("native camera callback layout/timestamp")
            identity = FrameIdentity(
                epoch, self._clock.instance, frame, round(timestamp_seconds * 1e9)
            )
            packet = BgraPacket(identity, bytes(raw_bgra), received)
            packet.validate()
            error = None
        except Exception as caught:
            error = str(caught)
        with self._condition:
            self._counts.offered += 1
            try:
                if error is not None:
                    raise ValueError(error)
                source, wall = self._now()
                match = self._clock.matches(identity)
                if (
                    self._stopped
                    or epoch != self._epoch
                    or generation != self._generation
                    or not received <= wall < received + LIFETIME_NS
                    or identity.source_ns < self._enable
                    or identity.frame <= self._last_frame
                    or (
                        self._last_frame
                        and identity.source_ns <= self._last_acquisition
                    )
                    or match is False
                    or (
                        match is True
                        and not identity.source_ns
                        <= source
                        < identity.source_ns + LIFETIME_NS
                    )
                ):
                    raise ValueError("native packet admission/session/source")
            except Exception as caught:
                self._counts.rejected += 1
                self._invalidate(str(caught))
                return False
            self._last_frame, self._last_acquisition = (
                identity.frame,
                identity.source_ns,
            )
            if self._pending is not None:
                self._counts.overwritten += 1
            self._pending = (self._generation, packet)
            self._counts.accepted += 1
            self._condition.notify_all()
            return True

    def snapshot(self):
        """Constant-size immutable read; never joins or invokes the backend."""
        with self._condition:
            try:
                source, wall = self._now()
            except ValueError:
                return None
            if (
                self._stopped
                or self._current is None
                or source >= self._current.expires_ns
                or wall >= self._current_wall_expiry
            ):
                return None
            return self._current

    def status(self):
        with self._condition:
            return dict(
                counters=asdict(self._counts),
                busy=self._busy,
                pending=self._pending is not None,
                stop_requested=self._stopped,
                stopped=not self._thread.is_alive(),
                clock_fault=self._clock_fault,
                last_error=self._last_error,
            )

    def drain(self, timeout=5):
        """Lifecycle/test helper only. State and control owners never call it."""
        with self._condition:
            return self._condition.wait_for(
                lambda: not self._busy and self._pending is None, timeout
            )

    def close(self, timeout=5):
        with self._condition:
            self._stopped = True
            self._invalidate("native perception closed")
        self._thread.join(timeout)
        return not self._thread.is_alive()

    def _run(self):
        while True:
            with self._condition:
                self._condition.wait_for(
                    lambda: self._pending is not None or self._stopped
                )
                if self._stopped:
                    return
                generation, packet = self._pending
                try:
                    source, wall = self._now()
                    if (
                        not packet.received_wall_ns
                        <= wall
                        < packet.received_wall_ns + LIFETIME_NS
                    ):
                        self._pending = None
                        self._counts.expired_pending += 1
                        self._current = None
                        self._last_error = "pending receipt deadline"
                        self._condition.notify_all()
                        continue
                    match = self._clock.matches(packet.identity)
                    if match is None:
                        self._condition.wait(0.01)
                        continue
                    if not match:
                        raise ValueError(
                            "camera timestamp not observed in world snapshot"
                        )
                    if (
                        not packet.identity.source_ns
                        <= source
                        < packet.identity.source_ns + LIFETIME_NS
                    ):
                        self._pending = None
                        self._counts.expired_pending += 1
                        self._current = None
                        self._last_error = "pending source deadline"
                        self._condition.notify_all()
                        continue
                except Exception as error:
                    # _now() may already have invalidated/cancelled this packet.
                    if self._pending is not None:
                        self._invalidate(error)
                    continue
                self._pending = None
                self._busy = True
                self._counts.started += 1
            result, error = None, None
            try:
                result = self._backend.infer(packet)
                if type(result) is not NativeResult:
                    raise ValueError("native backend result type")
                result.validate()
                if result.identity != packet.identity:
                    raise ValueError("backend changed original camera identity")
            except Exception as caught:
                error = f"{type(caught).__name__}: {caught}"
            with self._condition:
                self._busy = False
                self._counts.completed += 1
                if generation != self._generation or self._stopped:
                    self._counts.obsolete += 1
                else:
                    try:
                        source, wall = self._now()
                        if error is not None:
                            raise ValueError(error)
                        if (
                            source >= result.expires_ns
                            or wall >= packet.received_wall_ns + LIFETIME_NS
                        ):
                            self._counts.late += 1
                            self._current = None
                            self._last_error = "completion deadline"
                        else:
                            self._current = result
                            self._current_wall_expiry = (
                                packet.received_wall_ns + LIFETIME_NS
                            )
                            self._counts.published += 1
                            self._last_error = None
                    except Exception as caught:
                        self._counts.errors += 1
                        self._current = None
                        self._last_error = str(caught)
                self._condition.notify_all()

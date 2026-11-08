"""Bounded latest-frame inference owner with session and completion admission."""

from dataclasses import asdict, dataclass
import threading
import time
from .contract import CameraFrame, PerceptionResult, LIFETIME_NS, uint
from .preparation import Preparation, PROBE_CALLS, probe_frame


@dataclass
class Counters:
    submitted: int = 0
    overwritten: int = 0
    started: int = 0
    completed: int = 0
    published: int = 0
    rejected: int = 0
    errors: int = 0
    late: int = 0
    obsolete: int = 0
    cancelled: int = 0
    invalidated: int = 0


class LatestFrameWorker:
    """source_now belongs to the declared camera clock, wall_now is monotonic ns.

    No queue, thread, or model is shared with a control owner. A stuck backend
    cannot be cancelled safely; close(timeout) reports False in that case.
    """

    def __init__(
        self,
        backend,
        source_now,
        wall_now=time.monotonic_ns,
        *,
        require_preparation=False,
    ):
        self._backend, self._source_now, self._wall_now = backend, source_now, wall_now
        self._condition = threading.Condition()
        self._counts = Counters()
        self._epoch = self._clock = self._generation = 0
        self._enable = self._last_source = self._last_wall = 0
        self._last_frame = self._last_acquisition = 0
        self._clock_fault = False
        self._pending = self._current = None
        self._current_wall_expiry = 0
        self._busy = self._stopped = False
        self._last_error = None
        self._preparation = Preparation(require_preparation)
        self._prepare_pending = False
        self._thread = threading.Thread(
            target=self._run, name="m10-perception", daemon=True
        )
        self._thread.start()

    def _preparation_clock(self):
        try:
            self._preparation.observe(self._wall_now())
        except Exception:
            self._preparation.fail("preparation clock unavailable")

    def prepare(self):
        """Request three explicit probes on the inference owner; never a session."""
        with self._condition:
            if self._stopped:
                return False
            try:
                if not self._preparation.begin(self._wall_now()):
                    return False
            except Exception:
                return False
            self._prepare_pending = True
            self._condition.notify_all()
            return True

    def wait_ready(self, timeout=10):
        """Startup helper only. Timeout does not cancel or hide a running backend."""
        deadline = time.monotonic() + timeout
        with self._condition:
            while True:
                self._preparation_clock()
                if self._stopped or self._preparation.state != "PREPARING":
                    return not self._stopped and self._preparation.ready
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(min(remaining, 0.05))

    def invalidate(self, reason):
        """An adapter loss/error invalidates both published and in-flight output."""
        with self._condition:
            self._counts.invalidated += 1
            self._generation += 1
            self._current = None
            self._last_error = str(reason)
            if self._pending is not None:
                self._counts.cancelled += 1
                self._pending = None
            self._condition.notify_all()

    def _clocks(self):
        try:
            source, wall = self._source_now(), self._wall_now()
        except Exception as error:
            self._clock_fault = True
            self._current = None
            self._last_error = "clock_unavailable"
            raise ValueError("clock unavailable") from error
        if (
            not uint(source)
            or not uint(wall)
            or source < self._last_source
            or wall < self._last_wall
        ):
            self._clock_fault = True
            self._current = None
            self._last_error = "clock_regression"
            raise ValueError("clock regression/type")
        self._last_source, self._last_wall = source, wall
        return source, wall

    def start_session(self, epoch, clock_instance, enable_ns):
        with self._condition:
            self._preparation_clock()
            if not self._preparation.ready:
                return False
            try:
                source, wall = self._source_now(), self._wall_now()
            except Exception:
                self._clock_fault = True
                self._current = None
                self._last_error = "clock_unavailable"
                return False
            if (
                not uint(source)
                or not uint(wall)
                or wall < self._last_wall
                or (clock_instance == self._clock and source < self._last_source)
            ):
                self._clock_fault = True
                self._current = None
                self._last_error = "clock_regression"
                return False
            if (
                self._stopped
                or not uint(epoch, 2**32 - 1, True)
                or epoch <= self._epoch
                or not uint(clock_instance, positive=True)
                or not uint(enable_ns)
                or not uint(source)
                or not uint(wall)
                or wall < self._last_wall
                or enable_ns > source
                or (
                    clock_instance == self._clock
                    and (source < self._last_source or enable_ns < self._last_source)
                )
            ):
                return False
            self._epoch, self._clock, self._enable = epoch, clock_instance, enable_ns
            self._last_source, self._last_wall = source, wall
            self._generation += 1
            self._last_frame = self._last_acquisition = 0
            self._clock_fault = False
            self._current = None
            self._last_error = None
            if self._pending is not None:
                self._counts.cancelled += 1
                self._pending = None
            return True

    def submit(self, frame: CameraFrame, *, received_wall_ns=None):
        with self._condition:
            try:
                self._preparation_clock()
                if not self._preparation.ready:
                    raise ValueError("backend not prepared")
                frame.validate()
                source, wall = self._clocks()
                received = wall if received_wall_ns is None else received_wall_ns
                identity = frame.identity
                if (
                    self._stopped
                    or not uint(received)
                    or not received <= wall < received + LIFETIME_NS
                    or self._clock_fault
                    or not self._epoch
                    or (identity.epoch, identity.clock_instance)
                    != (self._epoch, self._clock)
                    or identity.source_ns < self._enable
                    or not identity.source_ns
                    <= source
                    < identity.source_ns + LIFETIME_NS
                    or identity.frame <= self._last_frame
                    or (
                        self._last_frame
                        and identity.source_ns <= self._last_acquisition
                    )
                ):
                    raise ValueError("frame admission")
            except (ValueError, TypeError, AttributeError) as error:
                self._counts.rejected += 1
                self._current = None
                self._last_error = str(error)
                # A result already in flight must not reopen availability after
                # a newer invalid submission. A new valid frame can recover.
                self._generation += 1
                if self._pending is not None:
                    self._counts.cancelled += 1
                    self._pending = None
                return False
            self._last_frame, self._last_acquisition = (
                identity.frame,
                identity.source_ns,
            )
            self._counts.submitted += 1
            if self._pending is not None:
                self._counts.overwritten += 1
            self._pending = (self._generation, frame, received)
            self._condition.notify_all()
            return True

    def snapshot(self):
        with self._condition:
            try:
                source, wall = self._clocks()
            except ValueError:
                return None
            if (
                self._stopped
                or self._clock_fault
                or self._current is None
                or source >= self._current.expires_ns
                or wall >= self._current_wall_expiry
            ):
                return None
            return self._current

    def status(self):
        with self._condition:
            self._preparation_clock()
            return dict(
                counters=asdict(self._counts),
                busy=self._busy,
                pending=self._pending is not None,
                stop_requested=self._stopped,
                stopped=not self._thread.is_alive(),
                clock_fault=self._clock_fault,
                last_error=self._last_error,
                preparation=self._preparation.snapshot(),
            )

    def drain(self, timeout=5):
        """Test/offline lifecycle helper, never called by a controller."""
        with self._condition:
            return self._condition.wait_for(
                lambda: not self._busy
                and self._pending is None
                and not self._prepare_pending,
                timeout,
            )

    def close(self, timeout=5):
        with self._condition:
            self._stopped = True
            self._preparation.cancel()
            self._prepare_pending = False
            self._current = None
            if self._pending is not None:
                self._counts.cancelled += 1
                self._pending = None
            self._condition.notify_all()
        self._thread.join(timeout)
        return not self._thread.is_alive()

    def _run(self):
        while True:
            with self._condition:
                self._condition.wait_for(
                    lambda: self._pending is not None
                    or self._prepare_pending
                    or self._stopped
                )
                if self._stopped:
                    return
                if self._prepare_pending:
                    self._prepare_pending = False
                    preparing = True
                else:
                    preparing = False
                self._busy = True
                if not preparing:
                    generation, frame, submitted = self._pending
                    self._pending = None
                    self._counts.started += 1
            if preparing:
                self._run_preparation()
                with self._condition:
                    self._busy = False
                    self._condition.notify_all()
                continue
            result, error = None, None
            try:
                result = self._backend.infer(frame)
                if type(result) is not PerceptionResult:
                    raise ValueError("backend result type")
                result.validate()
                if result.identity != frame.identity:
                    raise ValueError("backend changed camera identity")
            except Exception as caught:  # Backend failure is an unavailable result, never an empty road.
                error = f"{type(caught).__name__}: {caught}"
            with self._condition:
                self._counts.completed += 1
                self._busy = False
                if generation != self._generation or self._stopped:
                    self._counts.obsolete += 1
                else:
                    try:
                        source, wall = self._clocks()
                        if self._clock_fault:
                            raise ValueError("clock fault latched")
                        if error is not None:
                            raise ValueError(error)
                        if (
                            source >= result.expires_ns
                            or wall - submitted >= LIFETIME_NS
                        ):
                            self._counts.late += 1
                            self._current = None
                            self._last_error = "deadline"
                        else:
                            self._current = result
                            self._current_wall_expiry = submitted + LIFETIME_NS
                            self._counts.published += 1
                            self._last_error = None
                    except (ValueError, TypeError, AttributeError) as caught:
                        self._counts.errors += 1
                        self._current = None
                        self._last_error = str(caught)
                self._condition.notify_all()

    def _run_preparation(self):
        for number in range(1, PROBE_CALLS + 1):
            call = {"number": number}
            try:
                camera = probe_frame(number)
                with self._condition:
                    self._preparation_clock()
                    if self._preparation.state != "PREPARING":
                        return
                    before = self._wall_now()
                call["started_wall_ns"] = before
                result = self._backend.infer(camera)
                if type(result) is not PerceptionResult:
                    raise ValueError("preparation result type")
                result.validate()
                if result.identity != camera.identity:
                    raise ValueError("preparation identity changed")
                call.update(
                    preprocess_ns=result.preprocess_ns,
                    inference_ns=result.inference_ns,
                    postprocess_ns=result.postprocess_ns,
                    detection_count=len(result.detections),
                )
            except Exception as error:
                call["error"] = f"{type(error).__name__}: {error}"
            with self._condition:
                try:
                    now = self._wall_now()
                    self._preparation.observe(now)
                    if (
                        uint(now)
                        and "started_wall_ns" in call
                        and now >= call["started_wall_ns"]
                    ):
                        call["elapsed_wall_ns"] = now - call["started_wall_ns"]
                    else:
                        call["error"] = "preparation clock regression/type"
                except Exception:
                    now = None
                    call["error"] = "preparation clock unavailable"
                self._preparation.complete_call(call, now)
                self._condition.notify_all()

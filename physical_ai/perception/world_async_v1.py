"""Observed asynchronous world clock; no synthetic ticks or actuation authority.

Only real snapshots can authenticate a camera acquisition. Missing observations
are counted, never interpolated. State silence invalidates perception after
100ms; a new snapshot permits new input, but never revives an old result.
"""

from collections import OrderedDict
from copy import deepcopy
import threading

from .contract import LIFETIME_NS, uint
from .native_startup_v1 import PreparedNativePerception

STEP_NS = 10_000_000
TRACE_CAPACITY = 4096


class ObservedWorldClock:
    def __init__(self, clock_instance, *, step_ns=STEP_NS):
        if not uint(clock_instance, positive=True):
            raise ValueError("world instance")
        if type(step_ns) is not int or step_ns not in (5_000_000, STEP_NS):
            raise ValueError("declared world step must be5ms or10ms")
        self.instance = clock_instance
        self._step_ns = step_ns
        self._lock = threading.RLock()
        self._frames = OrderedDict()
        self._frame = self._source = self._receipt = 0
        self._failed = False
        self._counts = dict(accepted=0, missing=0, duplicate=0, reordered=0)

    def observe(self, instance, frame, source_ns, delta_ns, received_wall_ns, wall):
        with self._lock:
            try:
                if (
                    self._failed
                    or instance != self.instance
                    or not uint(instance, positive=True)
                    or not uint(frame, positive=True)
                    or not all(
                        uint(v) for v in (source_ns, delta_ns, received_wall_ns, wall)
                    )
                    or abs(delta_ns - self._step_ns) > 1000
                    or received_wall_ns > wall
                ):
                    raise ValueError("world snapshot identity/period/receipt")
                if self._frames:
                    gap = frame - self._frame
                    if (
                        abs(source_ns - self._source - gap * self._step_ns)
                        > max(1, abs(gap)) * 1000
                    ):
                        raise ValueError("world frame/time mismatch")
                    if gap <= 0:
                        disposition = "duplicate" if gap == 0 else "reordered"
                        self._counts[disposition] += 1
                        return disposition
                    self._counts["missing"] += gap - 1
                self._frame, self._source, self._receipt = (
                    frame,
                    source_ns,
                    received_wall_ns,
                )
                self._frames[frame] = source_ns
                if len(self._frames) > 128:
                    self._frames.popitem(last=False)
                self._counts["accepted"] += 1
                return "accepted"
            except Exception:
                self._failed = True
                raise

    def now(self):
        with self._lock:
            if self._failed or not self._frames:
                raise ValueError("observed world clock unavailable")
            return self._source

    def matches(self, identity):
        with self._lock:
            if self._failed or identity.clock_instance != self.instance:
                return False
            if identity.frame > self._frame:
                return None
            source = self._frames.get(identity.frame)
            return source is not None and abs(source - identity.source_ns) <= 1000

    def status(self):
        with self._lock:
            return dict(
                initialized=bool(self._frames),
                failed=self._failed,
                frame=self._frame,
                source_ns=self._source,
                received_wall_ns=self._receipt,
                counters=dict(self._counts),
            )


class WorldAsyncPerception(PreparedNativePerception):
    """Prepared owner with atomic state/result reads and bounded silence telemetry."""

    def __init__(self, backend, clock, wall_now=None):
        self._state_stale = False
        self._liveness_rows = []
        self._liveness_overflow = 0
        super().__init__(backend, clock, wall_now)

    def _liveness(self, kind, source, wall, state):
        row = dict(
            kind=kind,
            source_ns=source,
            wall_ns=wall,
            state_frame=state["frame"],
            received_wall_ns=state["received_wall_ns"],
            started=self._counts.started,
            completed=self._counts.completed,
        )
        if len(self._liveness_rows) < TRACE_CAPACITY:
            self._liveness_rows.append(row)
        else:
            self._liveness_overflow += 1

    def _now(self):
        state = self._clock.status()
        if not state["initialized"] and not state["failed"]:
            raise ValueError("waiting for first actual world snapshot")
        source, wall = super()._now()
        if wall >= state["received_wall_ns"] + LIFETIME_NS:
            if not self._state_stale:
                self._state_stale = True
                self._invalidate("observed world state silent for100ms")
            self._liveness("stale_read", source, wall, state)
            raise ValueError("observed world state silent for100ms")
        if self._state_stale:
            self._state_stale = False
            self._liveness("fresh_observation", source, wall, state)
        return source, wall

    def observe_snapshot(self, instance, frame, source_ns, delta_ns, received_wall_ns):
        with self._condition:
            if self._stopped:
                return "stopped"
            try:
                disposition = self._clock.observe(
                    instance,
                    frame,
                    source_ns,
                    delta_ns,
                    received_wall_ns,
                    self._wall_now(),
                )
            except Exception as error:
                self._clock_fault = True
                self._invalidate(str(error))
                return "fault"
            try:
                self._now()
            except ValueError:
                if self._clock_fault:
                    return "fault"
            self._condition.notify_all()
            return disposition

    def observe_tick(self, frame, source_ns):
        raise ValueError("use actual world snapshot with original receipt")

    def start_observed_session(self, epoch):
        with self._condition:
            try:
                return self.start_session(epoch, self._clock.now())
            except ValueError:
                return False

    def observation(self):
        """One lock covers actual state, read time and immutable result selection."""
        with self._condition:
            result = None
            try:
                source, wall = self._now()
                current = self._current
                if (
                    not self._stopped
                    and current is not None
                    and source < current.expires_ns
                    and wall < self._current_wall_expiry
                ):
                    result = current
            except ValueError:
                source, wall = None, self._wall_now()
            return dict(
                result=result,
                source_ns=source,
                wall_ns=wall,
                state=self._clock.status(),
            )

    def snapshot(self):
        return self.observation()["result"]

    def world_status(self):
        with self._condition:
            return dict(
                clock=self._clock.status(),
                stale=self._state_stale,
                rows=deepcopy(self._liveness_rows),
                overflow=self._liveness_overflow,
                capacity=TRACE_CAPACITY,
            )

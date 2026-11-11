"""2K owner with the unchanged actual-snapshot clock and exclusive deadlines."""

from copy import deepcopy
from .contract import LIFETIME_NS
from .native_startup_2k_v1 import PreparedNativePerception
from .world_async_v1 import ObservedWorldClock, TRACE_CAPACITY

__all__ = ["ObservedWorldClock", "WorldAsyncPerception"]


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

"""Opt-in bounded completion telemetry; V1 admission and capacities unchanged."""

from copy import deepcopy
from dataclasses import asdict
import time

from .async_native_v1 import AsyncNativePerception, NativeResult
from .contract import LIFETIME_NS


class TracedNativePerception(AsyncNativePerception):
    def __init__(self, backend, clock, wall_now=None, trace_capacity=512):
        if type(trace_capacity) is not int or not 1 <= trace_capacity <= 4096:
            raise ValueError("bounded decision trace capacity")
        self._decisions, self._trace_overflow, self._trace_capacity = (
            [],
            0,
            trace_capacity,
        )
        if wall_now is None:
            super().__init__(backend, clock)
        else:
            super().__init__(backend, clock, wall_now)

    def decision_trace(self):
        # Diagnostic/lifecycle only, never called from callback or consumer jobs.
        with self._condition:
            return dict(
                rows=deepcopy(self._decisions),
                overflow=self._trace_overflow,
                capacity=self._trace_capacity,
            )

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
                started_source, started_wall = source, wall
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
            returned_wall = time.monotonic_ns()
            with self._condition:
                decision = dict(
                    identity=asdict(packet.identity),
                    received_wall_ns=packet.received_wall_ns,
                    started_source_ns=started_source,
                    started_wall_ns=started_wall,
                    backend_return_monotonic_ns=returned_wall,
                    decision_source_ns=None,
                    decision_wall_ns=None,
                    source_expired=None,
                    receipt_expired=None,
                    outcome=None,
                )
                self._busy = False
                self._counts.completed += 1
                if generation != self._generation or self._stopped:
                    self._counts.obsolete += 1
                    decision["outcome"] = "obsolete"
                else:
                    try:
                        source, wall = self._now()
                        decision.update(
                            decision_source_ns=source,
                            decision_wall_ns=wall,
                            source_expired=source
                            >= packet.identity.source_ns + LIFETIME_NS,
                            receipt_expired=wall
                            >= packet.received_wall_ns + LIFETIME_NS,
                        )
                        if error is not None:
                            raise ValueError(error)
                        if (
                            source >= result.expires_ns
                            or wall >= packet.received_wall_ns + LIFETIME_NS
                        ):
                            self._counts.late += 1
                            decision["outcome"] = "late"
                            self._current = None
                            self._last_error = "completion deadline"
                        else:
                            self._current = result
                            self._current_wall_expiry = (
                                packet.received_wall_ns + LIFETIME_NS
                            )
                            self._counts.published += 1
                            decision["outcome"] = "published"
                            self._last_error = None
                    except Exception as caught:
                        self._counts.errors += 1
                        decision["outcome"] = "errors"
                        self._current = None
                        self._last_error = str(caught)
                if len(self._decisions) < self._trace_capacity:
                    self._decisions.append(decision)
                else:
                    self._trace_overflow += 1
                self._condition.notify_all()

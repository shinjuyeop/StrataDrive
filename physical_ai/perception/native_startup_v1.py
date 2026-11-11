"""Opt-in native4K preparation on the same owner that later handles sensors.

Preparation is never a camera observation or driving readiness. Every cold
probe remains in a separate startup denominator; no probe result is published.
"""

from dataclasses import asdict
import threading
import time

import numpy as np

from .async_native_trace_v1 import TracedNativePerception
from .async_native_v1 import BgraPacket, NativeResult, WIDTH, HEIGHT
from .contract import FrameIdentity
from .preparation import Preparation, PROBE_CALLS, PREPARATION_BUDGET_NS


def synthetic_bgra():
    """Deterministic4K BGRA version of the existing independent RGB XY gradient."""
    x = np.arange(WIDTH, dtype=np.uint16)[None, :]
    y = np.arange(HEIGHT, dtype=np.uint16)[:, None]
    bgra = np.empty((HEIGHT, WIDTH, 4), np.uint8)
    bgra[:, :, 2] = x % 256
    bgra[:, :, 1] = y % 256
    bgra[:, :, 0] = (x + y) % 256
    bgra[:, :, 3] = 255
    return bgra.tobytes()


class PreparedNativePerception(TracedNativePerception):
    def __init__(self, backend, clock, wall_now=None, trace_capacity=4096):
        # Reuse only the proven10s/3-call/last-two<100ms state machine. Native
        # image generation, typed results and publication isolation live here.
        self._preparation = Preparation(required=True)
        self._prepare_requested = False
        self._preparation_busy = False
        super().__init__(backend, clock, wall_now, trace_capacity)

    def prepare(self):
        with self._condition:
            if self._stopped or not self._preparation.begin(self._wall_now()):
                return False
            self._prepare_requested = True
            self._condition.notify_all()
            return True

    def preparation_status(self):
        with self._condition:
            self._preparation.observe(self._wall_now())
            return self._preparation.snapshot()

    def status(self):
        with self._condition:
            self._preparation.observe(self._wall_now())
            result = super().status()
            result.update(
                preparation_state=self._preparation.state,
                preparation_busy=self._preparation_busy,
            )
            return result

    def wait_prepared(self, timeout=10):
        """Setup/lifecycle only. Never called by a live state/consumer owner."""
        until = time.monotonic() + timeout
        with self._condition:
            while self._preparation.state == "PREPARING" and not self._stopped:
                self._preparation.observe(self._wall_now())
                remaining = until - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(min(remaining, 0.05))
            return self._preparation.state == "READY" and not self._stopped

    def start_session(self, epoch, enable_ns):
        with self._condition:
            self._preparation.observe(self._wall_now())
            if self._preparation.state != "READY":
                return False
            return super().start_session(epoch, enable_ns)

    def offer(self, frame, timestamp_seconds, width, height, raw_bgra):
        with self._condition:
            self._preparation.observe(self._wall_now())
            if self._preparation.state != "READY":
                self._counts.offered += 1
                self._counts.rejected += 1
                self._invalidate("native preparation is not ready")
                return False
        return super().offer(frame, timestamp_seconds, width, height, raw_bgra)

    def close(self, timeout=5):
        with self._condition:
            self._preparation.cancel()
            self._condition.notify_all()
        return super().close(timeout)

    def _run(self):
        with self._condition:
            self._condition.wait_for(lambda: self._prepare_requested or self._stopped)
            if self._stopped:
                return
        raw = None
        for number in range(1, PROBE_CALLS + 1):
            with self._condition:
                self._preparation.observe(self._wall_now())
                if self._stopped or self._preparation.state != "PREPARING":
                    return
                self._preparation_busy = True
            row = dict(
                number=number,
                owner_thread_id=threading.get_ident(),
                begin_wall_ns=self._wall_now(),
                synthetic=True,
                published=False,
            )
            try:
                if raw is None:
                    raw = synthetic_bgra()
                packet = BgraPacket(
                    FrameIdentity(1, 1, number, 0), raw, row["begin_wall_ns"]
                )
                result = self._backend.infer(packet)
                if (
                    type(result) is not NativeResult
                    or result.identity != packet.identity
                ):
                    raise ValueError("native preparation result identity/type")
                result.validate()
                row["result"] = asdict(result)
            except Exception as error:
                row["error"] = f"{type(error).__name__}: {error}"
            now = self._wall_now()
            row.update(end_wall_ns=now, elapsed_wall_ns=now - row["begin_wall_ns"])
            with self._condition:
                self._preparation_busy = False
                self._preparation.complete_call(row, now)
                self._condition.notify_all()
                if self._stopped or self._preparation.state not in (
                    "PREPARING",
                    "READY",
                ):
                    return
        del raw
        with self._condition:
            if self._preparation.state != "READY" or self._stopped:
                return
            if (
                self._preparation.report["finished_wall_ns"]
                - self._preparation.report["started_wall_ns"]
                >= PREPARATION_BUDGET_NS
            ):
                raise AssertionError("preparation state machine budget")
        # The thread/ORT context stays the same; only now enable sensor processing.
        super()._run()

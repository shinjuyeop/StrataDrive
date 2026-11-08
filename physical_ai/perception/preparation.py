"""Explicit startup probes, never camera observations or driving readiness.

The worker owns this state under its condition lock. No inference is cancelled:
an overdue backend stays busy, and late completion cannot reopen readiness.
"""

from copy import deepcopy
import json
from .contract import CameraFrame, FrameIdentity, PROFILE_PATH, WIDTH, HEIGHT, uint

STARTUP_PROFILE_PATH = PROFILE_PATH.with_name("perception-startup-host-v1.json")
PREPARATION_BUDGET_NS = 10_000_000_000
SETTLED_BUDGET_NS = 100_000_000
PROBE_CALLS = 3


def startup_profile():
    value = json.loads(STARTUP_PROFILE_PATH.read_text())
    if value != {
        "schema": "m10-perception-startup-host-v1",
        "semantic_profile": "m10-perception-host-v1",
        "probe": "rgb-xy-gradient-v1",
        "probe_calls": PROBE_CALLS,
        "preparation_budget_ns": PREPARATION_BUDGET_NS,
        "settled_call_budget_ns": SETTLED_BUDGET_NS,
        "settled_calls": 2,
        "retry": "new_worker_only",
        "sensor_output_during_preparation": False,
        "startup_cost_recorded": True,
    }:
        raise ValueError("startup profile/executable mismatch")
    return value


def probe_frame(number):
    # Deterministic synthetic input, independent of recorded/evaluation imagery.
    # Camera identity is synthetic and is never submitted to a sensor session.
    rgb = bytes(
        v
        for y in range(HEIGHT)
        for x in range(WIDTH)
        for v in (x % 256, y % 256, (x + y) % 256)
    )
    return CameraFrame(FrameIdentity(1, 1, number, 0), rgb)


class Preparation:
    def __init__(self, required):
        if type(required) is not bool:
            raise ValueError("preparation flag must be bool")
        if required:
            startup_profile()
        self.report = {
            "state": "NOT_REQUESTED" if required else "NOT_REQUIRED",
            "started_wall_ns": None,
            "finished_wall_ns": None,
            "last_observed_wall_ns": None,
            "error": None,
            "calls": [],
        }

    @property
    def state(self):
        return self.report["state"]

    @property
    def ready(self):
        return self.state in ("READY", "NOT_REQUIRED")

    def fail(self, reason, now=None):
        if self.state == "PREPARING":
            self.report.update(state="FAILED", error=reason, finished_wall_ns=now)

    def observe(self, now):
        if self.state != "PREPARING":
            return
        last = self.report["last_observed_wall_ns"]
        if not uint(now) or now < last:
            self.fail("preparation clock regression/type")
        else:
            self.report["last_observed_wall_ns"] = now
            if now - self.report["started_wall_ns"] >= PREPARATION_BUDGET_NS:
                self.fail("preparation deadline", now)

    def begin(self, now):
        if self.state != "NOT_REQUESTED" or not uint(now):
            return False
        self.report.update(
            state="PREPARING", started_wall_ns=now, last_observed_wall_ns=now
        )
        return True

    def complete_call(self, call, now):
        self.report["calls"].append(call)
        self.observe(now)
        if self.state != "PREPARING":
            return
        if call.get("error"):
            self.fail(call["error"], now)
        elif call["number"] > 1 and call["elapsed_wall_ns"] >= SETTLED_BUDGET_NS:
            self.fail("settled probe deadline", now)
        elif call["number"] == PROBE_CALLS:
            self.report.update(state="READY", finished_wall_ns=now)

    def cancel(self):
        if self.state in ("NOT_REQUESTED", "PREPARING", "READY"):
            self.report.update(state="CANCELLED", error="stop requested")

    def snapshot(self):
        return deepcopy(self.report)

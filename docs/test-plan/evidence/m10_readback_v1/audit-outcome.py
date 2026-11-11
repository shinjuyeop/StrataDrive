"""Offline integrity replay: retain the observed rejection, never turn it into acceptance."""

from unittest.mock import patch
from pathlib import Path
import runpy


import audit_carla_world_async_v1 as world
from audit_carla_readback_v1 import audit_capture

metrics = runpy.run_path(str(Path(__file__).with_name("timing.py")))["metrics"]

REASON = "fresh consumption in each of five source segments"


def outcome(report, expected_failure=None):
    metrics(report)
    if expected_failure is None:
        result = audit_capture(report)
        assert result == report["audit"]
        return result
    assert expected_failure == REASON
    assert report["status"] == "FAIL" and not report.get("error")
    assert report["schema"] == "m10-carla-readback-v1"
    assert report["condition"] == "deferred-02"
    assert ("ValueError: " + REASON) in report["audit_error"]
    rejected = []

    def collect(value, reason):
        if not value:
            rejected.append(reason)

    # Check every subsequent invariant as well; precisely one known availability
    # rejection is required. Original report/source bytes remain unchanged.
    with patch.object(world, "require", collect):
        replay = world.audit(dict(report, status="PASS", condition="async-01"))
    assert rejected == [REASON], rejected
    return dict(
        replay, status="REJECTED", acceptance=False, rejected_requirements=rejected
    )

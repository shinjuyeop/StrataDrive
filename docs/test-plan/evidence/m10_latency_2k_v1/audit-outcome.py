"""Replay all invariants while retaining the specific observed availability rejection."""

from pathlib import Path
import runpy
from unittest.mock import patch
import audit_carla_latency_2k_v1 as audit
import audit_carla_source_compare_v1 as original

metrics = runpy.run_path(str(Path(__file__).with_name("timing.py")))["metrics"]
REASON = "fresh consumption in each of five source segments"


def outcome(report, expected_failure=None):
    metrics(report)
    if expected_failure is None:
        result = audit.audit_capture(report)
        assert result == report["audit"]
        return result
    assert (
        expected_failure == REASON
        and report["status"] == "FAIL"
        and not report.get("error")
    )
    assert ("ValueError: " + REASON) in report["audit_error"]
    rejected = []

    def collect(value, reason):
        if not value:
            rejected.append(reason)

    with patch.object(original, "require", collect):
        replay = audit.audit_capture(dict(report, status="PASS"))
    assert rejected == [REASON], rejected
    return dict(
        replay, status="REJECTED", acceptance=False, rejected_requirements=rejected
    )

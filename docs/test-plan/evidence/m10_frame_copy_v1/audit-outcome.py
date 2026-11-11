"""Frozen semantic replay and independently recomputed timing metrics."""

from pathlib import Path
import runpy
from audit_carla_frame_copy_v1 import audit_capture

metrics = runpy.run_path(str(Path(__file__).with_name("timing.py")))["metrics"]


def outcome(report, expected_failure=None):
    assert expected_failure is None
    metrics(report)
    result = audit_capture(report)
    assert result == report["audit"]
    return result

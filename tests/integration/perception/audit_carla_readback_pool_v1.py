"""Largest-request render-target allocation experiment; same raw/clock semantics."""

from audit_async_native_v1 import require
from audit_carla_readback_v1 import audit_capture as original_capture
from audit_carla_readback_v1 import audit_readback as original_readback

CONDITIONS = {"pool-baseline-01": "baseline-01", "pool-deferred-01": "deferred-01"}


def normalized(report):
    require(report["condition"] in CONDITIONS, "pool condition")
    require(report["schema"] == "m10-carla-readback-pool-v1", "pool schema")
    return dict(
        report,
        condition=CONDITIONS[report["condition"]],
        schema="m10-carla-readback-v1",
    )


def audit_capture(report):
    return original_capture(normalized(report))


def audit_readback(report, log):
    require('r.SceneRenderTargetResizeMethod = "2"' in log, "observed resize policy")
    require(
        'r.SceneRenderTargetResizeMethodForceOverride = "1"' in log,
        "observed resize override",
    )
    return original_readback(normalized(report), log)

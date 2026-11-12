"""Preserve original contracts while auditing explicit tensor/readback variants."""

from audit_async_native_v1 import require
from audit_carla_source_compare_v1 import audit_capture as original_capture
from audit_carla_readback_pool_v1 import audit_readback as original_readback

CONDITIONS = {
    "baseline-01": ("baseline",),
    "tensor-01": ("tensor",),
    "balanced-01": ("balanced",),
    "confirm-01": ("tensor", "balanced"),
}


def check_variant(r):
    require(
        r["schema"] == "m10-carla-latency-2k-v1"
        and r["condition"] in CONDITIONS
        and r["variant"] in CONDITIONS[r["condition"]],
        "declared condition/variant",
    )


def audit_capture(r):
    check_variant(r)
    return original_capture(
        dict(r, schema="m10-carla-source-compare-v1", condition="source-2k-01")
    )


def audit_readback(r, log):
    check_variant(r)
    deferred = r["variant"] == "balanced"
    if deferred:
        require('t.MaxFPS = "100"' in log, "observed engine tick cap100")
    return original_readback(
        dict(
            r,
            schema="m10-carla-readback-pool-v1",
            condition="pool-deferred-01" if deferred else "pool-baseline-01",
        ),
        log,
    )

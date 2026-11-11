"""Small main viewport, unchanged4K sensor and original snapshot/clock contracts."""

from audit_async_native_v1 import require
from audit_carla_frame_copy_v1 import audit_capture as parent_capture
from audit_carla_frame_copy_v1 import audit_readback as parent_readback

CONDITIONS = ("viewport-small-01", "viewport-small-02")


def normalized(r):
    require(
        r["condition"] in CONDITIONS and r["schema"] == "m10-carla-viewport-v1",
        "viewport identity",
    )
    return dict(r, condition="copy-prefault-01", schema="m10-carla-frame-copy-v1")


def audit_capture(r):
    return parent_capture(normalized(r))


def audit_readback(r, log):
    before = log.split("STRATA_READBACK_V1 ", 1)[0]
    require(
        "Reallocating scene render targets to support 128x128 " in before,
        "observed initial main viewport",
    )
    return parent_readback(normalized(r), log)

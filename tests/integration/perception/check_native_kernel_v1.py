#!/usr/bin/env python3
"""Every84 consumed native4K development frame: Pillow versus native CPU input."""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.async_native_v1 import BgraPacket, WIDTH, HEIGHT
from physical_ai.perception.camera_resolution_v1 import NativeDataset, unpack
from physical_ai.perception.contract import FrameIdentity, sha256_file
from physical_ai.perception.native_kernel_v1 import NativeResize
from physical_ai.perception.native_preprocess_v1 import prepare_packet
from physical_ai.perception.run import distribution
from probe_async_native_v1 import check_sources


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("library", "profile", "freeze", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--media", type=Path, nargs=2, required=True)
    a = p.parse_args()
    if a.output.exists():
        p.error("new output required")
    report = dict(
        schema="m10-native-kernel-equivalence-v1",
        status="FAIL",
        rows=[],
        cold_calls_excluded=0,
        quality_acceptance=False,
    )
    try:
        report["freeze_sha256"] = check_sources(a.freeze)
        profile = json.loads(a.profile.read_text())
        native = NativeResize(a.library, profile["native_library_sha256"])
        cv2.setNumThreads(4)
        for path in a.media:
            data = NativeDataset(path)
            if data.scale != 6:
                raise ValueError("native4K development only")
            m = data.manifest
            for row in m["frames"]:
                raw = unpack(path.parent, row["rgb_raw"], WIDTH, HEIGHT)
                packet = BgraPacket(
                    FrameIdentity(
                        m["epoch"], m["clock_instance"], row["frame"], row["source_ns"]
                    ),
                    raw,
                    time.monotonic_ns(),
                )
                before = time.monotonic_ns()
                old = prepare_packet(packet)
                old_ns = time.monotonic_ns() - before
                before = time.monotonic_ns()
                new = native.prepare(packet)
                native_ns = time.monotonic_ns() - before
                if (
                    any(not np.array_equal(old[0][key], new[0][key]) for key in old[0])
                    or old[1:3] != new[1:3]
                ):
                    raise ValueError("exact tensor/health equality required")
                report["rows"].append(
                    dict(
                        frame=row["frame"],
                        rgb_sha256=row["rgb_sha256"],
                        bgra_sha256=row["rgb_raw"]["sha256"],
                        manifest_sha256=sha256_file(path),
                        tensor_sha256=hashlib.sha256(
                            new[0]["images"].tobytes()
                        ).hexdigest(),
                        tensor_exact=True,
                        health_exact=True,
                        pillow_ns=old_ns,
                        native_ns=native_ns,
                    )
                )
        if (
            len(report["rows"]) != 84
            or check_sources(a.freeze) != report["freeze_sha256"]
        ):
            raise ValueError("all84 and unchanged sources required")
        report["timing"] = {
            k: distribution([r[k] for r in report["rows"]])
            for k in ("pillow_ns", "native_ns")
        }
        report["status"] = "PASS"
    except Exception:
        report["error"] = traceback.format_exc()
    a.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report.get(k) for k in ("status", "timing", "error")}))
    return int(report["status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())

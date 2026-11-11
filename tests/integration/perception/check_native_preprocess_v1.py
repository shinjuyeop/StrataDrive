#!/usr/bin/env python3
"""Compare every consumed native4K development input; never open GT/holdout."""

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.async_native_v1 import BgraPacket, HEIGHT, WIDTH
from physical_ai.perception.camera_resolution_v1 import (
    NativeDataset,
    NativeFrame,
    health,
    prepare,
    unpack,
)
from physical_ai.perception.contract import FrameIdentity, sha256_file
from physical_ai.perception.native_preprocess_v1 import CV_THREADS, prepare_packet
from physical_ai.perception.run import distribution
from probe_async_native_v1 import check_sources


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--media", type=Path, nargs=2, required=True)
    p.add_argument("--freeze", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        p.error("new output required")
    report = dict(
        schema="m10-native-preprocess-equivalence-v1",
        status="FAIL",
        rows=[],
        cold_calls_excluded=0,
        quality_acceptance=False,
        cv_threads=CV_THREADS,
        timing_scope="conversion+health+resize+tensor; no inference/disk",
    )
    try:
        report["freeze_sha256"] = check_sources(a.freeze)
        cv2.setNumThreads(CV_THREADS)
        for manifest in a.media:
            data = NativeDataset(manifest)
            if data.scale != 6:
                raise ValueError("native4K development only")
            m = data.manifest
            for row in m["frames"]:
                raw = unpack(manifest.parent, row["rgb_raw"], WIDTH, HEIGHT)
                identity = FrameIdentity(
                    m["epoch"], m["clock_instance"], row["frame"], row["source_ns"]
                )
                packet = BgraPacket(identity, raw, time.monotonic_ns())
                t = time.monotonic_ns()
                rgb = (
                    np.frombuffer(raw, np.uint8)
                    .reshape(HEIGHT, WIDTH, 4)[:, :, 2::-1]
                    .copy()
                    .tobytes()
                )
                frame = NativeFrame(identity, WIDTH, HEIGHT, rgb)
                old = prepare(frame)
                legacy_ns = time.monotonic_ns() - t
                t = time.monotonic_ns()
                new, values, fallback, convert_ns, prep_ns = prepare_packet(packet)
                fast_ns = time.monotonic_ns() - t
                old_health = health(frame)
                if (
                    hashlib.sha256(rgb).hexdigest() != row["rgb_sha256"]
                    or Image.frombytes(
                        "RGB", (WIDTH, HEIGHT), raw, "raw", "BGRX"
                    ).tobytes()
                    != rgb
                    or any(not np.array_equal(old[k], new[k]) for k in old)
                    or any(abs(values[k] - old_health[k]) > 1e-10 for k in values)
                ):
                    raise ValueError("original RGB/tensor/health mismatch")
                report["rows"].append(
                    dict(
                        identity=asdict(identity),
                        rgb_sha256=row["rgb_sha256"],
                        bgra_sha256=row["rgb_raw"]["sha256"],
                        manifest_sha256=sha256_file(manifest),
                        tensor_sha256=hashlib.sha256(
                            new["images"].tobytes()
                        ).hexdigest(),
                        rgb_exact=True,
                        tensor_exact=True,
                        health=values,
                        legacy_health=old_health,
                        fallback=fallback,
                        legacy_ns=legacy_ns,
                        fast_ns=fast_ns,
                        convert_ns=convert_ns,
                        preprocess_ns=prep_ns,
                    )
                )
        if (
            len(report["rows"]) != 84
            or check_sources(a.freeze) != report["freeze_sha256"]
        ):
            raise ValueError("all84 frames and unchanged source required")
        report["timing"] = {
            k: distribution([r[k] for r in report["rows"]])
            for k in ("legacy_ns", "fast_ns")
        }
        report["status"] = "PASS"
    except Exception:
        report["error"] = traceback.format_exc()
    a.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report.get(k) for k in ("status", "timing", "error")}))
    return int(report["status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())

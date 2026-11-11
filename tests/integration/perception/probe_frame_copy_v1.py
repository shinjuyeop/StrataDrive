#!/usr/bin/env python3
"""Finite synthetic diagnostic; retain every copy, measure allocation separately."""

import argparse
import json
from pathlib import Path
import threading
import time

from physical_ai.perception.frame_copy_v1 import SnapshotPool
from physical_ai.perception.native_startup_v1 import synthetic_bgra
from physical_ai.perception.run import distribution
from physical_ai.perception.contract import sha256_file


def run(library, output):
    source = synthetic_bgra()
    view = memoryview(source)
    rows = []
    for name in ("baseline-01", "prefault-01", "prefault-02", "baseline-02"):
        pool = (
            SnapshotPool(library, sha256_file(library), 16)
            if name.startswith("prefault")
            else None
        )
        before = pool.stats() if pool else None
        stop = threading.Event()
        pulses = []

        def ticker():
            while not stop.wait(0.001):
                pulses.append(time.monotonic_ns())

        thread = threading.Thread(target=ticker)
        thread.start()
        time.sleep(0.02)
        frames = []
        times = []
        begin = time.monotonic_ns()
        for _ in range(16):
            start = time.monotonic_ns()
            frames.append(pool.copy(view, source) if pool else bytes(view))
            times.append(time.monotonic_ns() - start)
        end = time.monotonic_ns()
        stop.set()
        thread.join(2)
        assert not thread.is_alive() and len({id(f) for f in frames}) == 16
        assert all(type(f) is bytes and f == source for f in frames)
        rows.append(
            dict(
                condition=name,
                frames=16,
                copy=distribution(times),
                total_ns=end - begin,
                pool_preparation=before,
                pool_final=pool.stats() if pool else None,
                heartbeat_intervals=distribution(
                    [b - a for a, b in zip(pulses, pulses[1:])]
                ),
                heartbeat_times=pulses,
                copy_times=times,
            )
        )
        del frames
        if pool:
            pool.close()
    result = dict(
        schema="m10-frame-copy-synthetic-v1",
        source="independent synthetic XY gradient",
        exact_copies=64,
        quality_acceptance=False,
        realtime_acceptance=False,
        rows=rows,
    )
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            [
                dict(
                    condition=r["condition"],
                    copy=r["copy"],
                    heartbeat=r["heartbeat_intervals"],
                )
                for r in rows
            ]
        )
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--library", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        p.error("new output required")
    run(a.library, a.output)

"""Measure the same frames on the live worker's CPU set with both CARLA servers stopped."""

import argparse
import fcntl
import json
import os
from pathlib import Path
import time

from m10_asset_cache import stopped
from m10_quality_shadow_trial import ROOT, cap, helper_check, lease, save
from m10_quality_shadow_timing import save_rows
from m10_summarize_latency import distribution
from endurance_recording_v1 import RawReader
from quality_shadow_v1 import detector, predict


def compare(run, output):
    import numpy as np

    server = json.loads((run / "server.json").read_bytes())
    folder = run / "capture/paired/renderer"
    renderer = json.loads((folder / "result.json").read_bytes())
    if not server.get("quality_shadow") or not renderer.get("quality_binding"):
        raise ValueError("recorded six-class case required")
    plan = server["host_resources"]["cpus"]
    cpus = plan.get("pipeline", plan["renderer"])
    output.mkdir(parents=True, exist_ok=False)
    helper_check(ROOT / "tools/m10_boost_lease.py")
    raw = {r["frame"]: r for r in renderer["raw"]}
    samples = []
    reader = RawReader(folder)
    with (ROOT / "build/m10-cuda-resize-v1/launcher.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        stopped()
        if cap() != "100":
            raise ValueError("original cap required")
        os.sched_setaffinity(0, cpus)
        if set(os.sched_getaffinity(0)) != set(cpus):
            raise ValueError("worker CPU affinity")
        try:
            with (
                lease(output),
                detector(
                    renderer["quality_binding"].get("view_indices"),
                    "view_verifier_sha256" in renderer["quality_binding"],
                    "crop_reuse_sha256" in renderer["quality_binding"],
                    "batch_registration_sha256" in renderer["quality_binding"],
                ) as (
                    model,
                    spec,
                ),
            ):
                if renderer["quality_binding"] != spec:
                    raise ValueError("changed model")
                warm = np.empty((1536, 2560, 4), np.uint8)
                warm[:, :, :3] = (np.arange(2560, dtype=np.uint16) % 256)[None, :, None]
                warm[:, :, 3] = 255
                for _ in range(3):
                    predict(model, warm)
                for row in renderer["inference"]:
                    frame = row["renderer_frame"]
                    # Raw I/O and checksum verification precede the measured BGRA-to-box interval.
                    bgra = reader.read(raw[frame])
                    start = time.monotonic_ns()
                    response = predict(model, bgra)
                    elapsed = time.monotonic_ns() - start
                    if response["detections"] != row["detections"]:
                        raise ValueError(f"box mismatch in renderer frame {frame}")
                    samples.append(
                        dict(
                            renderer_frame=frame,
                            rgb_sha256=raw[frame]["rgb_sha256"],
                            replay_ns=elapsed,
                            live_ns=row["end_ns"] - row["begin_ns"],
                            stages_ms=response["stages_ms"],
                        )
                    )
                if cap() != "70":
                    raise RuntimeError("power lease expired during comparison")
            stopped()
        finally:
            reader.close()
    stats = {k: distribution(s[k] for s in samples) for k in ("replay_ns", "live_ns")}
    stats["paired_live_minus_replay"] = distribution(
        s["live_ns"] - s["replay_ns"] for s in samples
    )
    # Keep each original acquisition, queue and read clock when substituting only model cost.
    rows = renderer["inference"]
    sim = [
        row["begin_ns"] - row["original_acquisition_ns"] + s["replay_ns"]
        for row, s in zip(rows, samples)
    ]
    save_rows(output / "samples.json.gz", samples)
    save(
        output / "comparison.json",
        dict(
            frames=len(samples),
            all_boxes_equal=True,
            cpus=cpus,
            cpu_cap_percent=70,
            restored_percent=int(cap()),
            statistics=stats,
            detector_stages={
                k: distribution(round(s["stages_ms"][k] * 1e6) for s in samples)
                for k in samples[0]["stages_ms"]
            },
            estimated_scene_to_boxes_with_isolated_cost=dict(
                **distribution(sim), below_100ms=sum(v < 100_000_000 for v in sim)
            ),
            scope="Paired isolated replay; transport, queue changes and ECU acceptance are not measured by this substitution.",
        ),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    compare(args.run, args.output)

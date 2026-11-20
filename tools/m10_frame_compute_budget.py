"""Measure per-frame compute time available before the latest eligible native read."""

import argparse
from bisect import bisect_left
import gzip
import json
from pathlib import Path

import numpy as np

from m10_native_read_freshness import LIFETIME, timing
from m10_quality_shadow_timing import save_rows
from quality_shadow_v1 import digest


def measure(run, review, output):
    report = json.loads((review / "timing.json").read_bytes())["native"]
    trace = review / "frames.json.gz"
    frames = json.loads(gzip.decompress(trace.read_bytes()))
    observations = run / "capture/native-perception.jsonl"
    start, stop = report["start_wall_ns"], report["stop_wall_ns"]
    states = []
    with observations.open() as stream:
        for line in stream:
            state = json.loads(line)["perception"]
            if start <= state["observed_wall_ns"] < stop:
                states.append(state)
    clocks = [s["observed_wall_ns"] for s in states]
    if len(clocks) != report["native_observations"] or clocks != sorted(clocks):
        raise ValueError("native observations differ")
    sampled = []
    for f in frames:
        begin = f["begin_ns"]
        end = f["original_acquisition_ns"] + LIFETIME
        window = states[bisect_left(clocks, begin) : bisect_left(clocks, end)]
        last = next(
            (
                s["observed_wall_ns"]
                for s in reversed(window)
                if timing(s, f, f) == "time_eligible"
            ),
            None,
        )
        sampled.append(
            dict(
                frame=f["renderer_frame"],
                compute_ns=f["end_ns"] - begin,
                last_eligible_read_ns=last,
                budget_ns=None if last is None else last - begin,
            )
        )
    eligible = [s for s in sampled if s["budget_ns"] is not None]
    if not eligible:
        raise ValueError("no eligible read windows")
    budgets = np.asarray([s["budget_ns"] for s in eligible])
    need = np.asarray([max(0, s["compute_ns"] - s["budget_ns"]) for s in eligible])
    output.mkdir(parents=True, exist_ok=False)
    pairs = output / "budgets.json.gz"
    save_rows(pairs, sampled)
    summary = dict(
        input_frames_sha256=digest(trace),
        native_states_sha256=digest(observations),
        pairs_sha256=digest(pairs),
        frames=len(sampled),
        frames_with_window=len(eligible),
        actual_completion_by_last_eligible_read=int((need == 0).sum()),
        actual_unique_eligible_frames=report["unique_eligible_results"],
        available_compute_ms={
            f"p{p}": float(np.percentile(budgets, p) / 1e6) for p in (5, 50, 95)
        },
        required_saving_ms={
            f"p{p}": float(np.percentile(need, p) / 1e6) for p in (50, 95)
        },
        scope="Per-frame latest eligible poll at fixed worker start, zero transport; newer results can supersede this frame.",
    )
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("run", "review", "output"):
        parser.add_argument(key, type=Path)
    args = parser.parse_args()
    measure(args.run, args.review, args.output)

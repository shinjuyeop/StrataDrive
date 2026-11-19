"""Verify paired V2 runs against the frozen V1 detections, then package their frame-level timing."""

import argparse
import gzip
import json
from pathlib import Path

import numpy as np

from m10_quality_latency import current, old, prior, read
from quality_latency import score_run, tiles


def latency(rows):
    result = {}
    for k in ("elapsed_ms", "raw_to_boxes_ms"):
        times = np.array([r[k] for r in rows])
        if not np.isfinite(times).all() or np.min(times) <= 0:
            raise ValueError("invalid frame duration")
        result[k] = dict(
            frames=len(rows),
            p50=float(np.median(times)),
            p95=float(np.percentile(times, 95)),
            maximum=float(times.max()),
            under_100=int(sum(times < 100)),
        )
    result["mean_stages_ms"] = {
        k: float(np.mean([r["stages_ms"][k] for r in rows]))
        for k in rows[0]["stages_ms"]
    }
    return result


def audit(directories, output):
    if len(set(p.resolve() for p in directories)) != len(directories):
        raise ValueError("distinct replays required")
    previous = current.EVIDENCE.parent / "m10_quality_latency_v1"
    v1 = read(previous / "comparison.json")
    archive = previous / "frames.json.gz"
    if current.sha(archive) != v1["trace_sha256"] or current.nomination() != read(
        current.MARK
    ):
        raise ValueError("reference identity")
    with gzip.open(archive, "rt") as stream:
        original = json.load(stream)["selected"]
    sites = {
        **prior.DEV,
        "holdout": current.BASE / "runs/evaluation-holdout-01",
        "previous60": old.RUN,
        **old.HISTORICAL,
    }
    reference = v1["selected_binding"]
    final = dict(
        previous_trace_sha256=v1["trace_sha256"],
        gpu=v1["gpu"],
        quality=v1["evaluation"]["quality"],
        sites={},
        runs={},
    )
    delivery = read(previous.parent / "m10_cuda_resize_v1" / "latency-300s.json")[
        "statistics"
    ]["scene_to_callback"]["median_ms"]
    final["historical_scene_to_callback_median_ms"] = delivery
    traces = {}
    for number, directory in enumerate(directories, 1):
        name = f"run{number}"
        rows_by_site = {}
        combined = []
        binding = read(directory / "binding.json")
        if binding["mode"] != "targeted" or any(
            binding[k] != reference[k]
            for k in ("reference", "engine_sha256", "library_sha256", "tensorrt")
        ):
            raise ValueError("unexpected model or engine")
        if set(binding["source"]) != set(reference["source"]) | {
            "quality_vehicle_windows.py"
        }:
            raise ValueError("incomplete source binding")
        for filename, digest in binding["source"].items():
            folder = (
                Path(__file__).resolve().parent
                if filename == "m10_quality_latency.py"
                else current.TESTS
            )
            if current.sha(folder / filename) != digest:
                raise ValueError(f"changed implementation {filename}")
        if (
            number > 1
            and binding["source"] != final["runs"]["run1"]["binding"]["source"]
        ):
            raise ValueError("implementations differ")
        if set(p.stem for p in directory.glob("*.json")) != {"binding", *sites}:
            raise ValueError("site coverage")
        for site, run in sites.items():
            replay = read(directory / (site + ".json"))
            rows = replay["rows"]
            if len(rows) != 81:
                raise ValueError("frame count")
            for old_row, r in zip(original[site], rows, strict=True):
                if (r["rgb"], r["base"], r["new"]) != (
                    old_row["rgb"],
                    old_row["base"],
                    old_row["new"],
                ):
                    raise ValueError(f"changed output {site} {r['rgb']}")
                if r["stages_ms"].keys() != old_row["stages_ms"].keys():
                    raise ValueError("timing stage coverage")
                if r["raw_to_boxes_ms"] < r["elapsed_ms"] or not all(
                    np.isfinite(v) and v >= 0 for v in r["stages_ms"].values()
                ):
                    raise ValueError("invalid timing")
            quality = score_run(run, rows, tiles.cycle.OFF)[0]
            if (
                not quality["passed"]
                or quality != replay["quality"]
                or quality != v1["sites"][site]["quality"]
            ):
                raise ValueError(f"quality replay failed {site}")
            rec = final["sites"].setdefault(
                site,
                dict(
                    partition=v1["sites"][site]["partition"],
                    quality=quality["card"]["micro"],
                    absolute=quality["card"]["gates"],
                    relative=quality["relative"]["gates"],
                    previous=latency(original[site]),
                ),
            )
            rec[name] = latency(rows)
            rows_by_site[site] = [
                {
                    k: r[k]
                    for k in (
                        "rgb",
                        "elapsed_ms",
                        "raw_to_boxes_ms",
                        "stages_ms",
                        "dfine_crop_calls",
                    )
                }
                for r in rows
            ]
            if site not in prior.DEV:
                combined.extend(rows)
        final["runs"][name] = dict(
            binding=binding,
            evaluation=latency(combined),
            frames_with_historical_delivery_headroom=sum(
                r["raw_to_boxes_ms"] < 100 - delivery for r in combined
            ),
            first_development_frame_ms=rows_by_site[next(iter(prior.DEV))][0][
                "raw_to_boxes_ms"
            ],
        )
        traces[name] = rows_by_site
    final["previous_evaluation"] = latency(
        [r for site, rows in original.items() if site not in prior.DEV for r in rows]
    )
    for site, summary in final["sites"].items():
        late = [
            {r["rgb"] for r in group[site] if r["raw_to_boxes_ms"] >= 100}
            for group in traces.values()
        ]
        summary["always_late_rgb"] = sorted(set.intersection(*late))
        summary["ever_late"] = len(set.union(*late))
    output.mkdir(parents=True, exist_ok=False)
    path = output / "timings.json.gz"
    path.write_bytes(
        gzip.compress(
            json.dumps(traces, separators=(",", ":"), allow_nan=False).encode(), mtime=0
        )
    )
    final["timings_sha256"] = current.sha(path)
    (output / "comparison.json").write_text(
        json.dumps(final, indent=2, allow_nan=False) + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("replays", nargs="+", type=Path)
    args = parser.parse_args()
    audit(args.replays, args.output)

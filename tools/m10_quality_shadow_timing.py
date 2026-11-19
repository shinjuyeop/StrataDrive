"""Join completed renderer boxes to original images and observed native read times."""

import argparse
from bisect import bisect_right
from collections import Counter
import gzip
import json
from pathlib import Path

from m10_native_read_freshness import analyze, indexed, timing, LIFETIME
from m10_summarize_latency import distribution


def join_reads(frames, states, start, stop):
    ends = [row["end_ns"] for row in frames]
    if ends != sorted(set(ends)):
        raise ValueError("unordered renderer completions")
    reads = []
    previous = 0
    for state in states:
        now = state["observed_wall_ns"]
        if now < previous:
            raise ValueError("unordered native reads")
        previous = now
        if not start <= now < stop:
            continue
        if state["accepted_results"]:
            raise ValueError("unexpected native acceptance in observation-only case")
        index = bisect_right(ends, now) - 1
        frame = frames[index] if index >= 0 else None
        outcome = timing(state, frame, frame)
        if frame is not None and frame["first_native_read_ns"] is None:
            frame["first_native_read_ns"] = now
        reads.append(
            dict(
                observed_wall_ns=now,
                state_frame=state["state_frame"],
                state_source_ns=state["state_source_ns"],
                state_received_wall_ns=state["state_received_wall_ns"],
                renderer_frame=frame["renderer_frame"] if frame else None,
                accepted_results=state["accepted_results"],
                timing=outcome,
            )
        )
    return reads


def save_rows(path, rows):
    with (
        path.open("xb") as out,
        gzip.GzipFile(filename="", fileobj=out, mode="wb", mtime=0) as compressed,
    ):
        compressed.write(
            json.dumps(rows, separators=(",", ":"), allow_nan=False).encode()
        )


def summarize(run, output):
    # The existing verifier checks original actor, physical, renderer and callback clocks.
    validated = analyze(run)
    capture = run / "capture"
    renderer = json.loads((capture / "paired/renderer/result.json").read_bytes())
    if (
        not renderer.get("quality_binding")
        or renderer["perception_publications"]
        or renderer["complete_visual_scene"]
    ):
        raise ValueError("declared quality observation case required")
    images = indexed(renderer["raw"], "frame")
    mappings = indexed(renderer["mapped"], "renderer_frame")
    ticks = indexed(renderer["ticks"], "renderer_frame")
    source = json.loads((capture / "paired/source.json").read_bytes())
    exports = indexed(source["exports"], "frame")
    frames = []
    for row in renderer["inference"]:
        ident = row["renderer_frame"]
        tick = ticks[ident]
        offered = exports[row["physical_frame"]]["offered_wall_ns"]
        if not (
            row["original_acquisition_ns"]
            <= offered
            <= tick["apply_begin_ns"]
            <= tick["tick_begin_ns"]
            <= row["callback_ns"]
            <= row["worker_offer_ns"]
            <= row["begin_ns"]
        ):
            raise ValueError("scene export, renderer or worker handoff clock")
        frames.append(
            dict(
                **row,
                export_ns=offered,
                apply_begin_ns=tick["apply_begin_ns"],
                tick_begin_ns=tick["tick_begin_ns"],
                physical_source_ns=mappings[ident]["physical_source_ns"],
                original_acquisition_end_ns=mappings[ident][
                    "original_acquisition_end_ns"
                ],
                rgb_sha256=images[ident]["rgb_sha256"],
                bgra_sha256=images[ident]["bgra_sha256"],
                first_native_read_ns=None,
                actual_accept_ns=None,
            )
        )
    with (capture / "native-perception.jsonl").open() as stream:
        states = (json.loads(line)["perception"] for line in stream)
        reads = join_reads(
            frames, states, validated["start_wall_ns"], validated["stop_wall_ns"]
        )
    outcomes = Counter(r["timing"] for r in reads)
    if outcomes != validated["timing_outcomes"]:
        raise ValueError("native outcome cross-check")
    pairs = {
        "acquisition_to_export": ("original_acquisition_ns", "export_ns"),
        "export_to_apply": ("export_ns", "apply_begin_ns"),
        "apply_to_tick": ("apply_begin_ns", "tick_begin_ns"),
        "tick_to_callback": ("tick_begin_ns", "callback_ns"),
        "callback_to_offer": ("callback_ns", "worker_offer_ns"),
        "offer_to_worker": ("worker_offer_ns", "begin_ns"),
        "acquisition_to_callback": ("original_acquisition_ns", "callback_ns"),
        "callback_to_worker": ("callback_ns", "begin_ns"),
        "worker_to_boxes": ("begin_ns", "end_ns"),
        "callback_to_boxes": ("callback_ns", "end_ns"),
        "acquisition_to_boxes": ("original_acquisition_ns", "end_ns"),
        "boxes_to_first_native_read": ("end_ns", "first_native_read_ns"),
        "acquisition_to_first_native_read": (
            "original_acquisition_ns",
            "first_native_read_ns",
        ),
    }
    stats = {}
    for label, (a, b) in pairs.items():
        samples = [f[b] - f[a] for f in frames if f[b] is not None]
        stats[label] = dict(
            **distribution(samples), below_100ms=sum(v < LIFETIME for v in samples)
        )
    if not frames:
        raise ValueError("no completed quality inferences")
    stages = {
        k: distribution(round(f["stages_ms"][k] * 1e6) for f in frames)
        for k in frames[0]["stages_ms"]
    }
    stages["bgra_decode"] = distribution(f["decode_ns"] for f in frames)
    result = dict(
        raw_images=len(images),
        mapped_images=len(mappings),
        pending_replaced=renderer["inference_pending_replaced"],
        completed_boxes=len(frames),
        callbacks_per_second=len(images) / renderer["endurance_seconds"],
        detector_box_coordinate_size=[640, 384],
        camera_size=[2560, 1536],
        statistics=stats,
        detector_stages=stages,
        native=validated,
        scope="Native reads are measured. The join assumes zero transport time. No result was published or admitted.",
        percentile_method="nearest rank",
    )
    output.mkdir(exist_ok=True, parents=True)
    save_rows(output / "frames.json.gz", frames)
    save_rows(output / "native-reads.json.gz", reads)
    with (output / "timing.json").open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    summarize(args.run, args.output)

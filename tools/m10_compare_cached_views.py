"""Pair each six-view result with a same-image replay using frame-local crop reuse."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from m10_screen_view_schedules import sites, prior
from quality_cached_views import CachedFrameViews
from quality_latency import score_run, tiles, unpack
from quality_shadow_v1 import ROOT, VIEW_REGISTRATION, detector, digest
from m10_quality_shadow_timing import save_rows


def read(path):
    return json.loads(path.read_bytes())


def compare(output):
    output.mkdir(parents=True, exist_ok=False)
    previous = VIEW_REGISTRATION.parent
    ref_path = previous / "frames.json.gz"
    if digest(ref_path) != read(previous / "comparison.json")["frames_sha256"]:
        raise ValueError("reference trace hash")
    with gzip.open(ref_path, "rt") as stream:
        reference = json.load(stream)
    indices = read(VIEW_REGISTRATION)["indices"]
    frames = []
    scores = {}
    with detector(indices, fitted=True) as (model, spec):
        original = model.views
        cached = CachedFrameViews(model, indices)
        for name, site in sites().items():
            rows = []
            source = read(site / "images.json")["frames"]
            if len(source) != 81:
                raise ValueError("site denominator")
            for image, ref in zip(source, reference[name], strict=True):
                bgra = unpack(site / "dataset", image["rgb_raw"], 2560, 1536)
                measurements = {}
                modes = [("original", original), ("cached", cached)]
                if len(frames) % 2:
                    modes.reverse()
                for mode, views in modes:
                    model.views = views
                    start = time.monotonic_ns()
                    rgb = model.decode(bgra)
                    boxes, stages = model.predict(rgb)
                    elapsed = time.monotonic_ns() - start
                    if boxes != ref["base"] or ref["new"]:
                        raise ValueError(
                            f"{name}: {mode} disagrees with registered boxes"
                        )
                    measurements[mode] = dict(
                        ns=elapsed, calls=views.count, stages_ms=stages
                    )
                key = hashlib.sha256(memoryview(rgb)).hexdigest()
                if key != image["rgb_sha256"] or key != ref["rgb"]:
                    raise ValueError("source RGB identity")
                rows.append(dict(rgb=key, base=boxes, new={}))
                frames.append(dict(site=name, rgb=key, **measurements))
            scores[name] = score_run(site, rows, tiles.cycle.OFF)[0]
            if not scores[name]["passed"]:
                raise ValueError(f"{name}: site gate failed")
            print(name, "passed", flush=True)
    evaluation = [f for f in frames if f["site"] not in prior.DEV]
    if len(evaluation) != 891 or len(frames) != 1215:
        raise ValueError("full evaluation required")
    timing = {}
    for mode in ("original", "cached"):
        ns = np.asarray([f[mode]["ns"] for f in evaluation])
        timing[mode] = dict(
            median_ms=float(np.median(ns) / 1e6),
            p95_ms=float(np.percentile(ns, 95) / 1e6),
            below_100ms=int((ns < 100_000_000).sum()),
            dfine_calls=sum(f[mode]["calls"] for f in evaluation),
        )
    trace = output / "frames.json.gz"
    save_rows(trace, frames)
    report = dict(
        input_frames=len(frames),
        evaluation_frames=len(evaluation),
        baseline=spec,
        implementation_sha256=digest(
            ROOT / "tests/integration/perception/quality_cached_views.py"
        ),
        previous_trace_sha256=digest(ref_path),
        trace_sha256=digest(trace),
        exact_boxes=True,
        site_quality=scores,
        evaluation=timing,
    )
    (output / "comparison.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n"
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("output", type=Path)
    compare(p.parse_args().output)

"""Reproduce the M10 same-frame Host quality and latency comparison on retained RGB data."""

import argparse
from contextlib import ExitStack
from pathlib import Path
import time

import m10_bus_support_quality as current
import m10_visible_car_quality as old
from quality_latency import Detector, replay, read, dump, bus, prior


def run(args):
    if current.nomination() != read(current.MARK):
        raise ValueError("quality reference changed")
    sites = {
        **prior.DEV,
        "holdout": current.BASE / "runs/evaluation-holdout-01",
        "previous60": old.RUN,
        **old.HISTORICAL,
    }
    names = args.sites or list(sites)
    if not set(names) <= set(sites) or len(set(names)) != len(names):
        raise ValueError("unknown or duplicate site")
    args.output.mkdir(parents=True, exist_ok=False)
    binding = dict(
        reference=current.sha(current.MARK),
        mode=args.mode,
        source={
            p.name: current.sha(p)
            for p in [
                Path(__file__).resolve(),
                *[
                    current.TESTS / n
                    for n in (
                        "quality_crop.cu",
                        "quality_features.py",
                        "quality_latency.py",
                        "quality_latency_cuda.py",
                        "quality_views.py",
                    )
                ],
            ]
        },
    )
    start = time.perf_counter()
    with ExitStack() as stack:
        detector = None
        if args.mode == "reference":
            detector = Detector()
        else:
            import tensorrt
            from quality_latency_cuda import CropInput, Engine

            if not args.library or not args.engine:
                raise ValueError(
                    "both the CUDA crop library and the Host engine are required"
                )
            binding.update(
                engine_sha256=current.sha(args.engine),
                library_sha256=current.sha(args.library),
                tensorrt=tensorrt.__version__,
            )
            crops = stack.enter_context(CropInput(args.library))
            engine = stack.enter_context(Engine(args.engine))
            detector = Detector(crops, args.mode, engine)
        binding["startup_ms"] = (time.perf_counter() - start) * 1000
        dump(args.output / "binding.json", binding)
        for name in names:
            run_dir = sites[name]
            reference = (
                bus.EVIDENCE / (name + "-detections.json.gz")
                if name not in prior.DEV
                else None
            )
            out = args.output / (name + ".json")
            replay(detector, run_dir, reference, out)
            d = read(out)
            print(
                name,
                d["quality"]["passed"],
                round(d["p50_ms"], 2),
                round(d["p95_ms"], 2),
                flush=True,
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--mode",
        choices=("reference", "lite", "focus", "guided", "native"),
        default="guided",
    )
    parser.add_argument("--library", type=Path)
    parser.add_argument("--engine", type=Path)
    parser.add_argument("--sites", nargs="+")
    run(parser.parse_args())

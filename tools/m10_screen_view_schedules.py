"""Compare fixed RGB-only view schedules on original frames. Shared outputs are untimed."""

import argparse
from pathlib import Path

from m10_quality_latency import current, old, prior, dump, read, replay
from quality_latency import score_run, tiles, unpack
from quality_shadow_v1 import binding, detector, digest, VIEW_REGISTRATION
from quality_view_schedule import ScheduledViews
import hashlib
import json

SCHEDULES = {
    "full": tuple(range(10)),
    "four": (0, 5, 7, 9),
    "five": (0, 3, 5, 7, 9),
    "sides": (0, 2, 4, 5, 7, 9),
    "interleaved": (0, 2, 4, 6, 8),
    "narrow": (0, 5, 6, 7, 8, 9),
    "six": (0, 3, 5, 6, 8, 9),
    "narrow_flip": (0, 1, 5, 6, 7, 8, 9),
    "pyramid": (0, 2, 3, 4, 5, 7, 9),
    "symmetric": (0, 1, 2, 3, 4, 5, 7, 9),
    "no_broad_center": (0, 2, 4, 5, 6, 7, 8, 9),
    "no_mirror": (0, 2, 3, 4, 5, 6, 7, 8, 9),
    "no_center": (0, 1, 2, 4, 5, 6, 7, 8, 9),
    "no_outer_broad": (0, 1, 3, 5, 6, 7, 8, 9),
}


def sites():
    return {
        **prior.DEV,
        "holdout": current.BASE / "runs/evaluation-holdout-01",
        "previous60": old.RUN,
        **old.HISTORICAL,
    }


class CachedViews(ScheduledViews):
    def forward(self, rect, flip=False):
        key = (tuple(rect), bool(flip))
        if key not in self.frame_cache:
            self.frame_cache[key] = super().forward(rect, flip)
        return self.frame_cache[key]


def screen(model, runs, output):
    import gzip

    archive = current.EVIDENCE.parent / "m10_quality_latency_v1/frames.json.gz"
    if digest(archive) != read(archive.with_name("comparison.json"))["trace_sha256"]:
        raise ValueError("reference trace identity")
    with gzip.open(archive, "rt") as stream:
        reference = json.load(stream)["selected"]
    views = {k: CachedViews(model, indices) for k, indices in SCHEDULES.items()}
    for name, run in runs.items():
        records = {k: [] for k in views}
        for f, ref in zip(
            read(run / "images.json")["frames"], reference[name], strict=True
        ):
            image = model.decode(unpack(run / "dataset", f["rgb_raw"], 2560, 1536))
            key = hashlib.sha256(image.tobytes()).hexdigest()
            if key != f["rgb_sha256"] or key != ref["rgb"]:
                raise ValueError("frame identity")
            cache = {}
            for k, view in views.items():
                view.frame_cache = cache
                model.views = view
                boxes, _ = model.predict(image)
                if k == "full" and boxes != ref["base"]:
                    raise ValueError("original ten-view result differs")
                records[k].append(dict(rgb=key, base=boxes, new={}))
        scores = {
            k: score_run(run, rows, tiles.cycle.OFF)[0] for k, rows in records.items()
        }
        dump(output / (name + ".json"), scores)
        print(name, [k for k, s in scores.items() if s["passed"]], flush=True)


def main(args):
    args.output.mkdir(parents=True, exist_ok=False)
    runs = sites()
    if args.development:
        runs = prior.DEV
    fitted = args.timed == "registered"
    indices = (
        read(VIEW_REGISTRATION)["indices"] if fitted else SCHEDULES.get(args.timed)
    )
    spec = binding(indices, fitted)
    impl = current.TESTS / "quality_view_schedule.py"
    dump(
        args.output / "binding.json",
        dict(
            parent=spec,
            schedules=SCHEDULES,
            schedule=args.timed,
            implementation=digest(impl),
            driver=digest(Path(__file__)),
        ),
    )
    with detector(indices, fitted) as (model, _):
        if not args.timed:
            screen(model, runs, args.output)
            return
        for name, run in runs.items():
            path = args.output / (name + ".json")
            replay(model, run, None, path)
            result = read(path)
            print(
                name,
                result["quality"]["passed"],
                round(result["raw_p95_ms"], 2),
                flush=True,
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timed", choices=[*SCHEDULES, "registered"])
    parser.add_argument("--development", action="store_true")
    main(parser.parse_args())

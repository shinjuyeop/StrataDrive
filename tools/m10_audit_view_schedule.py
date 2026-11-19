"""Verify two independent timed replays against original RGB identities and site gates."""

import argparse
import gzip
import json
from pathlib import Path

from m10_quality_latency_audit import latency
from m10_screen_view_schedules import current, prior, read, sites
from quality_latency import score_run, tiles
from quality_shadow_v1 import binding as verify_binding, digest


def audit(first, second, output):
    if first.resolve() == second.resolve():
        raise ValueError("distinct timed replays required")
    binding = read(first / "binding.json")
    if not binding["schedule"] or binding != read(second / "binding.json"):
        raise ValueError("candidate differs")
    spec = binding["parent"]
    if spec != verify_binding(spec.get("view_indices"), "view_verifier_sha256" in spec):
        raise ValueError("candidate files differ from measured binding")
    if binding["driver"] != digest(
        Path(__file__).with_name("m10_screen_view_schedules.py")
    ):
        raise ValueError("timed replay driver identity")
    previous = current.EVIDENCE.parent / "m10_quality_latency_v1/frames.json.gz"
    if digest(previous) != read(previous.with_name("comparison.json"))["trace_sha256"]:
        raise ValueError("baseline frame trace")
    with gzip.open(previous, "rt") as stream:
        baseline = json.load(stream)["selected"]
    groups = [[], []]
    site_reports = {}
    traces = {}
    for name, site in sites().items():
        a, b = [read(root / (name + ".json")) for root in (first, second)]
        aa, bb = a["rows"], b["rows"]
        if len(aa) != 81:
            raise ValueError(f"incomplete site {name}")
        unchanged = 0
        for i, (x, y, ref) in enumerate(zip(aa, bb, baseline[name], strict=True)):
            if (
                x["rgb"] != ref["rgb"]
                or x["rgb"] != y["rgb"]
                or (x["base"], x["new"]) != (y["base"], y["new"])
            ):
                raise ValueError(f"pair mismatch {name} {i}")
            unchanged += x["base"] == ref["base"] and x["new"] == ref["new"]
        q = score_run(site, aa, tiles.cycle.OFF)[0]
        if q != a["quality"] or q != b["quality"] or not q["passed"]:
            raise ValueError(f"site quality {name}")
        site_reports[name] = dict(
            development=name in prior.DEV,
            unchanged_detections=unchanged,
            quality=q,
            latency=[latency(rr) for rr in (aa, bb)],
        )
        traces[name] = [
            dict(
                rgb=x["rgb"],
                base=x["base"],
                new=x["new"],
                measurements=[
                    {
                        k: r[k]
                        for k in (
                            "elapsed_ms",
                            "raw_to_boxes_ms",
                            "stages_ms",
                            "dfine_crop_calls",
                        )
                    }
                    for r in (x, y)
                ],
            )
            for x, y in zip(aa, bb, strict=True)
        ]
        if name not in prior.DEV:
            groups[0].extend(aa)
            groups[1].extend(bb)
    if any(len(g) != 891 for g in groups):
        raise ValueError("incomplete evaluation")
    totals = {
        k: sum(
            s["quality"]["card"]["micro"][k]
            for s in site_reports.values()
            if not s["development"]
        )
        for k in ("tp", "fp", "fn")
    }
    output.mkdir(parents=True, exist_ok=False)
    trace = output / "frames.json.gz"
    trace.write_bytes(
        gzip.compress(
            json.dumps(traces, separators=(",", ":"), allow_nan=False).encode(), mtime=0
        )
    )
    report = dict(
        binding=binding,
        baseline_sha256=digest(previous),
        frames_sha256=digest(trace),
        sites=site_reports,
        quality=totals,
        evaluation=[latency(g) for g in groups],
    )
    (output / "comparison.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("first", "second", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    audit(args.first, args.second, args.output)

"""Cross-check two measured replays and characterize small mask matches."""

import argparse
from collections import Counter
import gzip
import json
from pathlib import Path

from person_zoom_validation import CACHE, dump, frames, measure, score


def compare(first, second, paired):
    name = "pairs-validation" if paired else "archive-validation"
    path = name + ".jsonl.gz"
    seen = over = 0
    coord = confidence = 0.0
    small = []
    with (
        gzip.open(first / path, "rt") as before,
        gzip.open(second / path, "rt") as after,
    ):
        for (_, gt, sha, meta), a, b in zip(
            frames(CACHE, "validation", paired), before, after, strict=True
        ):
            x, y = json.loads(a), json.loads(b)
            if not x["rgb"] == sha == y["rgb"] or x["bounds"] != y["bounds"]:
                raise ValueError("input or crop changed")
            seen += 1
            over += y["timing_ns"]["total"] >= 100_000_000
            objs = [o for o in gt["objects"] if o["class_id"] == 0]
            for mode in ("full", "zoom"):
                for d, e in zip(x[mode], y[mode], strict=True):
                    coord = max(
                        coord,
                        max(
                            abs(u - v) for u, v in zip(d["box"], e["box"], strict=True)
                        ),
                    )
                    confidence = max(confidence, abs(d["score"] - e["score"]))
                v = measure(y[mode], objs, gt["excluded"])
                if measure(x[mode], objs, gt["excluded"]) != v:
                    raise ValueError("frame matching changed")
                if paired and mode == "zoom":
                    for i in sorted(v[3]):
                        obj = gt["excluded"][i]
                        left, top, right, bottom = obj["box"]
                        small.append(
                            dict(
                                rgb=sha,
                                role=meta["role"],
                                tags=obj["semantic_tags"],
                                width=right - left,
                                height=bottom - top,
                                native_visible_pixels=obj["native_visible_pixels"],
                            )
                        )
    result = dict(
        frames_replayed=seen,
        maximum_score_difference=confidence,
        maximum_coordinate_difference=coord,
        identical_per_frame_matches=True,
        total_at_least_100ms=over,
    )
    if paired:
        result["small_person_matches"] = small
    return result


def training_size_check(parity):
    counts = Counter()
    flagged = 0
    with gzip.open(parity / "pairs-train.jsonl.gz", "rt") as trace:
        for line, (_, gt, sha, meta) in zip(
            trace, frames(CACHE, "train", True), strict=True
        ):
            row = json.loads(line)
            if sha != row["rgb"]:
                raise ValueError("training trace identity")
            keep = []
            for d in row["zoom"]:
                left, top, right, bottom = d["box"]
                if d not in row["full"] and (
                    min(right - left, bottom - top) < 4
                    or (right - left) * (bottom - top) < 25
                ):
                    flagged += 1
                else:
                    keep.append(d)
            counts.update(score(keep, gt, meta["role"])[0])
    return dict(flagged=flagged, counts_if_flagged_boxes_omitted=counts)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("first", "second", "parity", "output"):
        p.add_argument(name, type=Path)
    a = p.parse_args()
    dump(
        a.output,
        {
            "archive-validation": compare(a.first, a.second, False),
            "pairs-validation": compare(a.first, a.second, True),
            "training_only_size_diagnostic": training_size_check(a.parity),
        },
    )

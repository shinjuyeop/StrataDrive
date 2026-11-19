"""Fit the original proposal classifiers on the same training frames with fewer RGB views."""

import argparse
import gzip
import json
from pathlib import Path

from multiview_detector import fit, records
from person_pair_candidate import frames
from person_zoom_validation import CACHE
from quality_shadow_v1 import ROOT, digest


def train(out, indices):
    indices = tuple(indices)
    if (
        not indices
        or indices[0] != 0
        or sorted(set(indices)) != list(indices)
        or indices[-1] >= 10
    ):
        raise ValueError("unique ordered view indices beginning at zero required")
    source = ROOT / "build/m10-multiview-v1/train.jsonl.gz"
    out.mkdir(parents=True, exist_ok=False)
    training_labels = {
        key: gt["objects"]
        for paired in (True, False)
        for _, gt, key, _ in frames(CACHE, "train", paired)
    }
    seen = set()
    with gzip.open(out / "train.jsonl.gz", "wt") as stream:
        for row in records(source):
            if training_labels.get(row["rgb"]) != row["gt"]:
                raise ValueError("training label association")
            if row["rgb"] in seen:
                raise ValueError("duplicate training RGB")
            seen.add(row["rgb"])
            row["obs"] = [v for v in row["obs"] if v[0] in indices]
            stream.write(json.dumps(row, separators=(",", ":")) + "\n")
    # fit independently resolves the original training sources and verifies every RGB.
    fit(out)
    manifest = dict(
        indices=indices,
        original_frames=len(seen),
        source_sha256=digest(source),
        filtered_sha256=digest(out / "train.jsonl.gz"),
        verifier_sha256=digest(out / "verifier.joblib"),
    )
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("output", type=Path)
    p.add_argument("--views", nargs="+", type=int, required=True)
    a = p.parse_args()
    train(a.output, a.views)

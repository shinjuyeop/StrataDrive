#!/usr/bin/env python3
"""Replay frozen source/data identities and all development scores without models/GPU."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import RgbDataset, read_json
from physical_ai.perception.model_screen_v1 import CANDIDATES
from run_model_screen_v1 import ROOT, check_freeze, require, score, write_new


def audit(directory):
    frozen = directory / "freeze.json"
    f = check_freeze(frozen)
    numeric = read_json(directory / "numeric-02.json")
    require(
        sha256_file(directory / "numeric-02.json") == f["numeric_check_sha256"]
        and numeric["status"] == "PASS"
        and len(numeric["rows"]) == 15,
        "screen numeric provenance",
    )
    seen = set()
    for spec in f["datasets"].values():
        dataset = RgbDataset(ROOT / spec["path"] / "rgb.json")
        hashes = [row["rgb_sha256"] for row, _ in dataset.frames()]
        require(
            hashes == spec["rgb_sha256"]
            and len(set(hashes)) == 81
            and not seen.intersection(hashes),
            "screen raw RGB identity",
        )
        seen.update(hashes)
    checked = []
    for candidate in CANDIDATES:
        expected = read_json(directory / f"{candidate}-score.json")
        actual = score(frozen, directory / f"{candidate}-run.json")
        require(actual == expected, "screen score replay mismatch: " + candidate)
        checked.append(
            dict(
                candidate=candidate,
                score_sha256=sha256_file(directory / f"{candidate}-score.json"),
                run_sha256=sha256_file(directory / f"{candidate}-run.json"),
                micro=actual["micro"],
            )
        )
    return dict(
        status="PASS",
        schema="m10-pretrained-screen-audit-v1",
        frames=len(seen),
        sources=len(f["sources"]),
        candidates=checked,
        raw_rgb_rehash=True,
        scores_recomputed=True,
        gpu_or_model_inference=False,
        holdout_access=False,
        fresh_acceptance=False,
        runtime_promotion=False,
        freeze_sha256=sha256_file(frozen),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = audit(args.directory)
    write_new(args.output, report)
    print(report["status"], report["frames"], report["sources"])

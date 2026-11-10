#!/usr/bin/env python3
"""Fresh-source CPU replay of V8 raw/GT/score/order and preserved preparation failures."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile


def read(path):
    return json.loads(path.read_text())


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def extract(path, target):
    with tarfile.open(path) as archive:
        members = archive.getmembers()
        if len(members) != len({m.name for m in members}):
            raise ValueError("duplicate archive members")
        for member in members:
            name = PurePosixPath(member.name)
            if (
                name.is_absolute()
                or ".." in name.parts
                or not (member.isfile() or member.isdir())
            ):
                raise ValueError("unsafe archive member")
        archive.extractall(target)


def main(evidence, output):
    evidence = evidence.resolve()
    if output.exists():
        raise FileExistsError(output)
    for line in (evidence / "SHA256SUMS").read_text().splitlines():
        expected, name = line.split("  ", 1)
        path = (evidence / name).resolve()
        if not path.is_relative_to(evidence) or digest(path) != expected:
            raise ValueError("evidence checksum: " + name)
    with tempfile.TemporaryDirectory(prefix="m10-v8-recheck-") as directory:
        temporary = Path(directory)
        project = temporary / "project"
        project.mkdir()
        extract(evidence / "sources.tar.gz", project)
        for name, expected in read(evidence / "sources.json")["files"].items():
            if digest(project / name) != expected:
                raise ValueError("source snapshot: " + name)
        extract(evidence / "experiment.tar.gz", project)
        root = project / "build/m10-quality-v8"
        env = dict(
            os.environ,
            PYTHONPATH=str(project)
            + os.pathsep
            + str(project / "tests/integration/perception"),
        )

        def run(args):
            result = subprocess.run(
                [sys.executable] + list(map(str, args)),
                cwd=project,
                env=env,
                text=True,
                capture_output=True,
            )
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)

        saved_initial = read(root / "initial-preparation-audit.json")
        (root / "initial-preparation-audit.json").unlink()
        run([root / "audit-initial-preparation.py"])
        if read(root / "initial-preparation-audit.json") != saved_initial:
            raise ValueError("initial preparation failure replay")
        replay = temporary / "quality-audit.json"
        run(
            [project / "tests/integration/perception/audit_quality_v8.py", root, replay]
        )
        rebuilt = read(replay)
        if rebuilt != read(root / "experiment-audit.json") or rebuilt != read(
            evidence / "experiment-audit.json"
        ):
            raise ValueError("raw/GT/score/nomination/order replay")

        import numpy as np

        prior = set(
            read(project / "profiles/perception-quality-exclusion-v8.json")[
                "rgb_sha256"
            ]
        )
        future = set(prior)
        pairs = 0
        attempts = read(root / "capture-attempts.json")
        for row in attempts:
            if row["capture"] is None:
                if row["frames"] != 0:
                    raise ValueError("missing raw capture")
                continue
            path = root / row["capture"]
            if digest(path) != row["capture_sha256"]:
                raise ValueError("capture identity")
            hashes = []
            for frame in read(path)["frames"]:
                for stream in ("rgb", "instance"):
                    raw = path.parent / frame[stream]["path"]
                    if digest(raw) != frame[stream]["sha256"]:
                        raise ValueError("original raw pair hash")
                bgra = np.frombuffer(
                    (path.parent / frame["rgb"]["path"]).read_bytes(), np.uint8
                ).reshape(384, 640, 4)
                hashes.append(
                    hashlib.sha256(bgra[:, :, [2, 1, 0]].copy().tobytes()).hexdigest()
                )
            if hashes != row["rgb_sha256"] or len(hashes) != row["frames"]:
                raise ValueError("attempt RGB identity")
            future.update(hashes)
            pairs += len(hashes)
        if (
            sorted(future)
            != read(root / "future-evaluation-exclusion.json")["rgb_sha256"]
        ):
            raise ValueError("all-attempt exclusion union")
        if (
            sorted(future)
            != read(evidence / "future-evaluation-exclusion.json")["rgb_sha256"]
        ):
            raise ValueError("published exclusion union")
        report = dict(
            status="PASS",
            schema="m10-quality-v8-archive-recheck-v1",
            source_files=len(read(evidence / "sources.json")["files"]),
            frozen_sources=len(read(root / "experiment-freeze.json")["sources"]),
            total_raw_pairs_rehashed=pairs,
            prior_rgb_excluded=len(prior),
            future_rgb_excluded=len(future),
            original_preparation_failure_replayed=True,
            shutdown_failure_and_separate_recovery_preserved=True,
            accepted_raw_gt_score_nomination_order_replay="PASS",
            eligible_for_runtime_review=rebuilt["eligible_for_runtime_review"],
            runtime_promotion=False,
            model_or_gpu_inference=False,
            experiment_sha256=digest(evidence / "experiment.tar.gz"),
            sources_sha256=digest(evidence / "sources.tar.gz"),
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    print(
        "PASS",
        pairs,
        "raw pairs; quality eligibility",
        report["eligible_for_runtime_review"],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    main(args.evidence, args.output)

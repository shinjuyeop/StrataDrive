#!/usr/bin/env python3
"""Reconstruct content-addressed experiment inputs and execute fresh source audits."""

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
import tempfile


def read(p):
    return json.loads(p.read_text())


def digest(p):
    h = hashlib.sha256()
    with p.open("rb") as stream:
        for b in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def relative(name):
    p = PurePosixPath(name)
    if p.is_absolute() or ".." in p.parts:
        raise ValueError("unsafe path")
    return p


def extract(path, target, objects=False):
    with tarfile.open(path) as archive:
        names = set()
        for member in archive:
            p = relative(member.name)
            if member.name in names or not member.isfile():
                raise ValueError("duplicate/nonregular archive member")
            names.add(member.name)
            if objects and (
                len(p.parts) != 2
                or p.parts[0] != "objects"
                or not re.fullmatch("[0-9a-f]{64}", p.name)
            ):
                raise ValueError("invalid content address")
            out = target / member.name
            out.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as source, out.open("xb") as dest:
                import shutil

                shutil.copyfileobj(source, dest)
            if objects and digest(out) != p.name:
                raise ValueError("object SHA")


def main(evidence, output):
    evidence = evidence.resolve()
    if output.exists():
        raise FileExistsError(output)
    for line in (evidence / "SHA256SUMS").read_text().splitlines():
        expected, name = line.split("  ", 1)
        relative(name)
        if digest(evidence / name) != expected:
            raise ValueError("published evidence SHA: " + name)
    manifest = read(evidence / "paths.json")
    with tempfile.TemporaryDirectory(prefix="m10-resolution-recheck-") as directory:
        root = Path(directory)
        project = root / "project"
        project.mkdir()
        extract(evidence / "sources.tar.gz", project)
        for name in manifest["archives"]:
            extract(evidence / name, root, objects=True)
        for name, sha in manifest["files"].items():
            relative(name)
            target = project / name
            source = root / "objects" / sha
            if not source.is_file():
                raise ValueError("missing object")
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if digest(target) != sha:
                    raise ValueError("source/object collision")
            else:
                os.link(source, target)
        for name, sha in read(evidence / "sources.json")["files"].items():
            if digest(project / name) != sha:
                raise ValueError("source snapshot")
        env = dict(
            os.environ,
            PYTHONPATH=str(project)
            + os.pathsep
            + str(project / "tests/integration/perception"),
        )

        def run(script, *args):
            result = subprocess.run(
                [
                    sys.executable,
                    str(project / "tests/integration/perception" / script),
                    *map(str, args),
                ],
                cwd=project,
                env=env,
                text=True,
                capture_output=True,
            )
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)

        base = project / "build/m10-camera-resolution-v1"
        replay = root / "camera-audit.json"
        run("audit_camera_resolution_v1.py", base, replay)
        rebuilt = read(replay)
        if rebuilt != read(base / "audit.json") or rebuilt != read(
            evidence / "audit.json"
        ):
            raise ValueError("camera raw/GT/numeric/model-score/order replay")

        frozen = read(base / "freeze.json")
        if (
            digest(base / "prelaunch-source-freeze.json")
            != frozen["prelaunch_inventory_parent_sha256"]
        ):
            raise ValueError("prelaunch inventory parent changed")
        if datetime.fromisoformat(frozen["created_utc"]) >= min(
            datetime.fromisoformat(
                read(base / row["run"] / "server.json")["started_utc"]
            )
            for row in read(base / "capture-attempts.json")
        ):
            raise ValueError("freeze before first source RGB")
        attempts = read(base / "capture-attempts.json")
        from collections import Counter

        if any(
            n > 2 for n in Counter((r["phase"], r["scale"]) for r in attempts).values()
        ):
            raise ValueError("bounded attempt denominator")
        for recovery in base.glob("*-recovery-before-launch.json"):
            note = read(recovery)
            old = base / note["original_run"]
            previous = read(old / "server.json")
            replacement = base / f"{note['phase']}-{note['scale']}-02"
            if (
                digest(old / "server.json") != note["original_server_sha256"]
                or note["source_freeze_sha256"] != digest(base / "freeze.json")
                or note["budgets"] != [180, 900, 30]
                or not note["same_source_plan"]
            ):
                raise ValueError("bounded recovery identity")
            if (
                previous["status"] != "FAIL"
                or previous["server_exit"] != -9
                or not previous.get("forced_stop")
                or previous["capture_exit"] != 0
            ):
                raise ValueError("original shutdown failure erased")
            if (old / "dataset/rgb.json").exists():
                raise ValueError("failed attempt supplied accepted data")
            if (
                not datetime.fromisoformat(previous["started_utc"])
                < datetime.fromisoformat(note["created_utc"])
                < datetime.fromisoformat(
                    read(replacement / "server.json")["started_utc"]
                )
            ):
                raise ValueError("recovery before replacement")
        import numpy as np

        sys.path[:0] = [str(project), str(project / "tests/integration/perception")]
        from physical_ai.perception.camera_resolution_v1 import (
            canonical,
            decode,
            unpack,
        )
        from check_model_screen_v1 import compare_top300, compare_detections
        from dataclasses import asdict

        numeric_pairs = failed_pairs = 0
        for scale in [1, 2, 3, 4, 6]:
            for row in read(base / f"numeric-{scale}.json")["rows"]:
                values = []
                for item in row.get("raw_files", []):
                    path = base / item["file"]
                    if digest(path) != item["sha256"]:
                        raise ValueError("numeric raw SHA")
                    with np.load(path) as arrays:
                        values.append(dict(arrays))
                if len(values) != 3:
                    raise ValueError("missing numeric output denominator")
                passed = True
                try:
                    for a, b in zip(values, values[1:]):
                        compare_top300(canonical(a, scale), canonical(b, scale))
                        compare_detections(
                            [asdict(d) for d in decode(a, scale)],
                            [asdict(d) for d in decode(b, scale)],
                        )
                except (ValueError, AssertionError):
                    passed = False
                if passed != row["passed"]:
                    raise ValueError("numeric original outcome differs")
                numeric_pairs += 1
                failed_pairs += int(not passed)
        from quality_annotation import visible_boxes_v2

        control = base / read(base / "comparison-runs.json")["1"]
        cap = read(control / "dataset/capture.json")
        truth = read(control / "dataset/evaluation-only-gt.json")["frames"]
        for pair, gt in zip(cap["frames"], truth):
            expected = visible_boxes_v2(
                unpack(control / "dataset", pair["instance"], 640, 384)
            )
            observed = tuple(
                [
                    {k: v for k, v in o.items() if not k.startswith("native_")}
                    for o in gt[field]
                ]
                for field in ["objects", "excluded"]
            )
            if expected != observed:
                raise ValueError("640 annotation legacy policy changed")
        profile = read(project / "profiles/perception-camera-source-candidates-v1.json")
        if (
            profile["audit_sha256"] != digest(base / "audit.json")
            or profile["source"]["width"] != 3840
            or profile["source"]["height"] != 2304
            or profile["runtime_promotion"]
            or profile["live20Hz_acceptance"]
        ):
            raise ValueError("camera source profile scope/identity")
        report = dict(
            schema="m10-camera-source-archive-recheck-v1",
            status="PASS",
            source_files=len(read(evidence / "sources.json")["files"]),
            logical_paths=len(manifest["files"]),
            objects=manifest["objects"],
            native_raw_pairs=rebuilt["raw_pairs_rehashed"],
            model_raw_replays=rebuilt["model_raw_replays"],
            native_numeric_pairs=numeric_pairs,
            numeric_failures_preserved=failed_pairs,
            legacy640_annotation_replays=81,
            selected_source=[3840, 2304],
            failed_shutdown_and_bounded_recovery_preserved=True,
            future_rgb_exclusion=rebuilt["future_rgb_exclusion"],
            new_development_only=True,
            holdout_access=False,
            runtime_promotion=False,
            live20Hz_acceptance=False,
            model_or_gpu_inference=False,
            experiment_archives={
                name: digest(evidence / name) for name in manifest["archives"]
            },
            sources_sha256=digest(evidence / "sources.tar.gz"),
        )
    with output.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    print(
        "PASS: native camera raw/GT/numeric/model scores and original failures; no live acceptance"
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("evidence", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    main(a.evidence, a.output)

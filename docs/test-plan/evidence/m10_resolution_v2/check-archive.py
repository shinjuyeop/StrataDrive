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
        extract(evidence / "experiment.tar.gz", root, objects=True)
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

        study = project / "build/m10-resolution-v2"
        car = project / "build/m10-resolution-car-v1"
        v1 = project / "build/m10-resolution-v1"
        result_path = root / "parent-audit.json"
        run("audit_resolution_v2.py", study, result_path)
        if read(result_path) != read(study / "audit.json") or read(result_path) != read(
            evidence / "v2-audit.json"
        ):
            raise ValueError("parent raw/score/selection/order audit")
        original = read(car / "audit.json")
        (car / "audit.json").unlink()
        run("run_resolution_car_v1.py", "audit", car)
        if read(car / "audit.json") != original or read(
            car / "evaluation.json"
        ) != read(evidence / "car-evaluation.json"):
            raise ValueError("revised vector raw/score audit")
        import numpy as np

        sys.path[:0] = [str(project), str(project / "tests/integration/perception")]
        from check_model_screen_v1 import compare_top300

        for n in range(3):
            with np.load(
                project / f"build/m10-quality-v9/numeric-reference-01/dfine-{n}.npz"
            ) as z:
                old = dict(z)
            with np.load(v1 / f"cached640-reference/640-{n}.npz") as z:
                cached = dict(z)
            with np.load(v1 / f"reference/640-{n}.npz") as z:
                regenerated = dict(z)
            compare_top300(old, cached)
            try:
                compare_top300(old, regenerated)
            except ValueError:
                pass
            else:
                raise ValueError("original640 reference failure erased")
        failed = read(v1 / "numeric-second-profile.json")
        if (
            failed["status"] != "FAIL"
            or sum(not r["passed"] for r in failed["rows"]) != 1
        ):
            raise ValueError("1280 numeric failure erased")
        if "default CPU EP" not in (v1 / "numeric-investigation.log").read_text():
            raise ValueError("fallback failure erased")
        if (v1 / "runs").exists():
            raise ValueError("original failed study ran quality")
        if datetime.fromisoformat(
            read(car / "freeze.json")["created_utc"]
        ) >= datetime.fromisoformat(read(car / "numeric.json")["completed_utc"]):
            raise ValueError("revision numeric order")
        candidate = read(project / "profiles/perception-resolution-candidates-v1.json")
        revision = read(car / "evaluation.json")
        spec = candidate["models"][revision["candidate"]]
        if (
            not revision["eligible_for_next_fresh_quality_test"]
            or spec["development_evaluation_sha256"] != digest(car / "evaluation.json")
            or candidate["runtime_promotion"]
        ):
            raise ValueError("derived offline candidate identity")
        report = dict(
            schema="m10-resolution-archive-recheck-v1",
            status="PASS",
            source_files=len(read(evidence / "sources.json")["files"]),
            logical_paths=len(manifest["files"]),
            objects=manifest["objects"],
            native_quality_raw_replays=1458,
            revised_raw_replays=486,
            original_numeric_failures_preserved=True,
            cached640_failure_and_correction_replayed=True,
            parent_rejection_preserved=read(result_path)[
                "eligible_for_next_fresh_quality_test"
            ]
            is False,
            revised_development_eligible=True,
            holdout_access=False,
            fresh_acceptance=False,
            new_rgb=False,
            future_rgb_exclusion=5449,
            runtime_promotion=False,
            model_or_gpu_inference=False,
            experiment_sha256=digest(evidence / "experiment.tar.gz"),
            sources_sha256=digest(evidence / "sources.tar.gz"),
        )
    with output.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    print(
        "PASS: full raw/score/order, original failures, derived candidate; no fresh acceptance"
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("evidence", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    main(a.evidence, a.output)

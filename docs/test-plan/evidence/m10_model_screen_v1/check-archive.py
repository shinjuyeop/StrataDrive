#!/usr/bin/env python3
"""Verify checksums, safely extract, and replay RGB/source/score checks without inference."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main(evidence, output):
    if output.exists():
        raise FileExistsError(output)
    evidence = evidence.resolve()
    checked = 0
    for line in (evidence / "SHA256SUMS").read_text().splitlines():
        expected, name = line.split("  ", 1)
        path = (evidence / name).resolve()
        if not path.is_relative_to(evidence) or digest(path) != expected:
            raise ValueError("evidence checksum mismatch: " + name)
        checked += 1
    archive = evidence / "experiment.tar.gz"
    with tempfile.TemporaryDirectory(prefix="m10-model-screen-recheck-") as tmp:
        temporary = Path(tmp)
        with tarfile.open(archive) as tar:
            for member in tar.getmembers():
                path = PurePosixPath(member.name)
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or not (member.isfile() or member.isdir())
                ):
                    raise ValueError("unsafe archive member")
            tar.extractall(temporary)
        project = temporary / "project"
        replay = project / "build/m10-model-screen-v1"
        result = temporary / "replay.json"
        env = dict(
            os.environ,
            PYTHONPATH=str(project)
            + os.pathsep
            + str(project / "tests/integration/perception"),
        )
        process = subprocess.run(
            [
                sys.executable,
                str(project / "tests/integration/perception/audit_model_screen_v1.py"),
                str(replay),
                str(result),
            ],
            cwd=project,
            env=env,
            text=True,
            capture_output=True,
        )
        if process.returncode:
            raise RuntimeError(process.stdout + process.stderr)
        audit = json.loads(result.read_text())
        source_manifest = json.loads((evidence / "sources.json").read_text())
        for name, expected in source_manifest["files"].items():
            if digest(project / name) != expected:
                raise ValueError("related source snapshot mismatch: " + name)
    report = dict(
        status="PASS",
        archive_sha256=digest(archive),
        archive_bytes=archive.stat().st_size,
        evidence_files_checked=checked,
        final_related_sources=len(source_manifest["files"]),
        replay=audit,
        model_or_gpu_inference=False,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    print(
        "PASS",
        report["archive_bytes"],
        "bytes;",
        audit["frames"],
        "RGB frames replayed",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    main(args.evidence, args.output)

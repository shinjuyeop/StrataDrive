#!/usr/bin/env python3
"""Safely extract frozen sources and replay raw/score/RGB integrity in a fresh process."""

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
    with tempfile.TemporaryDirectory(prefix="m10-screen-v2-replay-") as directory:
        temporary = Path(directory)
        archives = json.loads((evidence / "archives.json").read_text())
        expected = {
            "experiment.tar.gz",
            "raw-yolox-s.tar.gz",
            "raw-yolox-l.tar.gz",
            "raw-damo-s.tar.gz",
            "raw-detr.tar.gz",
        }
        if {record["file"] for record in archives} != expected or len(archives) != 5:
            raise ValueError("archive inventory")
        seen = set()
        for record in archives:
            source = evidence / record["file"]
            if (
                source.stat().st_size != record["bytes"]
                or digest(source) != record["sha256"]
            ):
                raise ValueError("archive identity")
            with tarfile.open(source) as archive:
                for member in archive.getmembers():
                    path = PurePosixPath(member.name)
                    if (
                        path.is_absolute()
                        or ".." in path.parts
                        or not member.isfile()
                        or member.name in seen
                    ):
                        raise ValueError("unsafe or duplicate archive member")
                    seen.add(member.name)
                archive.extractall(temporary)
        project = temporary / "project"
        manifest = json.loads((project / "archive-files.json").read_text())
        for relative, expected in manifest.items():
            path = (project / relative).resolve()
            if not path.is_relative_to(project) or digest(path) != expected:
                raise ValueError("archive member checksum mismatch: " + relative)
        replay = project / "build/m10-model-screen-v2"
        env = dict(
            os.environ,
            PYTHONPATH=str(project)
            + os.pathsep
            + str(project / "tests/integration/perception"),
        )
        audit_path = temporary / "audit.json"
        command = [
            sys.executable,
            str(project / "tests/integration/perception/audit_model_screen_v2.py"),
        ]
        for key, value in dict(
            freeze=replay / "freeze.json",
            numeric=replay / "numeric-rgb.json",
            runs=replay / "runs",
            selection=replay / "selection.json",
            check=replay / "check.json",
            output=audit_path,
        ).items():
            command.extend(["--" + key, str(value)])
        process = subprocess.run(
            command, cwd=project, env=env, text=True, capture_output=True
        )
        if process.returncode:
            raise RuntimeError(process.stdout + process.stderr)
        audit = json.loads(audit_path.read_text())
        if audit["status"] != "PASS" or Path(audit["source_root"]) != project:
            raise ValueError("fresh-source replay failed")
        rgb_script = """
import json
from pathlib import Path
from physical_ai.perception.dataset import RgbDataset
root = Path.cwd()
freeze = json.loads((root/'build/m10-model-screen-v2/freeze.json').read_text())
seen = set()
for paths in freeze['datasets'].values():
    for spec in paths.values():
        actual = [s['rgb_sha256'] for s, _ in RgbDataset(root/spec['path']/'rgb.json').frames()]
        assert actual == spec['rgb_sha256'] and not seen.intersection(actual)
        seen.update(actual)
assert len(seen) == 405
print(len(seen))
"""
        rgb = subprocess.run(
            [sys.executable, "-c", rgb_script],
            cwd=project,
            env=env,
            text=True,
            capture_output=True,
        )
        if rgb.returncode or rgb.stdout.strip() != "405":
            raise RuntimeError(rgb.stdout + rgb.stderr)
        result = dict(
            status="PASS",
            archive_sha256=digest(evidence / "experiment.tar.gz"),
            archive_bytes=(evidence / "experiment.tar.gz").stat().st_size,
            archives=archives,
            checksums_checked=checked,
            archive_members_checked=len(manifest),
            fresh_source_subprocess=True,
            unique_development_rgb=405,
            audit=audit,
            holdout_access=False,
            fresh_acceptance=False,
            runtime_promotion=False,
        )
    output.write_text(json.dumps(result, indent=2) + "\n")
    print("PASS", result["archive_members_checked"], result["unique_development_rgb"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    main(args.evidence, args.output)

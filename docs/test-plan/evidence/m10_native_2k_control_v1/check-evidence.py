#!/usr/bin/env python3
"""Rebuild this Host boundary from its own archived sources, without CARLA/model."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import xml.etree.ElementTree as ET


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, required=True)
    args = parser.parse_args()
    bundle = Path(__file__).resolve().parent
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=False)
    source, build = work / "source", work / "build"
    source.mkdir()
    manifest = json.loads((bundle / "sources.json").read_text())
    archive = bundle / "sources.tar.gz"
    assert sha(archive) == manifest["archive_sha256"]
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        assert {m.name for m in members} == set(manifest["files"])
        assert len(members) == len(manifest["files"])
        for m in members:
            assert m.isfile() and not Path(m.name).is_absolute() and ".." not in Path(m.name).parts
            data = tar.extractfile(m).read()
            expected = manifest["files"][m.name]
            assert len(data) == expected["bytes"] and hashlib.sha256(data).hexdigest() == expected["sha256"]
            destination = source / m.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
    env = dict(os.environ, PYTHONPATH=str(source) + ":" + str(source / "tests/integration/perception"), OMP_WAIT_POLICY="PASSIVE")
    commands = []

    def run(name, command):
        commands.append(command)
        with (work / (name + ".log")).open("w") as log:
            process = subprocess.run(command, cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=300)
        if process.returncode:
            raise RuntimeError(f"{name} failed ({process.returncode}); see {work / (name + '.log')}")

    run("configure", ["cmake", "-S", str(source), "-B", str(build), "-DCMAKE_BUILD_TYPE=Release",
                      "-DSTRATADRIVE_PERCEPTION_TESTS=ON", "-DPython3_EXECUTABLE=" + str(Path(sys.executable).absolute())])
    targets = {"perception_2k_receiver_test": 15, "perception_2k_control_sil_test": 9,
               "perception_receiver_test": 11, "speed_supervisor_test": 22, "vehicle_coordinator_test": 31}
    run("build", ["cmake", "--build", str(build), "--target", *targets, "perception_2k_replay", "perception_replay", "-j4"])
    env["STRATADRIVE_2K_CONTROL_EVIDENCE"] = str(work / "sil")
    counts = {}
    for name, expected in targets.items():
        xml = work / (name + ".xml")
        run(name, [str(build / name), "--gtest_output=xml:" + str(xml)])
        result = ET.parse(xml).getroot()
        assert int(result.attrib["tests"]) == expected
        assert all(int(result.attrib[k]) == 0 for k in ("failures", "disabled", "errors"))
        counts[name] = expected
    run("python", [sys.executable, "-m", "unittest", "test_boundary_2k_v1", "-v"])
    run("legacy-boundary", [sys.executable, str(source / "tests/integration/perception/check_boundary.py"),
                            str(build / "tests/integration/perception/perception_replay")])
    reports = [source / f"docs/test-plan/evidence/m10_latency_2k_v1/{name}/capture/result.json"
               for name in ("baseline-01", "tensor-01", "balanced-01")]
    run("retained-replay", [sys.executable, str(source / "tests/integration/perception/check_boundary_2k_v1.py"),
                            str(build / "tests/integration/perception/perception_2k_replay"),
                            "--reports", *map(str, reports), "--output", str(work / "replay")])
    for path in sorted((bundle / "sil").iterdir()):
        assert path.read_bytes() == (work / "sil" / path.name).read_bytes(), path
    for name in ("baseline-01", "tensor-01", "balanced-01"):
        for file in ("input.txt", "output.json"):
            assert (bundle / "replay" / name / file).read_bytes() == (work / "replay" / name / file).read_bytes()
    output = dict(status="PASS", scope="archived Host functional reproduction; no new live camera/model",
                  source_files=len(manifest["files"]), source_archive_sha256=manifest["archive_sha256"],
                  cpp_tests=counts, new_python_tests=7, sil_and_replay_artifacts_exact=True, commands=commands)
    (work / "validation.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({k: v for k, v in output.items() if k != "commands"}, indent=2))


if __name__ == "__main__":
    main()

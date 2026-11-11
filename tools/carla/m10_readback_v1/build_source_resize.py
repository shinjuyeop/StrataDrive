#!/usr/bin/env python3
"""Build the versioned2K resize kernel with unchanged Pillow arithmetic."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    a = parser.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    source = (
        Path(__file__).resolve().parents[3]
        / "physical_ai/perception/native_resize_2k_v1.cpp"
    )
    library = a.output / "libstrata_resize_2k_v1.so"
    command = [
        "g++",
        "-std=c++17",
        "-O3",
        "-fPIC",
        "-shared",
        "-fopenmp",
        "-ffp-contract=off",
        "-Wall",
        "-Wextra",
        "-Werror",
        str(source),
        "-o",
        str(library),
    ]
    subprocess.run(command, check=True)
    report = dict(
        schema="m10-source-resize-build-v1",
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        binary_sha256=hashlib.sha256(library.read_bytes()).hexdigest(),
        command=command,
        compiler=subprocess.check_output(["g++", "--version"], text=True),
    )
    (a.output / "build.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()

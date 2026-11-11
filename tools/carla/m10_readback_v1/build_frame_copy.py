#!/usr/bin/env python3
"""Build the portable CPython snapshot helper with the selected interpreter ABI."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import sysconfig


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    source = (
        Path(__file__).resolve().parents[3] / "physical_ai/perception/frame_copy_v1.c"
    )
    library = a.output / ("_frame_copy_v1" + sysconfig.get_config_var("EXT_SUFFIX"))
    command = [
        "gcc",
        "-std=c11",
        "-O3",
        "-fPIC",
        "-shared",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-I" + sysconfig.get_paths()["include"],
        str(source),
        "-o",
        str(library),
    ]
    subprocess.run(command, check=True)
    info = dict(
        schema="m10-frame-copy-build-v1",
        python=sys.version,
        command=command,
        compiler=subprocess.check_output(["gcc", "--version"], text=True),
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        binary_sha256=hashlib.sha256(library.read_bytes()).hexdigest(),
        binary_bytes=library.stat().st_size,
    )
    (a.output / "build.json").write_text(json.dumps(info, indent=2) + "\n")
    print(json.dumps(info))


if __name__ == "__main__":
    main()

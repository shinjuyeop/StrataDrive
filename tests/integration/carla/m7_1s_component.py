#!/usr/bin/env python3
"""Build/run real pinned CARLA network sources; never start UE or install files."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/carla/m7_nodrive"))
from install import PIN, replace
from shutdown_patch import apply


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--carla", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--patched", action="store_true")
    p.add_argument("--sanitizer", choices=("none", "address", "thread"), default="none")
    p.add_argument("--repeats", type=int, default=1000)
    p.add_argument("--disable-aslr", action="store_true", help="Child-only setarch -R for sanitizer address-space compatibility")
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    assert subprocess.check_output(["git", "-C", str(a.carla), "rev-parse", "HEAD"], text=True).strip() == PIN
    def base(path):
        return subprocess.check_output(["git", "-C", str(a.carla), "show", f"{PIN}:{path}"], text=True)
    files = ["listener.cpp", "listener.h", "router.cpp", "router.h", "primary.cpp", "primary.h", "primaryCommands.cpp", "primaryCommands.h"]
    sources = {"LibCarla/source/carla/multigpu/"+name: base("LibCarla/source/carla/multigpu/"+name).encode() for name in files}
    if a.patched:
        sources.update(apply(base, replace))
    for path, data in sources.items():
        dest = a.output/path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    harness = a.output/"m7_1s_shutdown.cpp"
    harness.write_bytes(Path(__file__).with_suffix(".cpp").with_name("m7_1s_shutdown.cpp").read_bytes())
    boost = a.carla/"Build/boost-1.84.0-c10-install/include"
    argv = ["clang++-14", "-std=c++14", "-pthread", "-O1", "-g", "-fno-omit-frame-pointer", "-fno-pie", "-no-pie", "-DBOOST_ERROR_CODE_HEADER_ONLY",
            "-I"+str(a.output/"LibCarla/source"), "-I"+str(a.carla/"LibCarla/source"),
            "-isystem", str(a.carla/"LibCarla/source/third-party"),
            "-isystem", str(a.carla/"Build/rpclib-v2.2.1_c5-c10-libcxx-install/include"), "-isystem", str(boost),
            str(harness), *(str(a.output/path) for path in sources if path.endswith(".cpp")),
            str(a.carla/"LibCarla/source/carla/Buffer.cpp"), "-o", str(a.output/"probe")]
    if a.sanitizer != "none":
        argv += ["-fsanitize="+("address,undefined" if a.sanitizer == "address" else "thread")]
    report = {"patched": a.patched, "sanitizer": a.sanitizer, "disable_aslr": a.disable_aslr, "pin": PIN, "build_argv": argv,
              "source_sha256": {path: hashlib.sha256(data).hexdigest() for path, data in sources.items()},
              "harness_sha256": hashlib.sha256(harness.read_bytes()).hexdigest(), "cases": []}
    with (a.output/"build.log").open("w") as log:
        proc = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT)
    report["build_exit"] = proc.returncode
    if proc.returncode == 0:
        report["binary_sha256"] = hashlib.sha256((a.output/"probe").read_bytes()).hexdigest()
        env = dict(os.environ, ASAN_OPTIONS="detect_leaks=1:abort_on_error=1", UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1", TSAN_OPTIONS="halt_on_error=1")
        for case, count in [("cancel", 1), ("empty", 1), ("double", 1), ("stress", a.repeats), ("connected", min(100, a.repeats)), ("lifetime", 10)]:
            cmd = [str(a.output/"probe"), case, str(count)]
            if a.disable_aslr:
                cmd = ["setarch", "x86_64", "-R"] + cmd
            with (a.output/(case+".log")).open("w") as log:
                try:
                    result = subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=120)
                    code = result.returncode
                except subprocess.TimeoutExpired:
                    code = "TIMEOUT"
            report["cases"].append({"case": case, "iterations": count, "argv": cmd, "exit": code})
    (a.output/"result.json").write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps({key: report[key] for key in ("patched", "sanitizer", "build_exit", "cases")}))
    return 0 if report["build_exit"] == 0 and all(c["exit"] == 0 for c in report["cases"]) else 1


if __name__ == "__main__":
    sys.exit(main())

"""Run one bounded 30s instrumented Host case with the registered renderer-only detector."""

import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from m10_asset_cache import install, restore, load
from m10_start_owner_gc_unattended import HELPER, helper_check

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests/integration/perception"
BASE = ROOT / "docs/test-plan/evidence/m10_cuda_resize_v1"
PYTHON = ROOT / "build/m10-perception/cuda-venv/bin/python"
sys.path[:0] = [str(TESTS), str(BASE)]
from runtime_restore import restore as restore_runtime  # noqa: E402
from run_carla_control_shadow_v1 import sha  # noqa: E402
from quality_shadow_v1 import REFERENCE, LIBRARY, ENGINE, binding  # noqa: E402
from profile_host_v1 import host  # noqa: E402


def save(p, obj):
    with p.open("x") as f:
        json.dump(obj, f, indent=2, allow_nan=False)
        f.write("\n")


def run_log(args, path, **kwargs):
    with path.open("x") as stream:
        subprocess.run(
            list(map(str, args)),
            stdout=stream,
            stderr=subprocess.STDOUT,
            check=True,
            **kwargs,
        )


@contextmanager
def lease(work):
    # A dedicated unprivileged lifetime owner lets the fixed helper restore on
    # normal return or a launcher crash, independently of the UE processes.
    owner = subprocess.Popen(["cat"], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL)
    try:
        with (work / "power.jsonl").open("x") as log:
            helper = subprocess.Popen(
                [
                    "sudo",
                    "-n",
                    "-k",
                    str(HELPER),
                    "--owner-pid",
                    str(owner.pid),
                    "--seconds",
                    "1800",
                ],
                stdout=log,
            )
            try:
                for _ in range(100):
                    if helper.poll() is not None:
                        raise RuntimeError("host lease exited before trial")
                    events = (work / "power.jsonl").read_text().splitlines()
                    if any('"APPLIED"' in line for line in events) and cap() == "70":
                        break
                    time.sleep(0.1)
                else:
                    raise TimeoutError("host lease activation")
                yield
            finally:
                owner.stdin.close()
                owner.wait(timeout=5)
                if helper.wait(timeout=10) or cap() != "100":
                    raise RuntimeError("host power restoration")
    finally:
        if not owner.stdin.closed:
            owner.stdin.close()
        owner.wait(timeout=5)


def cap():
    return Path("/sys/devices/system/cpu/intel_pstate/max_perf_pct").read_text().strip()


def freeze(work):
    spec = binding()
    original = json.loads((BASE / "sources.json").read_text())
    names = set(original["files"])
    for folder in (TESTS, ROOT / "physical_ai/perception", ROOT / "tools"):
        names.update(str(p.relative_to(ROOT)) for p in folder.glob("*.py"))
    names.add(str(REFERENCE.relative_to(ROOT)))
    files = {
        n: dict(bytes=(ROOT / n).stat().st_size, sha256=sha(ROOT / n))
        for n in sorted(names)
    }
    external = dict(original["external"])
    for asset in (
        "m10-multiview-v1/verifier.joblib",
        "m10-vehicle-class-v1/arbiter.joblib",
        "m10-vehicle-conflict-v1/appearance.joblib",
        "m10-bus-support-v1/appearance.joblib",
        "m10-perception/yolox.onnx",
        "m10-parking-verifier-v1/export-bus-truck/parking-dfine-960.onnx",
        "m10-parking-verifier-v1/export-bus-truck/manifest.json",
    ):
        path = ROOT / "build" / asset
        external[str(path)] = sha(path)
    external[str(ENGINE)] = spec["engine_sha256"]
    external[str(LIBRARY)] = spec["library_sha256"]
    save(
        work / "freeze.json",
        dict(
            files=files,
            external=external,
            previous=sha(BASE / "sources.json"),
            candidate=spec,
        ),
    )


def launch(work):
    work.mkdir(parents=True, exist_ok=False)
    spool = Path("/tmp") / ("stratadrive-" + work.name)
    if spool.exists():
        raise FileExistsError(spool)
    cache_declaration = json.loads((BASE / "cache-manifest.json").read_text())
    cache = Path(cache_declaration["cache"])
    if load(cache)["entries"] != cache_declaration["entries"]:
        raise ValueError("asset cache declaration")
    helper_check(ROOT / "tools/m10_boost_lease.py")
    metadata = work / "preparation-config" / work.name
    metadata.mkdir(parents=True)
    shutil.copyfile(BASE / "pre-install.json", work / "pre-install.json")
    for name in ("pre-install.json", "preparation-argv.json", "runtime_restore.py"):
        shutil.copyfile(BASE / name, metadata / name)
    freeze(work)
    argv = json.loads((BASE / "normal-30s-01/case.json").read_text())["argv"]
    argv[argv.index("--freeze") + 1] = str(work / "freeze.json")
    argv[argv.index("--output") + 1] = str(spool)
    argv += ["--quality-shadow"]
    env = dict(
        os.environ,
        PYTHONPATH=os.pathsep.join(map(str, (TESTS, ROOT / "tools", ROOT))),
        OPENBLAS_NUM_THREADS="1",
        OMP_NUM_THREADS="1",
        PYTHONDONTWRITEBYTECODE="1",
    )
    save(
        work / "case.json",
        dict(argv=argv, freeze_sha256=sha(work / "freeze.json"), spool=str(spool)),
    )
    with (ROOT / "build/m10-cuda-resize-v1/launcher.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        install_result = install(cache)
        try:
            save(work / "cache-install.json", install_result)
            run_log(
                [
                    PYTHON,
                    ROOT / "tools/m10_prepare_empty_pair.py",
                    "--series",
                    metadata,
                ],
                work / "prepare.log",
                env=env,
            )
            with lease(work):
                try:
                    engine = argv[argv.index("--engine") + 1]
                    source = argv[argv.index("--source") + 1]
                    run_log(
                        [
                            PYTHON,
                            ROOT / "tools/carla/m7_nodrive/build_endurance.py",
                            "--engine",
                            engine,
                            "--source",
                            source,
                            "--output",
                            ROOT / "build/m10-gc-feedback-v1/visual-tags-build-01",
                            "--install",
                        ],
                        work / "module.log",
                    )
                    run_log(
                        [
                            PYTHON,
                            ROOT / "tools/carla/m7_nodrive/build_dxc_lifetime.py",
                            "--engine",
                            engine,
                            "--output",
                            ROOT / "build/m10-dxc-lifetime-v1",
                            "--install",
                        ],
                        work / "dxc.log",
                    )
                    deadline = time.monotonic() + 180
                    while True:
                        temperature = max(
                            v / 1000 for k, v in host().items() if "/temp" in k
                        )
                        if temperature <= 70 or time.monotonic() >= deadline:
                            break
                        time.sleep(1)
                    if cap() != "70" or temperature > 70:
                        raise ValueError(
                            f"live host preflight cap={cap()} temperature={temperature}"
                        )
                    save(
                        work / "preflight.json", dict(max_cpu_c=temperature, cap=cap())
                    )
                    run_log(argv, work / "live.log", env=env)
                    if cap() != "70":
                        raise RuntimeError("lease ended during trial")
                finally:
                    restore_runtime(ROOT, work, work, work / "runtime-restoration.json")
        finally:
            result = restore(cache)
            save(work / "asset-restoration.json", result)
            # The engine writes its derived cache. Retain those bytes separately
            # and repopulate only the staged copy from the verified original.
            changed = set(result["modified_cache_files"])
            for e in cache_declaration["entries"]:
                if e["target"] not in changed:
                    continue
                src, dst = Path(e["path"]), Path(e["target"])
                if src.suffix not in (".ddc", ".udd") or sha(src) != e["sha256"]:
                    raise ValueError("unexpected modified cache entry")
                shutil.copyfile(dst, work / ("after-" + dst.name))
                shutil.copyfile(src, dst)
                if sha(dst) != e["sha256"]:
                    raise ValueError("staged cache reset")
            save(
                work / "readback.json",
                dict(
                    cap=cap(),
                    restored=result["restored"],
                    staged_mutable_reset=len(changed),
                ),
            )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("name", help="new attempt name under build/")
    name = p.parse_args().name
    if not name.startswith("m10-quality-shadow-") or Path(name).name != name:
        p.error("use a new m10-quality-shadow-* name")
    launch(ROOT / "build" / name)

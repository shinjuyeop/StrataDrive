"""Finite source/environment identity without recording user environment variables."""

import os
from pathlib import Path
import platform
from .contract import (
    PROFILE_PATH,
    CUDA_PROFILE_PATH,
    CARLA_RGB_PROFILE_PATH,
    sha256_file,
)
from .preparation import STARTUP_PROFILE_PATH


def runtime_identity():
    package = Path(__file__).resolve().parent
    root = package.parents[1]
    files = sorted(package.glob("*.py")) + [
        PROFILE_PATH,
        CUDA_PROFILE_PATH,
        STARTUP_PROFILE_PATH,
        CARLA_RGB_PROFILE_PATH,
    ]
    cpu = platform.processor()
    if Path("/proc/cpuinfo").exists():
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    return {
        "source_files_sha256": {
            str(path.relative_to(root)): sha256_file(path) for path in files
        },
        "cpu": cpu,
        "logical_cpus": os.cpu_count(),
        "cpu_affinity": sorted(os.sched_getaffinity(0))
        if hasattr(os, "sched_getaffinity")
        else None,
        "scheduler_policy": os.sched_getscheduler(0)
        if hasattr(os, "sched_getscheduler")
        else None,
        "scheduler_priority": os.sched_getparam(0).sched_priority
        if hasattr(os, "sched_getparam")
        else None,
        "placement": "inherited; no isolated CPU or realtime guarantee",
    }

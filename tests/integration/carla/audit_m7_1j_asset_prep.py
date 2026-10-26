#!/usr/bin/env python3
"""Audit saved UE DDC preparation, including exit-zero/no-map failure.

The pinned commandlet processes packages already loaded as dependencies without
another Loading line. Verify the complete target enumeration and final blocking
drain, rather than requiring ten redundant explicit LoadPackage calls.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("log", type=Path)
    args = parser.parse_args()
    r = json.loads(args.manifest.read_text())
    log = args.log.read_text(errors="replace")
    map_arg = next(x for x in r["argv"] if x.startswith("-Map="))
    targets = map_arg[5:].split("+")
    enumerated = [int(n) for n in re.findall(r"LogDerivedDataCacheCommandlet: Display: (\d+) packages to load", log)]
    loads = re.findall(r"LogDerivedDataCacheCommandlet: Display: Loading \(\d+\) (.+)", log)
    last_load = log.rfind("LogDerivedDataCacheCommandlet: Display: Loading (")
    final_drain = log.rfind("Done waiting for shaders to finish.")
    checks = {
        "process_exit_zero": r.get("tool_exit") == 0,
        "ten_unique_targets": len(targets) == len(set(targets)) == 10,
        "ten_packages_enumerated": bool(enumerated) and set(enumerated) == {10},
        "target_packages_loaded": bool(loads) and all(Path(s).stem in {Path(x).name for x in targets} for s in loads),
        "blocking_drain_after_loading": last_load >= 0 and final_drain > last_load,
        "commandlet_completed": "finished execution (result 0)" in log,
        "zero_error_summary": bool(re.search(r"Success - 0 error\(s\)", log)),
    }
    before = r.get("maps_before", [])
    checks["map_bytes_unchanged"] = len(before) == 10 and all(
        Path(x["path"]).is_file()
        and hashlib.sha256(Path(x["path"]).read_bytes()).hexdigest() == x["sha256"] for x in before)
    report = dict(status="PASS" if all(checks.values()) else "FAIL", checks=checks,
                  enumerated_counts=enumerated, explicitly_loaded_packages=sorted(set(loads)),
                  scope="pinned commandlet target enumeration/completion only; runtime readiness and renderer stability separate")
    print(json.dumps(report, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run/reuse M4 component regression and export small, commit-bound evidence."""
import argparse
import csv
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIRS = ("cmake", "central", "zone", "vecu", "interfaces", "simulation", "tests", "tools")
PROFILES = {"normal": "build/m4-readiness", "sanitized": "build/m1-angle-sanitized"}
SCENARIOS = {
    "logical-normal": "M4AsyncRuntime.NormalUsesRealBmsAndFeedbackBeforeActuation",
    "logical-normal-stop": "M4AsyncRuntime.NormalStopWaitsForLeafHandoffThenActualHvOff",
    "logical-partial-front": "M4AsyncRuntime.PartialFrontWritePreventsRearBatchAndProtectsAllDomains",
    "logical-feedback-loss": "M4AsyncRuntime.FeedbackLossCannotBeHiddenByLiveZoneHeartbeat",
    "logical-rejoin": "M4AsyncRuntime.ExplicitNewEpochRejoinKeepsPhysicalStateAndRestoresReadiness",
    "wall-normal": "M4AsyncWall.IndependentOwnersRunActualNormalPath",
    "wall-feedback-loss": "M4AsyncWall.IndependentFeedbackLossHasMeasuredProtectionResponse",
}


def fingerprint():
    files = subprocess.check_output(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT, text=True).splitlines()
    digest = hashlib.sha256()
    for name in sorted(set(files)):
        p = Path(name)
        if name == "CMakeLists.txt" or p.parts[0] in SOURCE_DIRS:
            digest.update(name.encode()); digest.update((ROOT / name).read_bytes())
    return digest.hexdigest()


def call(command, log, env=None):
    with log.open("w") as stream:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT, check=False)
    if result.returncode:
        raise RuntimeError(f"exit {result.returncode}: {command}; retained log: {log}")


def junit(path):
    cases = ET.parse(path).getroot().findall(".//testcase")
    if not cases:
        raise ValueError(f"empty result: {path}")
    result = {}
    for case in cases:
        name = case.attrib["name"]
        result[name] = "FAIL" if case.find("failure") is not None or case.find("error") is not None else "NOT RUN" if case.find("skipped") is not None else "PASS"
    return result


def export(raw, output, metadata):
    output.mkdir(parents=True, exist_ok=True)
    mapping = list(csv.DictReader((ROOT / "docs/test-plan/component-traceability.csv").open()))
    results = {p: junit(raw / p / "unit.xml") for p in PROFILES}
    for profile, tests in results.items():
        if any(value != "PASS" for value in tests.values()):
            raise ValueError(f"{profile}: failed/unexecuted cases retained in {raw}")
    for row in mapping:
        for profile in PROFILES:
            if results[profile].get(row["test"]) != "PASS":
                raise ValueError(f"missing successful test: {profile}/{row['test']}")
        for entry in row["implementation"].split(";"):
            path, symbol = entry.split("#")
            if symbol not in (ROOT / path).read_text():
                raise ValueError(f"stale implementation reference: {entry}")
    report = {"metadata": metadata, "scope": "Host component; system requirements/TC results remain NOT RUN", "counts": {p: len(t) for p, t in results.items()}, "component_results": mapping, "scenarios": {}, "cli_durable_rejoin": {}}
    for profile in PROFILES:
        startup = json.loads((raw / profile / "cli-rejoin/startup.json").read_text())
        scenario = json.loads((raw / profile / "cli-rejoin/logical-rejoin.json").read_text())
        if startup != {"first_epoch": 1, "rejoin_epoch": 2, "model_epoch": 7} or not scenario["passed"]:
            raise ValueError(f"durable CLI rejoin failed: {profile}")
        report["cli_durable_rejoin"][profile] = {"startup": startup, "passed": scenario["passed"]}
    for name, test in SCENARIOS.items():
        for profile in PROFILES:
            data = json.loads((raw / profile / f"{name}.json").read_text())
            if not data["passed"] or not data["ownership_ok"] or not data["physical_ok"]:
                raise ValueError(f"invalid scenario: {profile}/{name}")
            if "feedback-loss" in name or "partial-front" in name or "rejoin" in name:
                if not (1_200_000_000 <= data["first_fault_ns"] <= data["all_protected_ns"] <= 1_300_000_000):
                    raise ValueError(f"wrong injection/protection interval: {profile}/{name}")
            report["scenarios"][f"{profile}/{name}"] = {"test": test, **data}
        rows = list(csv.DictReader((raw / "normal" / f"{name}.csv").open()))
        # Original integer source timestamps and values are copied verbatim.
        keep = set(range(0, len(rows), 2)) | {len(rows)-1}
        for ns in (1_200_000_000, 2_300_000_000, report["scenarios"][f"normal/{name}"]["first_fault_ns"]):
            if rows:
                keep.add(min(range(len(rows)), key=lambda i: abs(float(rows[i]["elapsed_ms"]) - ns/1e6)))
        with (output / f"{name}.csv").open("w") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader()
            writer.writerows(rows[i] for i in sorted(keep))
    (output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    plot(output)
    print(json.dumps({"counts": report["counts"], "component_links": len(mapping), "source_commit": metadata["source_commit"], "output": str(output)}, ensure_ascii=False))


def plot(output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    matplotlib.rcParams["svg.fonttype"] = "none"
    for name in ("logical-normal", "logical-feedback-loss", "logical-rejoin"):
        rows = list(csv.DictReader((output / f"{name}.csv").open()))
        x = [float(r["elapsed_ms"])/1000 for r in rows]
        fig, axes = plt.subplots(3, 1, sharex=True, figsize=(7.2, 5.4), constrained_layout=True)
        for ax, field, label in zip(axes, ("angle_rad", "pressure_pa", "torque_nm"), ("Angle [rad]", "Pressure [MPa]", "Torque [Nm]")):
            scale = 1e6 if field == "pressure_pa" else 1
            ax.plot(x, [float(r[field])/scale for r in rows], linewidth=1.4)
            ax.set_ylabel(label); ax.grid(alpha=.25)
            if name != "logical-normal": ax.axvline(1.2, color="#b54", linestyle="--", linewidth=.9)
            if name == "logical-rejoin": ax.axvline(2.3, color="#478", linestyle="--", linewidth=.9)
        axes[-1].set_xlabel("Logical elapsed time [s]"); axes[0].set_title(name)
        fig.savefig(output / f"{name}.svg", metadata={"Date": None}); plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("build/m4-async-verification"))
    parser.add_argument("--output", type=Path, default=Path("build/m4-async-evidence"))
    parser.add_argument("--reuse", action="store_true", help="reuse matching sources, retaining the original tested commit")
    args = parser.parse_args()
    raw, output = args.raw_dir.resolve(), args.output.resolve()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    digest = fingerprint()
    if args.reuse:
        metadata = json.loads((raw / "metadata.json").read_text())
        if metadata["source_digest"] != digest:
            raise ValueError("reuse rejected: tested source/commit differs")
    else:
        raw.mkdir(parents=True, exist_ok=False)
        metadata = {"source_commit": commit, "source_digest": digest, "source_dirs": SOURCE_DIRS, "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "kernel": platform.release(), "machine": platform.machine(), "cpu_count": os.cpu_count(), "affinity": sorted(os.sched_getaffinity(0)),
                    "scheduler_policy": os.sched_getscheduler(0), "compiler": subprocess.check_output(["c++", "--version"], text=True).splitlines()[0],
                    "cmake": subprocess.check_output(["cmake", "--version"], text=True).splitlines()[0],
                    "python": platform.python_version(), "transport_poll_ns": 200000, "physical_step_ns": 1000000,
                    "control_period_ns": 10000000, "bms_allocation_period_ns": 20000000, "model_epoch": 7, "wheel_speed_rad_s": 0,
                    "acceleration_mps2": .2, "curvature_inv_m": .02, "pack_auxiliary_current_a": .25,
                    "injection_ns": 1200000000, "explicit_rejoin_ns": 2300000000, "system_tc_status": "NOT RUN"}
        (raw / "metadata.json").write_text(json.dumps(metadata, indent=2)+"\n")
        for profile, build in PROFILES.items():
            folder = raw / profile; folder.mkdir()
            command = ["cmake", "-S", ".", "-B", build, "-DCMAKE_BUILD_TYPE=Debug", f"-DSTRATADRIVE_SANITIZERS={'ON' if profile == 'sanitized' else 'OFF'}"]
            call(command, folder / "configure.txt"); call(["cmake", "--build", build, "-j", "4"], folder / "build.txt")
            env = {**os.environ, "STRATADRIVE_M4_RESULTS": str(folder)}
            call(["ctest", "--test-dir", build, "--output-on-failure", "--output-junit", str(folder / "unit.xml")], folder / "ctest.txt", env)
            demo = str(ROOT / build / "actuator_demo")
            call([demo, "epoch", "init", str(folder / "epoch-store")], folder / "cli-init.txt")
            call([demo, "m4-async", "logical", "rejoin", str(folder / "epoch-store"), str(folder / "cli-rejoin")], folder / "cli-rejoin.txt")
        if fingerprint() != digest:
            raise ValueError("sources changed during verification")
    export(raw, output, metadata)


if __name__ == "__main__":
    main()

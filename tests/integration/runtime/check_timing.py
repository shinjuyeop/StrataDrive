#!/usr/bin/env python3
"""Run/analyze finite M3 Steering or multirate/vCAN experiments; retain every job."""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def distribution(values):
    """Nearest-rank percentiles of individual observations, never of run percentiles."""
    ordered = sorted(values)
    if not ordered:
        return {"samples": 0, "mean": None, "p95": None, "p99": None, "max": None}
    return {"samples": len(ordered), "mean": statistics.fmean(ordered),
            "p95": ordered[math.ceil(.95 * len(ordered)) - 1],
            "p99": ordered[math.ceil(.99 * len(ordered)) - 1], "max": ordered[-1]}


def job_metrics(rows):
    require(bool(rows), "empty schedule")
    for row in rows:
        require(row["deadline_ns"] > row["release_ns"], "invalid deadline")
        if row["ran"]:
            require(row["end_ns"] >= row["start_ns"] >= row["release_ns"], "invalid job interval")
        else:
            require(row["start_ns"] == row["end_ns"] == 0, "skipped job has fabricated execution")
    ran = [r for r in rows if r["ran"]]
    # A completion not visible to the monitor at deadline also remains a miss,
    # even if the worker was preempted just after taking its end timestamp.
    missed = [r for r in rows if r["detected_ns"] or not r["ran"] or r["end_ns"] > r["deadline_ns"]]
    return {"eligible_jobs": len(rows), "executed_jobs": len(ran), "skipped_jobs": len(rows) - len(ran),
            "missed_jobs": len(missed), "miss_rate": len(missed) / len(rows),
            "job_elapsed_ms": distribution([(r["end_ns"] - r["start_ns"]) / 1e6 for r in ran]),
            "start_lateness_ms": distribution([(r["start_ns"] - r["release_ns"]) / 1e6 for r in ran]),
            "response_time_ms": distribution([(r["end_ns"] - r["release_ns"]) / 1e6 for r in ran]),
            "observed_start_interval_ms": distribution([(b["start_ns"] - a["start_ns"]) / 1e6 for a, b in zip(ran, ran[1:])])}


def load_rows(path, integer=True):
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    return [{k: (float(v) if k == "angle_rad" and not integer else int(v)) for k, v in r.items()} for r in rows]


def validate_feedback(row):
    if not row["feedback_publish_ns"]:
        return
    if row["feedback_valid"]:
        require(row["feedback_source_ns"] == row["input_source_ns"], "feedback source refreshed/fabricated")
    else:
        # Unavailable is a diagnostic generated at job time, not a fresh angle.
        require(row["feedback_source_ns"] == row["job_time_ns"], "invalid diagnostic generation time")
    require(row["feedback_source_ns"] <= row["job_time_ns"] <= row["feedback_publish_ns"] <= row["deadline_ns"], "late/future feedback")
    require(not row["fault"] or row["feedback_failsafe"], "fault feedback lost protection state/origin")
    if row["command_rx_ns"]:
        require(row["causal_sequence"] == row["command_sequence"], "command correlation lost")


def analyze(directory):
    metadata = json.loads((directory / "run.json").read_text())
    if metadata.get("family") == "multirate":
        return analyze_multirate(directory, metadata)
    rows = load_rows(directory / "jobs.csv")
    plants = load_rows(directory / "plant.csv", integer=False)
    watches = load_rows(directory / "monitor.csv")
    metrics = job_metrics(rows)
    require(metadata["schema"] == 1 and metadata["clock"] == "CLOCK_MONOTONIC", "unknown trace/clock schema")
    require(not metadata["aborted"] and not metadata["monitor_clock_error"], "runtime aborted/clock fault")
    require(metadata["trace_drops"] == metadata["expired_outputs"] == metadata["input_read_empty"] == 0, "trace/output/initial input loss")
    require(len(rows) == metadata["jobs"] and [r["job"] for r in rows] == list(range(len(rows))), "missing/duplicate schedule rows")
    require(metadata["monitor_ended_ns"] >= rows[-1]["deadline_ns"], "last jobs not monitored through deadline")
    for index, row in enumerate(rows):
        require(row["release_ns"] == metadata["enable_ns"] + (index + 1) * metadata["period_ns"], "schedule drift")
        require(row["deadline_ns"] - row["release_ns"] == metadata["relative_deadline_ns"], "deadline changed")
        if not row["ran"] or row["end_ns"] > row["deadline_ns"]:
            require(row["detected_ns"] >= row["deadline_ns"], "monitor omitted missed job")
        if row["detected_ns"]:
            require(row["detected_ns"] >= row["deadline_ns"], "early deadline fault")
        if row["ran"]:
            require(row["start_ns"] <= row["job_time_ns"] <= row["end_ns"], "logical job time outside execution")
        validate_feedback(row)
        if metadata["detailed_trace"] and row["ran"]:
            require(row["start_ns"] <= row["prepare_begin_ns"] <= row["prepare_end_ns"] <= row["complete_begin_ns"] <= row["complete_end_ns"] <= row["end_ns"], "invalid phase endpoints")
    phases = [r for r in rows if r["prepare_begin_ns"]]
    metrics["ecu_prepare_plus_complete_ms"] = distribution([
        (r["prepare_end_ns"] - r["prepare_begin_ns"] + r["complete_end_ns"] - r["complete_begin_ns"]) / 1e6 for r in phases])
    metrics["sensor_to_local_feedback_ms"] = distribution([
        (r["feedback_publish_ns"] - r["feedback_source_ns"]) / 1e6 for r in rows if r["feedback_publish_ns"] and r["feedback_valid"]])
    metrics["monitor_deadline_lateness_ms"] = distribution([
        (r["detected_ns"] - r["deadline_ns"]) / 1e6 for r in rows if r["detected_ns"]])
    metrics["physics_and_capture_ms"] = distribution([(r["physics_end_ns"] - r["physics_begin_ns"]) / 1e6 for r in plants])
    if metadata["detailed_trace"]:
        require(plants and watches, "missing detailed owner traces")
        for a, b in zip(plants, plants[1:]):
            require(b["time_ns"] > a["time_ns"] and b["sensor_sequence"] > a["sensor_sequence"], "plant/acquisition stopped")
        for row in plants:
            require(row["sensor_source_ns"] == row["time_ns"], "plant acquisition timestamp mismatch")
            require(row["time_ns"] <= row["physics_begin_ns"] <= row["physics_end_ns"], "invalid physics interval")
            if row["last_ecu_applied_job"] >= 0:
                job = rows[row["last_ecu_applied_job"]]
                require(row["output_issued_ns"] == job["job_time_ns"], "output lost job identity")
                require(row["output_issued_ns"] <= row["output_applied_ns"] <= job["deadline_ns"], "output applied late/backdated")
        require(all(b["time_ns"] > a["time_ns"] for a, b in zip(watches, watches[1:])), "monitor clock stopped")
    else:
        require(not plants and not watches and not phases, "minimal instrumentation still writes detailed events")
    applications = {r["last_ecu_applied_job"]: r for r in plants if r["last_ecu_applied_job"] >= 0}
    metrics["output_issue_to_apply_ms"] = distribution([
        (r["output_applied_ns"] - r["output_issued_ns"]) / 1e6 for r in applications.values()])
    if metadata["scenario"] == "normal":
        require(metrics["missed_jobs"] == 0 and metrics["executed_jobs"] == len(rows), "normal workload missed jobs")
        require(metadata["hold_applied_ns"] == 0, "unexpected independent hold")
        require(all(r["prepared"] and r["fault"] == 0 and r["feedback_publish_ns"] and r["feedback_valid"] for r in rows), "normal ECU fault/feedback loss")
        if plants:
            require(abs(plants[-1]["angle_rad"] - .3) < 1e-12, "normal physical target not reached")
    else:
        injected = rows[metadata["injected_job"]]
        begin, end = injected["injection_begin_ns"], injected["injection_end_ns"]
        require(begin and end > begin, "fault job was not injected")
        require(injected["end_ns"] > injected["deadline_ns"] and not injected["feedback_publish_ns"], "late injected job published feedback")
        first = next((r for r in rows if r["detected_ns"]), None)
        require(first is not None and first["job"] == injected["job"], "unrelated earlier deadline failure")
        detection, hold = first["detected_ns"], metadata["hold_applied_ns"]
        require(begin <= detection <= hold < end, "monitor/action waited for ECU return")
        require(detection - first["deadline_ns"] <= 10_000_000 and hold - detection <= 10_000_000, "local monitor/action margin exceeded")
        require(metrics["skipped_jobs"] > 0, "overload hid skipped jobs")
        require(any(r["start_ns"] > end and r["feedback_publish_ns"] and r["feedback_failsafe"] for r in rows), "protected diagnostics did not resume")
        metrics["first_detection_after_deadline_ms"] = (detection - first["deadline_ns"]) / 1e6
        metrics["hold_after_detection_ms"] = (hold - detection) / 1e6
        if plants:
            require(sum(begin < r["time_ns"] < end for r in plants) >= 2, "plant did not run during ECU stall")
            require(any(begin < r["time_ns"] < end for r in watches), "monitor did not run during ECU stall")
            held = [r for r in plants if r["override_hold"]]
            require(held and held[0]["time_ns"] == hold and held[0]["angle_rad"] > 0, "hold action missing/motion not established")
            require(all(abs(r["angle_rad"] - held[0]["angle_rad"]) < 1e-12 for r in held), "independent hold changed/rewound angle")
    return {"verdict": "PASS", "scope": "Host Steering component; full TC-PERF/E2E NOT RUN", "metadata": metadata, "metrics": metrics}


def receive_latency(stream):
    require(stream["health"] in (1, 2), "stream never acquired/clock fault")
    require(stream["last_valid_ns"] > 0, "missing original last-valid reference")
    if stream["health"] == 1:
        require(stream["detected_ns"] == 0, "live stream has a latched detection")
        return None
    elapsed = stream["detected_ns"] - stream["last_valid_ns"]
    require(80_000_000 <= elapsed <= 100_000_000, "valid RX loss outside 80..100 ms budget")
    return elapsed / 1e6


def multirate_rows(path):
    floating = {"pressure_pa", "torque_nm", "bus_v", "current_a", "soc", "balance_j", "selected"}
    with path.open(newline="") as stream:
        return [{k: float(v) if k in floating else int(v) for k, v in row.items()} for row in csv.DictReader(stream)]


def analyze_multirate(directory, metadata):
    require(metadata["schema"] == 2 and metadata["clock"] == "CLOCK_MONOTONIC", "unknown multirate schema/clock")
    require(not metadata["aborted"] and metadata["trace_drops"] == metadata["expired_outputs"] == 0, "runtime/output/trace failure")
    rows, metrics = {}, {}
    expected_periods = {"brake": 10_000_000, "drive": 10_000_000, "bms": 20_000_000, "power": 10_000_000, "rx": 2_000_000}
    require(len(metadata["tasks"]) == len(expected_periods) and {t["name"] for t in metadata["tasks"]} == set(expected_periods), "missing/duplicate task")
    for task in metadata["tasks"]:
        name = task["name"]
        task_rows = multirate_rows(directory / (name + "-jobs.csv"))
        require(task["period_ns"] == expected_periods[name], "wrong runnable rate")
        require(len(task_rows) == task["jobs"] and [r["job"] for r in task_rows] == list(range(task["jobs"])), "missing/duplicate job rows")
        require(metadata["monitor_ended_ns"] >= task_rows[-1]["deadline_ns"], "monitor stopped before last deadline")
        for i, row in enumerate(task_rows):
            require(row["release_ns"] == task["first_release_ns"] + i * task["period_ns"], "release drift")
            require(row["deadline_ns"] == row["release_ns"] + task["deadline_ns"], "deadline inferred from period")
            if not row["ran"] or row["end_ns"] > row["deadline_ns"]:
                require(row["detected_ns"] >= row["deadline_ns"], "independent monitor omitted missed work")
            if row["ran"]:
                require(row["start_ns"] <= row["phase_ns"] <= row["end_ns"], "invalid phase clock")
                require(0 <= row["ecu_elapsed_ns"] <= row["end_ns"] - row["start_ns"], "physics/injection included as ECU cost")
                require(row["input_source_ns"] <= row["phase_ns"], "future sensor")
            if row["reported"]:
                require(row["end_ns"] <= row["deadline_ns"], "late admitted feedback")
                require(row["report_source_ns"] == (row["input_source_ns"] if row["value_valid"] else row["phase_ns"]), "original report source lost")
            require(row["raw_frames"] <= metadata["rx_budget"], "RX drain unbounded")
        rows[name] = task_rows
        metrics[name] = job_metrics(task_rows)
        metrics[name]["ecu_elapsed_ms"] = distribution([r["ecu_elapsed_ns"] / 1e6 for r in task_rows if r["ran"] and name != "rx"])
    latencies = {s["name"]: receive_latency(s) for s in metadata["streams"]}
    physical = multirate_rows(directory / "physical.csv")
    watches = multirate_rows(directory / "monitor.csv")
    raw = multirate_rows(directory / "can-rx.csv")
    if metadata["detailed_trace"]:
        require(physical and watches and raw, "missing owner trace")
        require(all(b["time_ns"] > a["time_ns"] for a, b in zip(physical, physical[1:])), "physics clock regressed")
        require(all(r["time_ns"] == r["brake_source_ns"] == r["torque_source_ns"] for r in physical), "acquisition source fabricated")
        require(all(r["physics_end_ns"] >= r["physics_begin_ns"] >= r["time_ns"] for r in physical), "invalid physics cost")
        require(all(r["kernel_drops"] == 0 for r in raw), "unreported kernel continuity loss")
        require({r["stream"] for r in raw if r["crc_ok"]} == set(range(5)), "stream never arrived intact")
        require(max(abs(r["balance_j"]) for r in physical) <= .00072, "EV energy conservation failed")
    else:
        require(not physical and not watches and not raw, "minimal mode recorded detailed buffers")
    # A delayed independent torque acquisition remains unavailable on the
    # existing Drive wire. Never stamp it as a fresh end-of-job measurement.
    require(all(not r["value_valid"] for r in rows["drive"] if r["input_source_ns"] != r["phase_ns"]), "Drive torque retimestamped")
    require(any(r["active"] and r["selected"] > 0 for r in rows["drive"]), "Drive gate never enabled before fault")
    require(any(r["state"] == 2 and not r["inhibit"] for r in rows["bms"]), "BMS never passed fresh release dwell")
    require(any(r["state"] == 7 for r in rows["power"]), "power never reached measured READY")
    final = metadata["final_physical"]
    require(final and 0 < final["soc"] < .5 and abs(final["balance_j"]) <= .00072, "missing actual energy flow")
    scenario = metadata["scenario"]
    if scenario == "normal":
        require(all(m["missed_jobs"] == m["skipped_jobs"] == 0 for m in metrics.values()), "normal multirate missed jobs")
        require(all(r["fault"] == 0 for name in ("brake", "drive", "bms", "power") for r in rows[name]), "normal ECU fault")
        require(all(value is None for value in latencies.values()), "normal stream timed out")
        require(metadata["floor_applied_ns"] == metadata["zero_applied_ns"] == 0, "unexpected independent action")
        require(abs(final["pressure_pa"] - 1300000) < 1e-5 and abs(final["torque_nm"] - 250) < 1e-8, "normal response not reached")
    elif scenario.endswith("-stall"):
        name = scenario.removesuffix("-stall")
        injected = next((r for r in rows[name] if r["injection_begin_ns"]), None)
        require(injected is not None, "stall not injected")
        begin, end, detection = injected["injection_begin_ns"], injected["injection_end_ns"], injected["detected_ns"]
        require(end - begin >= 120_000_000 and begin <= detection < end, "monitor waited for stopped task")
        require(0 <= detection - injected["deadline_ns"] <= 10_000_000, "deadline monitor late")
        require(metrics[name]["skipped_jobs"] > 0 and not injected["reported"], "late job hidden/published")
        require(all(m["missed_jobs"] == 0 for other, m in metrics.items() if other != name), "unrelated task missed deadline")
        action = metadata["floor_applied_ns"] if name == "brake" else metadata["zero_applied_ns"]
        require(detection <= action < end and action - detection <= 10_000_000, "independent action waited for task")
        if physical:
            require(sum(begin < r["time_ns"] < end for r in physical) >= 20, "plant paused with ECU")
            require(any(begin < r["time_ns"] < end for r in watches), "monitor paused with ECU")
            if name == "power":
                require(all(r["positive"] and r["negative"] for r in physical if begin < r["time_ns"] < end), "power watchdog blindly opened contacts")
        metrics[name]["first_detection_after_deadline_ms"] = (detection - injected["deadline_ns"]) / 1e6
        metrics[name]["independent_action_after_detection_ms"] = (action - detection) / 1e6
    elif scenario == "rx-corrupt":
        require(all(m["missed_jobs"] == 0 for m in metrics.values()), "corrupt RX confused with task stall")
        require(all(value is not None for value in latencies.values()), "CRC traffic refreshed valid RX")
        require(raw and any(not r["crc_ok"] and r["time_ns"] > min(s["detected_ns"] for s in metadata["streams"]) for r in raw), "raw corrupt traffic did not continue after detection")
    else:
        raise AssertionError("unknown multirate scenario")
    if scenario != "normal":
        if metadata["zero_applied_ns"]:
            require(abs(final["torque_nm"]) < 1e-8, "independent zero never reached")
            if physical:
                action = metadata["zero_applied_ns"]
                require(any(r["time_ns"] >= action and r["torque_nm"] > 1 for r in physical), "actual torque clipped to zero")
        if metadata["floor_applied_ns"]:
            require(final["pressure_pa"] >= 1000000, "brake floor not reached")
            held = [r for r in physical if r["independent_floor"]]
            require(all(b["pressure_pa"] >= a["pressure_pa"] - 1e-6 for a, b in zip(held, held[1:])), "brake protection released pressure")
        if scenario in ("bms-stall", "power-stall", "rx-stall", "rx-corrupt"):
            require(rows["power"][-1]["inhibit"], "fault automatically restored driving permission")
    return {"verdict": "PASS", "scope": "Host multirate/vCAN component; full system TC NOT RUN", "metadata": metadata,
            "metrics": metrics, "valid_rx_loss_ms": latencies}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def environment(build, binary, family):
    tracked = subprocess.check_output(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT, text=True).splitlines()
    sources = sorted({name for name in tracked if name.endswith((".cpp", ".hpp", ".yaml", ".py")) or name == "CMakeLists.txt"})
    cache = (build / "CMakeCache.txt").read_text()
    selected = {line.split(":", 1)[0]: line.split("=", 1)[1] for line in cache.splitlines()
                if "=" in line and line.startswith(("CMAKE_BUILD_TYPE:", "CMAKE_CXX_COMPILER:", "CMAKE_CXX_FLAGS:", "CMAKE_CXX_FLAGS_DEBUG:", "CMAKE_CXX_FLAGS_RELEASE:", "STRATADRIVE_SANITIZERS:", "BUILD_TESTING:"))}
    governor = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
    cpu_info = Path("/proc/cpuinfo").read_text()
    cpu_model = next((line.split(":", 1)[1].strip() for line in cpu_info.splitlines() if line.startswith("model name")), "unknown")
    return {"utc_started": datetime.now(timezone.utc).isoformat(), "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "working_tree": subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True).splitlines(),
            "binary_sha256": sha256(binary), "build_settings": selected, "cmake_cache_sha256": sha256(build / "CMakeCache.txt"),
            "compiler": subprocess.check_output([selected["CMAKE_CXX_COMPILER"], "--version"], text=True).splitlines()[0],
            "platform": platform.platform(), "machine": platform.machine(), "cpu_model": cpu_model, "cpu_count": os.cpu_count(),
            "cpu_affinity": sorted(os.sched_getaffinity(0)), "cpu_governor": governor.read_text().strip() if governor.exists() else "unknown",
            "load_average_before": os.getloadavg(), "power_clocks_cooling": "not controlled; governor observed only",
            "warmup_jobs_excluded": 0, "clock_sync": "single process CLOCK_MONOTONIC; cross-node N/A",
            "family": family,
            "simulator": ("wall-time functional SteeringResponse; CARLA N/A" if family == "steering" else "wall-time Brake/Drive response and EV circuit/Battery; CARLA N/A"),
            "percentile_estimator": "nearest rank over individual observations",
            "fixture_deadline": ("5 ms" if family == "steering" else "Brake/Drive/Power 5 ms, BMS 8 ms, RX 3 ms") + "; chosen for this Host experiment, not vehicle/Target deadlines",
            "source_sha256": {name: sha256(ROOT / name) for name in sources}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=ROOT / "build/m1-angle")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--family", choices=("steering", "multirate"), default="steering")
    parser.add_argument("--analyze", type=Path, help="analyze one existing runtime trace without executing")
    args = parser.parse_args()
    if args.analyze:
        print(json.dumps(analyze(args.analyze), indent=2))
        return 0
    require(1 <= args.repetitions <= 20, "repetitions must be 1..20")
    build = args.build_dir.resolve()
    binary = build / "actuator_demo"
    output = (args.output_dir or build / ("timing-results-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ"))).resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / "environment.json").write_text(json.dumps(environment(build, binary, args.family), indent=2) + "\n")
    reports = []
    conditions = [("normal", True), ("normal", False), ("overrun", True), ("stall", True)]
    interface = "m3timing0"
    created = False
    if args.family == "multirate":
        conditions = [("normal", True), ("normal", False)] + [(name + "-stall", True) for name in ("brake", "drive", "bms", "power", "rx")] + [("rx-corrupt", True)]
        subprocess.run(["ip", "link", "add", "dev", interface, "type", "vcan"], check=True)
        created = True
        try:
            subprocess.run(["ip", "link", "set", "dev", interface, "mtu", "72", "up"], check=True)
        except BaseException:
            subprocess.run(["ip", "link", "delete", "dev", interface], check=True)
            raise
    # Alternate full/minimal normals; do not group all full runs before all minimal runs.
    try:
        for repetition in range(args.repetitions):
            for scenario, detailed in conditions:
                label = f"{scenario}-{'full' if detailed else 'minimal'}-{repetition+1}"
                directory = output / label
                command = [str(binary), "steering-runtime", scenario, str(directory)] if args.family == "steering" else [str(binary), "multirate-runtime", scenario, interface, str(directory)]
                command += [] if detailed else ["trace-off"]
                begin = time.monotonic_ns()
                try:
                    process = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
                    (output / (label + ".stdout.txt")).write_text(process.stdout)
                    (output / (label + ".stderr.txt")).write_text(process.stderr)
                    require(process.returncode == 0, f"runtime exit {process.returncode}: {process.stderr.strip()}")
                    report = analyze(directory)
                except (AssertionError, OSError, ValueError, subprocess.TimeoutExpired) as error:
                    report = {"verdict": "FAIL", "error": str(error)}
                report.update(label=label, directory=str(directory), observed_process_wall_ns=time.monotonic_ns()-begin)
                reports.append(report)
                print(label, report["verdict"], report.get("error", ""), flush=True)
    finally:
        if created:
            subprocess.run(["ip", "link", "delete", "dev", interface], check=True)
    role_overheads = {}
    for role in (("steering",) if args.family == "steering" else ("brake", "drive", "bms", "power", "rx")):
        overhead = {}
        for detailed in (True, False):
            values = []
            for report in reports:
                if report["verdict"] == "PASS" and report["label"].startswith("normal-" + ("full" if detailed else "minimal")):
                    path = Path(report["directory"]) / ("jobs.csv" if role == "steering" else role + "-jobs.csv")
                    task_rows = load_rows(path) if role == "steering" else multirate_rows(path)
                    values.extend((r["end_ns"] - r["start_ns"]) / 1e6 for r in task_rows if r["ran"])
            overhead["full_ms" if detailed else "minimal_ms"] = distribution(values)
        if overhead["full_ms"]["samples"] and overhead["minimal_ms"]["samples"]:
            overhead["observed_mean_difference_ms"] = overhead["full_ms"]["mean"] - overhead["minimal_ms"]["mean"]
        overhead["interpretation"] = "separate runs; includes scheduler/cache noise; no correction subtracted from deadlines"
        role_overheads[role] = overhead
    overhead = role_overheads["steering"] if args.family == "steering" else {"by_task": role_overheads}
    summary = {"verdict": "PASS" if all(r["verdict"] == "PASS" for r in reports) else "FAIL", "runs": reports,
               "trace_overhead_comparison": overhead, "full_system_tc": "NOT RUN"}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    artifacts = {str(p.relative_to(output)): sha256(p) for p in sorted(output.rglob("*")) if p.is_file()}
    (output / "artifact-sha256.json").write_text(json.dumps(artifacts, indent=2) + "\n")
    print(summary["verdict"], output, flush=True)
    return 0 if summary["verdict"] == "PASS" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, ValueError) as error:
        raise SystemExit(str(error)) from error

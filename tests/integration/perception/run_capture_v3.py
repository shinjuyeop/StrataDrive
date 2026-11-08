#!/usr/bin/env python3
"""Own one fresh CARLA process, read-only readiness, capture, bounded cleanup."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import socket
import subprocess
import sys
import time
import traceback


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--engine", type=Path, required=True)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--python", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--port", type=int, default=2300)
    p.add_argument(
        "--mode",
        choices=("capture", "live", "quality", "quality-v3"),
        default="capture",
    )
    p.add_argument("--plan", type=Path)
    p.add_argument("--partition", choices=("preparation", "development", "holdout"))
    p.add_argument("--selection", type=Path)
    p.add_argument("--probe-python", type=Path)
    p.add_argument("--model", type=Path)
    p.add_argument("--execution", choices=("cpu", "cuda"), default="cuda")
    p.add_argument("--frames", type=int, default=300)
    p.add_argument(
        "--fault",
        choices=("none", "slow", "exception", "blackout", "silence"),
        default="none",
    )
    p.add_argument("--boundary", type=Path)
    p.add_argument(
        "--camera-clock", choices=("frame5", "sensor-tick"), default="frame5"
    )
    p.add_argument("--quality", choices=("Low", "Epic"), default="Low")
    p.add_argument(
        "--rgb-postprocess", choices=("disabled", "enabled"), default="disabled"
    )
    args = p.parse_args()
    is_quality = args.mode in ("quality", "quality-v3")
    if is_quality and (not args.plan or not args.partition or args.quality != "Epic"):
        p.error("quality requires --plan, --partition and --quality Epic")
    if is_quality and args.partition == "holdout" and not args.selection:
        p.error("holdout acquisition requires a sealed --selection")
    if args.mode == "live" and not (args.probe_python and args.model and args.boundary):
        p.error("live requires --probe-python, --model and --boundary")
    if args.mode == "live" and args.quality != "Low":
        p.error(
            "live renderer profile requires Low quality; Epic is capture diagnostic only"
        )
    if (
        args.mode == "live"
        and args.rgb_postprocess == "enabled"
        and args.camera_clock != "frame5"
    ):
        p.error("explicit RGB live profile requires frame5 scheduling")
    if is_quality:
        plan_input = json.loads(args.plan.read_text())
        if any(a["blueprint"] == "vehicle.carlamotors.european_hgv" for v in plan_input["partitions"].values() for c in v["cases"] for a in c["actors"]):
            p.error("incompatible NW asset denied before server launch")
    guards = []
    try:
        for port in range(args.port, args.port + 3):
            sock = socket.socket()
            guards.append(sock)
            sock.bind(("127.0.0.1", port))
    finally:
        for sock in guards:
            sock.close()
    args.output.mkdir(parents=True, exist_ok=False)
    selection_digest = None
    if is_quality and args.partition == "holdout":
        selected = args.output / "candidate-selection.json"
        shutil.copy2(args.selection, selected)
        selection_digest = hashlib.sha256(selected.read_bytes()).hexdigest()
    command = [
        str(args.engine / "Engine/Binaries/Linux/UE4Editor"),
        str(args.source / "Unreal/CarlaUE4/CarlaUE4.uproject"),
        "/Game/Carla/Maps/Town03_Opt",
        "-game",
        "-FixedSeed",
        "-RenderOffScreen",
        "-nosound",
        "-unattended",
        "-nosplash",
        "-carla-server",
        f"-carla-rpc-port={args.port}",
        f"-quality-level={args.quality}",
        "-StrataM7SensorFrame5",
        "-ini:EditorSettings:[/Script/UnrealEd.CrashReportsPrivacySettings]:bSendUnattendedBugReports=False",
        "-ini:Engine:[CrashReportClient]:bAgreeToCrashUpload=False,[CrashReportClient]:bImplicitSend=False",
        "-log",
        "-stdout",
        "-FullStdOutLogOutput",
    ]
    if args.mode == "live" and args.camera_clock == "frame5":
        # Existing prepared CARLA sensor patch requires this flag AND role_name.
        # No native owner bind, solver-work/vehicle320 or control RPC is issued.
        command.append("-StrataM7NativeProbe")
    report = {
        "status": "FAIL",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode,
        "selection_sha256": selection_digest,
        "argv": command,
        "startup_budget_seconds": 180,
        "capture_budget_seconds": 900 if is_quality else 180,
        "source_head": subprocess.check_output(
            ["git", "-C", str(args.source), "rev-parse", "HEAD"], text=True
        ).strip(),
    }
    if args.mode == "live":
        source_root = args.source / "Unreal/CarlaUE4/Plugins/Carla/Source/Carla"
        report["sensor_scheduler_sources"] = {
            name: hashlib.sha256((source_root / name).read_bytes()).hexdigest()
            for name in ("Sensor/Sensor.cpp", "M7NoDrive/M7NoDrivePort.cpp")
        }
    proc = None
    begun = time.monotonic()

    def no_core():
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    ready_code = """
import carla,json,sys,time
c=carla.Client('127.0.0.1',int(sys.argv[1]));end=time.monotonic()+float(sys.argv[2])
while time.monotonic()<end:
 c.set_timeout(2)
 try:
  w=c.get_world();s=w.get_snapshot()
  if s.frame>0:
   print(json.dumps({'frame':s.frame,'version':c.get_server_version(),'world':w.id}));sys.exit(0)
 except RuntimeError as error:print(str(error),flush=True)
 time.sleep(.2)
sys.exit(1)
"""
    try:
        with (args.output / "server.log").open("w") as log:
            proc = subprocess.Popen(
                command,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                preexec_fn=no_core,
            )
        report["pid"] = proc.pid
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise RuntimeError("server exited before RPC readiness")
            try:
                with socket.create_connection(("127.0.0.1", args.port), timeout=0.5):
                    break
            except OSError:
                time.sleep(0.2)
        else:
            raise TimeoutError("RPC port readiness")
        remaining = deadline - time.monotonic()
        with (args.output / "readiness.log").open("w") as log:
            ready = subprocess.run(
                [str(args.python), "-c", ready_code, str(args.port), str(remaining)],
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=remaining + 2,
            )
        if ready.returncode or proc.poll() is not None:
            raise RuntimeError("server readiness failed")
        probe = args.output / "capture-probe.py"
        probe_name = {
            "live": "carla_live.py",
            "capture": "carla_capture.py",
            "quality": "carla_quality_capture.py",
            "quality-v3": "carla_quality_capture_v3.py",
        }[args.mode]
        shutil.copy2(Path(__file__).with_name(probe_name), probe)
        report["probe_sha256"] = hashlib.sha256(probe.read_bytes()).hexdigest()
        client_command = [
            str(args.probe_python if args.mode == "live" else args.python),
            str(probe),
            "--output",
            str(args.output / "dataset"),
            "--port",
            str(args.port),
        ]
        if args.mode == "live":
            client_command.extend(
                [
                    "--repo-root",
                    str(Path(__file__).resolve().parents[3]),
                    "--model",
                    str(args.model.resolve()),
                    "--execution",
                    args.execution,
                    "--frames",
                    str(args.frames),
                    "--fault",
                    args.fault,
                    "--boundary",
                    str(args.boundary.resolve()),
                    "--camera-clock",
                    args.camera_clock,
                    "--rgb-postprocess",
                    args.rgb_postprocess,
                ]
            )
        if args.mode == "capture":
            client_command.extend(["--rgb-postprocess", args.rgb_postprocess])
        if is_quality:
            plan = args.output / "quality-plan.json"
            shutil.copy2(args.plan, plan)
            report["plan_sha256"] = hashlib.sha256(plan.read_bytes()).hexdigest()
            client_command.extend(["--plan", str(plan), "--partition", args.partition])
        report["client_argv"] = client_command
        with (args.output / "client.log").open("w") as log:
            capture = subprocess.run(
                client_command,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=report["capture_budget_seconds"],
            )
        report["capture_exit"] = capture.returncode
        if capture.returncode:
            raise RuntimeError("capture failed")
        report["status"] = "PASS"
    except Exception:
        report["error"] = traceback.format_exc()
    finally:
        if proc is not None:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGINT)
                try:
                    proc.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    report["forced_stop"] = True
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait(timeout=10)
            report["server_exit"] = proc.returncode
            if proc.returncode != 130 or report.get("forced_stop"):
                report["status"] = "FAIL"
        report["elapsed_wall_seconds"] = time.monotonic() - begun
        (args.output / "server.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

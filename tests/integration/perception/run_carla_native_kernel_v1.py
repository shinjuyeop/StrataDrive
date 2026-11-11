#!/usr/bin/env python3
"""One isolated live4K observational server; bounded startup/client/shutdown."""

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
import time
import traceback
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import sha256_file


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("engine", "source", "python", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--condition", choices=("baseline", "kernel"), required=True)
    p.add_argument("--library", type=Path, required=True)
    p.add_argument("--port", type=int, default=2300)
    for key in ("freeze", "model", "models"):
        p.add_argument("--" + key, type=Path, required=True)
    a = p.parse_args()
    from probe_async_native_v1 import check_sources

    freeze_sha = check_sources(a.freeze)
    frozen = json.loads(a.freeze.read_text())
    profile_path = (
        Path(__file__).resolve().parents[3]
        / "profiles/perception-carla-native-async-v1.json"
    )
    profile = json.loads(profile_path.read_text())
    for name, digest in profile["external_files"].items():
        if sha256_file(a.source / name) != digest:
            raise ValueError("external sensor/build identity: " + name)
    if (
        sha256_file(a.plan)
        != frozen["files"]["profiles/perception-camera-resolution-plan-v1.json"]
    ):
        p.error("frozen development plan required")
    guards = []
    try:
        for port in range(a.port, a.port + 3):
            s = socket.socket()
            guards.append(s)
            s.bind(("127.0.0.1", port))
    finally:
        for s in guards:
            s.close()
    a.output.mkdir(parents=True, exist_ok=False)

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    probe = Path(__file__).resolve().parent / "carla_native_kernel_v1.py"
    head = subprocess.check_output(
        ["git", "-C", str(a.source), "rev-parse", "HEAD"], text=True
    ).strip()
    if head != "294096eb1c38eabf246e4f3a9cdab704e33a7f4c":
        raise ValueError("CARLA source HEAD")
    report = dict(
        schema="m10-carla-native-kernel-server-v1",
        condition=a.condition,
        status="FAIL",
        started_utc=datetime.now(timezone.utc).isoformat(),
        startup_budget_seconds=180,
        capture_budget_seconds=900,
        shutdown_budget_seconds=30,
        source_head=head,
        probe_sha256=sha(probe),
        freeze_sha256=freeze_sha,
        plan_sha256=sha(a.plan),
        profile_sha256=sha(profile_path),
        external_files=profile["external_files"],
    )
    shutil.copy2(probe, a.output / probe.name)
    client = [
        str(a.python),
        str(probe),
        "--condition",
        a.condition,
        "--library",
        str(a.library),
        "--output",
        str(a.output / "capture"),
        "--port",
        str(a.port),
        "--plan",
        str(a.plan),
        "--model",
        str(a.model),
        "--models",
        str(a.models),
        "--freeze",
        str(a.freeze),
    ]
    command = [
        str(a.engine / "Engine/Binaries/Linux/UE4Editor"),
        str(a.source / "Unreal/CarlaUE4/CarlaUE4.uproject"),
        "/Game/Carla/Maps/Town04_Opt",
        "-game",
        "-FixedSeed",
        "-RenderOffScreen",
        "-nosound",
        "-unattended",
        "-nosplash",
        "-carla-server",
        f"-carla-rpc-port={a.port}",
        "-quality-level=Epic",
        "-StrataM7SensorFrame5",
        "-StrataM7NativeProbe",
        "-ini:EditorSettings:[/Script/UnrealEd.CrashReportsPrivacySettings]:bSendUnattendedBugReports=False",
        "-ini:Engine:[CrashReportClient]:bAgreeToCrashUpload=False,[CrashReportClient]:bImplicitSend=False",
        "-log",
        "-stdout",
        "-FullStdOutLogOutput",
    ]
    report.update(argv=command, client_argv=client)
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

    def no_core():
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    proc = None
    begun = time.monotonic()
    try:
        with (a.output / "server.log").open("w") as log:
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
                raise RuntimeError("server exited before readiness")
            try:
                with socket.create_connection(("127.0.0.1", a.port), timeout=0.5):
                    break
            except OSError:
                time.sleep(0.2)
        else:
            raise TimeoutError("RPC port readiness")
        remaining = deadline - time.monotonic()
        with (a.output / "readiness.log").open("w") as log:
            ready = subprocess.run(
                [str(a.python), "-c", ready_code, str(a.port), str(remaining)],
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=remaining + 2,
            )
        if ready.returncode or proc.poll() is not None:
            raise RuntimeError("readiness failed")
        with (a.output / "client.log").open("w") as log:
            result = subprocess.run(
                client, stdout=log, stderr=subprocess.STDOUT, timeout=900
            )
        report["capture_exit"] = result.returncode
        if result.returncode:
            raise RuntimeError("probe failed")
        if check_sources(a.freeze) != freeze_sha:
            raise ValueError("live sources changed during run")
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
        (a.output / "server.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

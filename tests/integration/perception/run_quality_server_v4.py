#!/usr/bin/env python3
"""One isolated CARLA road survey/preparation server with unchanged bounded cleanup."""

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


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("engine", "source", "python", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--stage", choices=("survey", "preparation"), required=True)
    p.add_argument("--plan", type=Path)
    p.add_argument("--partition")
    p.add_argument("--port", type=int, default=2300)
    a = p.parse_args()
    if a.stage == "preparation":
        if not a.plan or not a.partition:
            p.error("preparation requires plan and partition")
        plan = json.loads(a.plan.read_text())
        if (
            plan["schema"] != "m10-road-preparation-plan-v4"
            or a.partition not in plan["partitions"]
        ):
            p.error("preparation plan/partition")
        if any(
            x["blueprint"] == "vehicle.carlamotors.european_hgv"
            for v in plan["partitions"].values()
            for c in v["cases"]
            for x in c["actors"]
        ):
            p.error("incompatible NW asset denied before server launch")
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

    source = Path(__file__).parent
    probe = a.output / "capture-probe.py"
    shutil.copy2(
        source
        / (
            "carla_quality_layout_v4.py"
            if a.stage == "survey"
            else "carla_quality_capture_v4.py"
        ),
        probe,
    )
    helper = a.output / "quality_geometry_v4.py"
    shutil.copy2(source / helper.name, helper)
    report = dict(
        schema="m10-road-server-v4",
        status="FAIL",
        stage=a.stage,
        started_utc=datetime.now(timezone.utc).isoformat(),
        startup_budget_seconds=180,
        capture_budget_seconds=900,
        shutdown_budget_seconds=30,
        source_head=subprocess.check_output(
            ["git", "-C", str(a.source), "rev-parse", "HEAD"], text=True
        ).strip(),
        probe_sha256=sha(probe),
        helper_sha256=sha(helper),
    )
    client = [
        str(a.python),
        str(probe),
        "--output",
        str(a.output / "dataset"),
        "--port",
        str(a.port),
    ]
    if a.stage == "preparation":
        copied = a.output / "quality-plan.json"
        shutil.copy2(a.plan, copied)
        report["plan_sha256"] = sha(copied)
        client += ["--plan", str(copied), "--partition", a.partition]
    command = [
        str(a.engine / "Engine/Binaries/Linux/UE4Editor"),
        str(a.source / "Unreal/CarlaUE4/CarlaUE4.uproject"),
        "/Game/Carla/Maps/Town03_Opt",
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

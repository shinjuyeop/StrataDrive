#!/usr/bin/env python3
"""One owned bounded2K shadow trial, unchanged native wall guards, no retry."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import secrets
import signal
import socket
import subprocess
import time
import traceback


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def verify(freeze):
    data = json.loads(freeze.read_text())
    root = Path(__file__).resolve().parents[3]
    for name, item in data["files"].items():
        if sha(root / name) != item["sha256"]:
            raise ValueError("frozen input changed: " + name)
    for name, digest in data["external"].items():
        if sha(name) != digest:
            raise ValueError("frozen runtime changed: " + name)
    return sha(freeze)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("engine", "source", "python", "native", "detector", "models", "library", "freeze", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    report = dict(schema="m10-control-shadow-server-v1", status="FAIL", started_utc=datetime.now(timezone.utc).isoformat(),
                  startup_seconds=180, client_seconds=900, shutdown_seconds=30, live_driving_acceptance=False,
                  owner_credential="ephemeral child environment; never recorded", attempts=1)
    proc = None
    ini = a.source / "Unreal/CarlaUE4/Saved/Config/Linux/GameUserSettings.ini"
    original_ini = ini.read_bytes()
    report["original_ini_sha256"] = hashlib.sha256(original_ini).hexdigest()
    began = time.monotonic()
    try:
        report["freeze_sha256"] = verify(a.freeze)
        root = Path(__file__).resolve().parents[3]
        profile = json.loads((root / "profiles/perception-source-compare-server-v2.json").read_text())
        for name, digest in profile["external_files"].items():
            if sha(a.source / name) != digest:
                raise ValueError("existing pinned server module/source: " + name)
        report["external_files"] = profile["external_files"]
        guards = []
        try:
            for port in (2200, 2201, 2202):
                sock = socket.socket();guards.append(sock);sock.bind(("127.0.0.1", port))
        finally:
            for sock in guards:
                sock.close()
        env = dict(os.environ, STRATADRIVE_M7_OWNER_KEY=secrets.token_hex(32), OMP_WAIT_POLICY="PASSIVE")
        if env.get("LD_PRELOAD"):
            raise RuntimeError("unexpected LD_PRELOAD")
        command = [str(a.engine / "Engine/Binaries/Linux/UE4Editor"),
                   str(a.source / "Unreal/CarlaUE4/CarlaUE4.uproject"), "/Game/Carla/Maps/Town03_Opt",
                   "-game", "-FixedSeed", "-RenderOffScreen", "-nosound", "-unattended", "-nosplash", "-carla-server",
                   "-carla-rpc-port=2200", "-quality-level=Epic", "-StrataM7SensorFrame5", "-StrataM7NativeProbe",
                   "-StrataM7V1Substeps320", "-StrataM7SolverWork", "-StrataM7CompactWork", "-StrataM7WallNative",
                   "-StrataM7HeldSteerSleep", "-StrataM10ReadbackProfile",
                   "-ExecCmds=r.SceneRenderTargetResizeMethod 2,r.SceneRenderTargetResizeMethodForceOverride 1",
                   "-ini:EditorSettings:[/Script/UnrealEd.CrashReportsPrivacySettings]:bSendUnattendedBugReports=False",
                   "-ini:Engine:[CrashReportClient]:bAgreeToCrashUpload=False,[CrashReportClient]:bImplicitSend=False",
                   "-log", "-stdout", "-FullStdOutLogOutput"]
        client = [str(a.python), str(Path(__file__).with_name("carla_control_shadow_v1.py")),
                  "--output", str(a.output / "capture"), "--native", str(a.native),
                  "--model", str(root / "tools/carla/m7_nodrive/virtual_ev_v1.json"),
                  "--scenario", str(root / "tests/integration/carla/scenarios/m7_integrated_v1.txt"),
                  "--ticks", "200", "--warmup-ticks", "150", "--cameras", "--wall-clock", str(secrets.randbits(63) or 1),
                  "--detector", str(a.detector), "--models", str(a.models), "--library", str(a.library)]
        report.update(argv=command, client_argv=client)
        def no_core():
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        with (a.output / "server.log").open("w") as log:
            proc = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT,
                                    start_new_session=True, preexec_fn=no_core)
        report["pid"] = proc.pid
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise RuntimeError("server exited before readiness")
            try:
                with socket.create_connection(("127.0.0.1", 2200), timeout=.5):
                    break
            except OSError:
                time.sleep(.2)
        else:
            raise TimeoutError("RPC readiness")
        ready_code = '''import carla,json,time,sys
c=carla.Client('127.0.0.1',2200);end=time.monotonic()+float(sys.argv[1])
while time.monotonic()<end:
 c.set_timeout(2)
 try:
  w=c.get_world();s=w.get_snapshot()
  if s.frame>0:
   print(json.dumps(dict(frame=s.frame,version=c.get_server_version(),world=w.id)));sys.exit(0)
 except RuntimeError as e:print(str(e),flush=True)
 time.sleep(.2)
sys.exit(1)
'''
        remaining = deadline - time.monotonic()
        with (a.output / "readiness.log").open("w") as log:
            ready = subprocess.run([str(a.python), "-c", ready_code, str(remaining)], env=env,
                stdout=log, stderr=subprocess.STDOUT, timeout=max(1, remaining + 2))
        if ready.returncode or proc.poll() is not None:
            raise RuntimeError("world readiness failed")
        with (a.output / "client.log").open("w") as log:
            capture = subprocess.run(client, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=900)
        report["capture_exit"] = capture.returncode
        if verify(a.freeze) != report["freeze_sha256"]:
            raise ValueError("frozen source changed during trial")
        if capture.returncode:
            raise RuntimeError("native live trial failed; see preserved capture evidence")
        report["status"] = "EXECUTED_REQUIRES_AUDIT"
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
                    os.killpg(proc.pid, signal.SIGKILL);proc.wait(timeout=10)
            report["server_exit"] = proc.returncode
            if proc.returncode != 130 or report.get("forced_stop"):
                report["status"] = "FAIL"
        ini.write_bytes(original_ini)
        report["restored_ini_sha256"] = sha(ini)
        report["elapsed_wall_seconds"] = time.monotonic() - began
        (a.output / "server.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    return 0 if report["status"] == "EXECUTED_REQUIRES_AUDIT" else 1


if __name__ == "__main__":
    raise SystemExit(main())

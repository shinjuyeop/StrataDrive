#!/usr/bin/env python3
"""One fresh, owned, isolated NoDrive server. Never retries an ambiguous tick.

Caller supplies existing engine/source/venv/fixture; no downloads or builds.
Owner credential exists only in child environments, never in argv or evidence.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import time
import traceback


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--engine", type=Path, required=True)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--python", type=Path, required=True)
    p.add_argument("--fixture", type=Path, required=True)
    p.add_argument("--runtime", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--vehicle-substeps", type=int, choices=(0, 20, 40, 80, 160, 320, 640), default=20)
    p.add_argument("--settle-mode", choices=("fixed100", "sleep"), default="fixed100")
    p.add_argument("--zero", action="store_true")
    p.add_argument("--native-actual", type=Path)
    p.add_argument("--solver-work", action="store_true")
    p.add_argument("--native-fault", choices=("none","credit","command","snapshot","work-missing","work-duplicate","ev-ack-missing","ev-ack-duplicate","ev-ack-energy"), default="none")
    p.add_argument("--response-fixture", type=Path)
    p.add_argument("--require-solver-wheel", action="store_true")
    p.add_argument("--native-wheel-bridge", type=Path)
    p.add_argument("--bridge-drop-snapshot", action="store_true")
    p.add_argument("--flag-check", choices=("ambiguous", "requires-v1", "disabled"),
                   help="Read-only describe rejection, without creating an ego")
    a = p.parse_args()
    if a.solver_work and not a.native_actual:
        p.error("solver work requires native Actual")
    if a.native_actual and (a.zero or a.response_fixture or a.native_wheel_bridge or a.flag_check or a.vehicle_substeps != 320):
        p.error("native Actual requires exclusive vehicle320 profile")
    root = Path(__file__).resolve().parents[3]
    # Refuse another process's ports before any server mutation.
    guards = []
    try:
        for port in (2200, 2201, 2202):
            sock = socket.socket()
            guards.append(sock)
            sock.bind(("127.0.0.1", port))
    finally:
        for sock in guards:
            sock.close()
    if a.output.exists():
        raise FileExistsError(a.output)
    a.runtime.mkdir(parents=True, exist_ok=False)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    settings = a.runtime/"CarlaSettings.ini"
    settings.write_text("[CARLA/Server]\nDisableRendering=True\n")
    argv = [str(a.engine/"Engine/Binaries/Linux/UE4Editor"),
            str(a.source/"Unreal/CarlaUE4/CarlaUE4.uproject"), "/Game/Carla/Maps/Town03_Opt",
            "-game", "-RenderOffScreen", "-nosound", "-unattended", "-nosplash", "-carla-server",
            "-ini:EditorSettings:[/Script/UnrealEd.CrashReportsPrivacySettings]:bSendUnattendedBugReports=False",
            "-ini:Engine:[CrashReportClient]:bAgreeToCrashUpload=False,[CrashReportClient]:bImplicitSend=False",
            "-carla-rpc-port=2200", "-quality-level=Low", "-carla-settings="+str(settings),
            "-StrataM7NativeProbe" if a.native_actual else ("-StrataM7ZeroProbe" if a.zero else "-StrataM7V1Probe")]
    if a.vehicle_substeps and not a.zero:
        argv.append(f"-StrataM7V1Substeps{a.vehicle_substeps}")
    if a.solver_work:
        argv.append("-StrataM7SolverWork")
    if a.flag_check == "ambiguous":
        argv.append("-StrataM7V1Substeps40" if a.vehicle_substeps == 20 else "-StrataM7V1Substeps20")
    elif a.flag_check == "requires-v1":
        argv = [v for v in argv if v not in ("-StrataM7V1Probe", "-StrataM7ZeroProbe")]
    elif a.flag_check == "disabled":
        argv = [v for v in argv if not v.startswith("-StrataM7")]
    argv += ["-log", "-stdout", "-FullStdOutLogOutput"]
    env = dict(os.environ, STRATADRIVE_M7_OWNER_KEY=secrets.token_hex(32))
    report = dict(status="FAIL", argv=argv, started_utc=datetime.now(timezone.utc).isoformat(),
                  normal_driving_enabled=False, owner_key="ephemeral child environment; value never recorded")
    def sha(path):
        digest = hashlib.sha256()
        with path.open("rb") as file:
            for block in iter(lambda: file.read(1024*1024), b""):
                digest.update(block)
        return digest.hexdigest()
    report["executed_artifact_sha256"] = {
        str(path): sha(path) for path in (
            Path(__file__), Path(__file__).with_name("m7_1m_effort.py"), a.fixture,
            a.engine/"Engine/Plugins/Runtime/PhysXVehicles/Binaries/Linux/libUE4Editor-PhysXVehicles.so",
            a.source/"Unreal/CarlaUE4/Plugins/Carla/Binaries/Linux/libUE4Editor-Carla.so",
            a.source/"Unreal/CarlaUE4/Plugins/Carla/Binaries/Linux/libUE4Editor-M7Native.so")}
    if a.native_actual:
        # Freeze exact child inputs before server startup; a subsequent IDE build
        # must not silently change the executable behind the recorded hash.
        snapshot = a.runtime/"probe"
        snapshot.mkdir()
        report["native_source_snapshots"] = {}
        for path in (a.native_actual, Path(__file__).with_name("m7_1q_probe.py"),
                     Path(__file__).with_name("audit_m7_1r_work.py"), Path(__file__).with_name("audit_m7_1q_native.py"),
                     Path(__file__).with_name("m7_1p_bridge.py"), Path(__file__).with_name("m7_1k_server_probe.py")):
            dest = snapshot/path.name
            shutil.copy2(path, dest)
            report["executed_artifact_sha256"][str(dest)] = sha(dest)
            report["native_source_snapshots"][str(path)] = str(dest)
        a.native_actual = snapshot/a.native_actual.name
    if a.response_fixture:
        report["executed_artifact_sha256"][str(a.response_fixture)] = sha(a.response_fixture)
    if a.native_wheel_bridge:
        for path in (a.native_wheel_bridge, Path(__file__).with_name("m7_1p_bridge.py")):
            report["executed_artifact_sha256"][str(path)] = sha(path)
    server = None
    started = time.monotonic()
    try:
        with (a.runtime/"server.log").open("w") as log:
            server = subprocess.Popen(argv, env=env, stdout=log, stderr=subprocess.STDOUT,
                                      start_new_session=True)
        report["pid"] = server.pid
        deadline = time.monotonic()+180
        while time.monotonic() < deadline:
            if server.poll() is not None:
                raise RuntimeError("server exited before readiness")
            try:
                with socket.create_connection(("127.0.0.1", 2200), timeout=.5):
                    break
            except OSError:
                time.sleep(.5)
        else:
            raise TimeoutError("RPC port readiness timeout")
        # A listening RPC port can precede the first usable episode snapshot
        # during cold map loading. Only read state here; never tick or mutate.
        # Share the existing 180 s startup deadline, not the driving budgets.
        readiness = a.runtime/"readiness.json"
        ready_code = """
import carla,json,sys,time
from pathlib import Path
client=carla.Client('127.0.0.1',2200)
deadline=time.monotonic()+float(sys.argv[2])
report={'status':'FAIL','attempts':[]}
try:
    while time.monotonic()<deadline:
        client.set_timeout(min(2.,max(.001,deadline-time.monotonic())))
        try:
            world=client.get_world()
            snapshot=world.get_snapshot()
            if snapshot.frame>0:
                report.update(status='READY_READ_ONLY',episode=world.id,
                              frame=snapshot.frame,elapsed_seconds=snapshot.timestamp.elapsed_seconds)
                break
        except RuntimeError as error:
            report['attempts'].append(str(error))
        time.sleep(min(.2,max(0.,deadline-time.monotonic())))
finally:
    Path(sys.argv[1]).write_text(json.dumps(report,indent=2)+'\\n')
sys.exit(0 if report['status']=='READY_READ_ONLY' else 1)
"""
        remaining = deadline-time.monotonic()
        if remaining <= 0:
            raise TimeoutError("world readiness deadline exhausted")
        with (a.runtime/"readiness.log").open("w") as log:
            ready = subprocess.run([str(a.python), "-c", ready_code, str(readiness), str(remaining)],
                                   env=env, stdout=log, stderr=subprocess.STDOUT, timeout=remaining+2)
        if readiness.exists():
            report["world_readiness"] = json.loads(readiness.read_text())
        if ready.returncode:
            raise RuntimeError("world snapshot not ready within startup deadline")
        probe = "m7_1k_server_probe.py" if a.zero else "m7_1m_effort.py"
        cmd = [str(a.python), str(Path(__file__).with_name(probe)), "--fixture", str(a.fixture),
               "--output", str(a.output)]
        if a.zero:
            cmd += ["--expected-version", "294096e-dirty"]
        else:
            cmd += ["--model", str(root/"tools/carla/m7_nodrive/virtual_ev_v1.json"),
                    "--vehicle-substeps", str(a.vehicle_substeps), "--settle-mode", a.settle_mode]
            if a.response_fixture:
                cmd += ["--response-fixture", str(a.response_fixture)]
            if a.require_solver_wheel:
                cmd += ["--require-solver-wheel"]
            if a.native_wheel_bridge:
                cmd += ["--native-wheel-bridge", str(a.native_wheel_bridge)]
            if a.bridge_drop_snapshot:
                cmd += ["--bridge-drop-snapshot"]
        if a.native_actual:
            cmd = [str(a.python), str(a.runtime/"probe/m7_1q_probe.py"), "--native", str(a.native_actual),
                   "--model", str(root/"tools/carla/m7_nodrive/virtual_ev_v1.json"), "--output", str(a.output),
                   "--fault", a.native_fault]
            if a.solver_work:
                cmd += ["--solver-work"]
        if a.flag_check:
            expected = {"ambiguous": "ambiguous_numerical_profile", "requires-v1": "numerical_profile_requires_v1",
                        "disabled": "disabled"}[a.flag_check]
            # A fresh client only reads describe. It does not bind, tick or create actors.
            code = "\n".join([
                "import carla,json,sys", "from pathlib import Path",
                "c=carla.Client('127.0.0.1',2200);c.set_timeout(10)",
                "r=json.loads(c.m7_nodrive(json.dumps({'op':'describe'})))",
                "ok=not r['ok'] and r['reason']==sys.argv[2] and not r['locked']",
                "p=Path(sys.argv[1]);p.mkdir()",
                "(p/'result.json').write_text(json.dumps({'status':'PASS_FLAG_REJECTION' if ok else 'FAIL','response':r,'expected':sys.argv[2]},indent=2)+'\\n')",
                "sys.exit(0 if ok else 1)"])
            cmd = [str(a.python), "-c", code, str(a.output), expected]
        report["probe_argv"] = cmd
        with (a.runtime/"client.log").open("w") as log:
            proc = subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=300)
        report["probe_exit"] = proc.returncode
        report["status"] = "COMPLETE_ISOLATED_RUN" if proc.returncode == 0 else "PROBE_FAIL"
    except Exception:
        report["error"] = traceback.format_exc()
    finally:
        if server is not None:
            if server.poll() is None:
                report["stop_requested"] = "SIGINT to owned process group after probe"
                os.killpg(server.pid, signal.SIGINT)
                try:
                    server.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    report["forced_stop"] = "SIGKILL after SIGINT timeout"
                    os.killpg(server.pid, signal.SIGKILL)
                    server.wait(timeout=10)
            report["server_exit"] = server.returncode
            if server.returncode != 130 or "forced_stop" in report:
                report["status"] = "SERVER_EXIT_FAIL"
        report["elapsed_wall_seconds"] = time.monotonic()-started
        report["logs"] = {}
        for name in ("server.log", "client.log", "readiness.log"):
            path = a.runtime/name
            if path.exists():
                report["logs"][name] = dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        (a.output.parent/("server-"+a.output.name+".json")).write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report))
    return 0 if report["status"] == "COMPLETE_ISOLATED_RUN" and "forced_stop" not in report else 1


if __name__ == "__main__":
    raise SystemExit(main())

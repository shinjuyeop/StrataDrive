"""Run the isolated training-image collector and restore the shared renderer."""

import argparse
import os
from pathlib import Path
import resource
import socket
import subprocess
import time

from m10_capture_fresh_quality import (
    DXC,
    PYTHON,
    ROOT,
    SERIES,
    TESTS,
    prepare_empty_world,
    read,
    restore_component,
    sha,
    shutdown,
    write,
)


def wait_for_client(client, server, timeout=1800):
    deadline = time.monotonic() + timeout
    try:
        while client.poll() is None:
            if server.poll() is not None:
                raise RuntimeError(
                    f"renderer exited during collection ({server.returncode})"
                )
            if time.monotonic() >= deadline:
                raise TimeoutError("training collection deadline")
            time.sleep(0.2)
        if client.returncode:
            raise subprocess.CalledProcessError(client.returncode, client.args)
    finally:
        if client.poll() is None:
            client.terminate()
            try:
                client.wait(timeout=3)
            except subprocess.TimeoutExpired:
                client.kill()
                client.wait()


def collect(output, parked=False, parking_map=None):
    files = read(SERIES / "pre-install.json")["files"]
    if any(sha(item["path"]) != item["sha256"] for item in files.values()):
        raise RuntimeError("shared renderer baseline mismatch")
    if (
        subprocess.run(
            ["pgrep", "-x", "UE4Editor"], stdout=subprocess.DEVNULL
        ).returncode
        == 0
    ):
        raise RuntimeError("renderer already active")
    for port in range(2400, 2403):
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("localhost", port))
    output.mkdir(parents=True, exist_ok=False)
    argv = [
        a.replace(
            "Town03_Opt", parking_map or ("Town05_Opt" if parked else "Town04_Opt")
        ).replace("rpc-port=2300", "rpc-port=2400")
        for a in read(SERIES / "preparation-argv.json")["renderer"]
    ]
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
    dxc = read(DXC / "manifest.json")

    def install(action):
        return subprocess.run(
            [
                "python3",
                ROOT / "tools/carla/m7_nodrive/build_dxc_lifetime.py",
                "--engine",
                Path(argv[0]).parents[3],
                "--output",
                DXC,
                "--" + action,
            ]
        ).returncode

    ini = Path(files["ini"]["path"])
    original = ini.read_bytes()
    outcome = {"status": "FAIL"}
    try:
        if (
            install("install")
            or sha(files["dxcompiler"]["path"]) != dxc["candidate_sha256"]
        ):
            raise RuntimeError("DXC installation")
        with (output / "server.log").open("x") as log:
            proc = subprocess.Popen(
                argv,
                stdout=log,
                stderr=subprocess.STDOUT,
                env=env,
                start_new_session=True,
                preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0)),
            )
            try:
                prepare_empty_world(PYTHON, 2400, output, env, proc, argv[2])
                with (output / "client.log").open("x") as client_log:
                    client = subprocess.Popen(
                        [
                            PYTHON,
                            TESTS / "occlusion_transfer_capture.py",
                            output / "dataset",
                            *(["--parked"] if parked else []),
                            *(["--parking-map", parking_map] if parking_map else []),
                        ],
                        env=env,
                        stdout=client_log,
                        stderr=subprocess.STDOUT,
                    )
                    wait_for_client(client, proc)
            finally:
                outcome["shutdown"] = shutdown(proc, output / "shutdown")
        if outcome["shutdown"]["server_exit"] != 130 or outcome["shutdown"].get(
            "forced_stop"
        ):
            raise RuntimeError("renderer shutdown")
        outcome["status"] = "PASS"
    finally:
        restore_component(
            files["dxcompiler"]["path"],
            files["dxcompiler"]["sha256"],
            dxc["candidate_sha256"],
            lambda: install("restore"),
        )
        if ini.read_bytes() != original:
            ini.write_bytes(original)
        outcome["restored"] = {key: sha(item["path"]) for key, item in files.items()}
        if any(outcome["restored"][k] != item["sha256"] for k, item in files.items()):
            raise RuntimeError("runtime restoration")
        write(output / "server.json", outcome)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("output", type=Path)
    p.add_argument("--parked", action="store_true")
    p.add_argument(
        "--parking-map", choices=("Town10HD_Opt", "Town02_Opt", "Town06_Opt")
    )
    args = p.parse_args()
    collect(args.output, args.parked, args.parking_map)

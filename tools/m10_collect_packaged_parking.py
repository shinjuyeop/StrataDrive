"""Capture an offline, map-disjoint parking dataset with the cooked CARLA renderer."""

import argparse
import hashlib
import os
from pathlib import Path
import resource
import socket
import subprocess

from m10_collect_occlusion_transfer import (
    PYTHON,
    ROOT,
    TESTS,
    read,
    sha,
    shutdown,
    wait_for_client,
    write,
)
from carla_readiness_v1 import wait_ready


def collect(output, town, port):
    import carla

    output = output.resolve()
    argv = [
        arg.replace("Town03_Opt", town).replace("rpc-port=2300", f"rpc-port={port}")
        for arg in read(
            ROOT
            / "docs/test-plan/evidence/m10_packaged_renderer_v1/preparation-argv.json"
        )["renderer"]
    ]
    project = Path(argv[0]).parents[2]
    if (
        subprocess.run(
            ["pgrep", "-f", "^" + argv[0]], stdout=subprocess.DEVNULL
        ).returncode
        == 0
    ):
        raise RuntimeError("packaged renderer already active")
    for number in range(port, port + 3):
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("localhost", number))
    ini = project / "Saved/Config/Linux/GameUserSettings.ini"
    original = ini.read_bytes() if ini.exists() else None
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
    output.mkdir(parents=True, exist_ok=False)
    outcome = dict(
        status="FAIL",
        renderer="CARLA cooked",
        argv=argv,
        executable_sha256=sha(argv[0]),
    )
    try:
        with (output / "server.log").open("x") as log:
            proc = subprocess.Popen(
                argv,
                cwd=project.parent,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0)),
            )
            try:
                outcome["readiness"] = wait_ready(
                    PYTHON, port, output / "readiness.jsonl", env
                )
                sdk = carla.Client("127.0.0.1", port)
                sdk.set_timeout(120)
                outcome["client_version"] = sdk.get_client_version()
                world = sdk.get_world()
                outcome["initial_map"] = world.get_map().name
                expected_paths = {f"Carla/Maps/{town}", argv[2]}
                if outcome["initial_map"] not in expected_paths:
                    world = sdk.load_world(town)
                road = world.get_map()
                if road.name not in expected_paths:
                    raise RuntimeError(f"wrong loaded map {road.name}")
                outcome.update(
                    map=road.name,
                    xodr_sha256=hashlib.sha256(
                        road.to_opendrive().encode()
                    ).hexdigest(),
                )
                with (output / "client.log").open("x") as client_log:
                    client = subprocess.Popen(
                        [
                            PYTHON,
                            TESTS / "occlusion_transfer_capture.py",
                            output / "dataset",
                            "--port",
                            str(port),
                            "--parking-map",
                            town,
                        ],
                        env=env,
                        stdout=client_log,
                        stderr=subprocess.STDOUT,
                    )
                    wait_for_client(client, proc)
                if world.get_settings().synchronous_mode:
                    raise RuntimeError("capture did not release synchronous mode")
            finally:
                outcome["shutdown"] = shutdown(
                    proc, output / "shutdown", diagnostics=False
                )
        if outcome["shutdown"]["server_exit"] not in (0, 130) or outcome[
            "shutdown"
        ].get("forced_stop"):
            raise RuntimeError("packaged renderer shutdown")
        outcome["status"] = "PASS"
    except Exception as exc:
        outcome["error"] = str(exc)
        raise
    finally:
        if original is None:
            ini.unlink(missing_ok=True)
        elif not ini.exists() or original != ini.read_bytes():
            ini.write_bytes(original)
        write(output / "server.json", outcome)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--parking-map",
        choices=("Town10HD_Opt", "Town02_Opt", "Town06_Opt"),
        required=True,
    )
    parser.add_argument("--port", type=int, default=2460)
    args = parser.parse_args()
    collect(args.output, args.parking_map, args.port)

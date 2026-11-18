"""Load the empty fixed Town04 renderer once so quality capture starts with built game assets."""

import argparse
import json
import os
from pathlib import Path
import resource
import socket
import subprocess

from m10_inspect_visual_pair import (
    prepare_empty_world,
    shutdown,
    restore_component,
    sha,
)

ROOT = Path(__file__).resolve().parents[1]
SERIES = ROOT / "docs/test-plan/evidence/m10_cuda_resize_v1"


def prepare(output):
    config = json.loads((SERIES / "preparation-argv.json").read_text())["renderer"]
    files = json.loads((SERIES / "pre-install.json").read_text())["files"]
    if any(sha(v["path"]) != v["sha256"] for v in files.values()):
        raise RuntimeError("quality preparation requires baseline runtime")
    if (
        subprocess.run(
            ["pgrep", "-x", "UE4Editor"], stdout=subprocess.DEVNULL
        ).returncode
        == 0
    ):
        raise RuntimeError("another server owns the shared runtime")
    port = 2400
    for n in range(port, port + 3):
        with socket.socket() as check:
            check.bind(("127.0.0.1", n))
    args = [
        s.replace("/Town03_Opt", "/Town04_Opt")
        if "/Maps/" in s
        else f"-carla-rpc-port={port}"
        if s.startswith("-carla-rpc-port=")
        else s
        for s in config
    ]
    python = ROOT / "build/m10-perception/cuda-venv/bin/python"
    dxc = ROOT / "build/m10-dxc-lifetime-v1"
    manifest = json.loads((dxc / "manifest.json").read_text())
    output.mkdir(parents=True, exist_ok=False)
    ini = Path(files["ini"]["path"])
    ini_backup = ini.read_bytes()
    record = dict(
        status="FAIL",
        scope="Empty renderer asset preparation only",
        images=0,
        model_calls=0,
        argv=args,
    )

    def component(action):
        with (output / (action + ".log")).open("x") as log:
            return subprocess.run(
                list(
                    map(
                        str,
                        [
                            "python3",
                            ROOT / "tools/carla/m7_nodrive/build_dxc_lifetime.py",
                            "--engine",
                            Path(args[0]).parents[3],
                            "--output",
                            dxc,
                            "--" + action,
                        ],
                    )
                ),
                stdout=log,
                stderr=subprocess.STDOUT,
            ).returncode

    try:
        if component("install"):
            raise RuntimeError("DXC installation failed")
        with (output / "server.log").open("x") as log:
            process = subprocess.Popen(
                args,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0)),
            )
            try:
                record["readiness"] = prepare_empty_world(
                    python, port, output, os.environ, process, args[2]
                )
            finally:
                record["shutdown"] = shutdown(process, output / "shutdown")
        if record["shutdown"]["server_exit"] != 130 or record["shutdown"].get(
            "forced_stop"
        ):
            raise RuntimeError("failed clean empty renderer shutdown")
        record["status"] = "PASS_EMPTY_PREPARATION"
    except Exception as error:
        record["error"] = repr(error)
    finally:
        try:
            record["dxc"] = restore_component(
                files["dxcompiler"]["path"],
                files["dxcompiler"]["sha256"],
                manifest["candidate_sha256"],
                lambda: component("restore"),
            )
            if ini.read_bytes() != ini_backup:
                ini.write_bytes(ini_backup)
            record["restored"] = {k: sha(v["path"]) for k, v in files.items()}
            if any(record["restored"][k] != v["sha256"] for k, v in files.items()):
                raise RuntimeError("runtime hash readback")
        except Exception as error:
            record.update(restoration_error=repr(error), status="FAIL")
        (output / "result.json").write_text(json.dumps(record, indent=2) + "\n")
    print(record["status"], record.get("error", ""), flush=True)
    return record["status"] == "PASS_EMPTY_PREPARATION"


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("output", type=Path)
    raise SystemExit(0 if prepare(p.parse_args().output) else 1)

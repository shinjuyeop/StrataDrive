"""Load the empty fixed Town04 renderer once so quality capture starts with built game assets."""

import argparse
import json
import os
from pathlib import Path
import resource
import socket
import secrets
import subprocess

from m10_inspect_visual_pair import (
    prepare_empty_world,
    shutdown,
    restore_component,
    sha,
)

ROOT = Path(__file__).resolve().parents[1]
SERIES = ROOT / "docs/test-plan/evidence/m10_cuda_resize_v1"


def prepare(output, module=None, plan=None):
    plan = (
        plan
        or ROOT
        / "docs/test-plan/evidence/m10_fresh_quality_2k_v1/plan/preparation.json"
    )
    map_name = json.loads(plan.read_text())["map"]
    if map_name not in (
        "Town04_Opt",
        "Town10HD_Opt",
        "Town02_Opt",
        "Town06_Opt",
        "Town07_Opt",
    ):
        raise ValueError("unsupported preparation map")
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
            check.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            check.bind(("127.0.0.1", n))
    args = [
        s.replace("/Town03_Opt", "/" + map_name)
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

    env = dict(os.environ)
    module_manifest = None
    if module:
        module_manifest = json.loads((module / "manifest.json").read_text())
        if (
            not (
                "quality_asset_barrier.hpp" in module_manifest["generated"]
                or module_manifest.get("barrier_sha256")
            )
            or module_manifest["original_sha256"] != files["module"]["sha256"]
            or sha(module / "libUE4Editor-Carla.so") != module_manifest["module_sha256"]
        ):
            raise ValueError("unverified quality preparation module")
        args.append("-StrataM10QualityAssetBarrier")
        if map_name != "Town04_Opt":
            args.append("-StrataM10QualityMap=" + map_name)
        if module_manifest.get("offline_game_asset_warmup"):
            args.append("-StrataM10AssetWarmNoTags")
        env["STRATADRIVE_M10_QUALITY_KEY"] = secrets.token_hex(32)
        record["module_sha256"] = module_manifest["module_sha256"]

    def handle_module(action):
        with (output / ("module-" + action + ".log")).open("x") as log:
            cmd = [
                "python3",
                ROOT / "tools/carla/m7_nodrive/build_endurance.py",
                "--engine",
                Path(args[0]).parents[3],
                "--source",
                Path(args[1]).parents[2],
                "--output",
                module,
                "--" + action,
            ]
            return subprocess.run(
                list(map(str, cmd)), stdout=log, stderr=subprocess.STDOUT
            ).returncode

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
        if module and handle_module("install"):
            raise RuntimeError("quality preparation module installation failed")
        if component("install"):
            raise RuntimeError("DXC installation failed")
        with (output / "server.log").open("x") as log:
            process = subprocess.Popen(
                args,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0)),
            )
            try:
                record["readiness"] = prepare_empty_world(
                    python, port, output, env, process, args[2]
                )
                if module:
                    with (output / "client.log").open("x") as client_log:
                        cmd = [
                            python,
                            ROOT
                            / "tests/integration/perception/prepare_quality_game_assets.py",
                            "--port",
                            str(port),
                            "--plan",
                            plan,
                            "--output",
                            output / "game-resources.json",
                        ]
                        rpc_timeout = 300 if map_name == "Town04_Opt" else 1500
                        cmd.extend(["--timeout", str(rpc_timeout)])
                        subprocess.run(
                            list(map(str, cmd)),
                            env=env,
                            stdout=client_log,
                            stderr=subprocess.STDOUT,
                            timeout=2 * rpc_timeout + 60,
                            check=True,
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
        restorations = [("dxcompiler", manifest["candidate_sha256"], component)]
        if module:
            restorations.append(
                ("module", module_manifest["module_sha256"], handle_module)
            )
        for name, candidate, manage in restorations:
            try:
                item = files[name]
                record[name] = restore_component(
                    item["path"], item["sha256"], candidate, lambda: manage("restore")
                )
            except Exception as error:
                record.setdefault("restoration_errors", []).append(f"{name}: {error!r}")
                record["status"] = "FAIL"
        try:
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
    p.add_argument("--module", type=Path)
    p.add_argument("--plan", type=Path)
    args = p.parse_args()
    raise SystemExit(0 if prepare(args.output, args.module, args.plan) else 1)

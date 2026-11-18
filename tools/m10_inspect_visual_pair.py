#!/usr/bin/env python3
"""Inspect a parked physical and rendering world with a read-only CARLA module."""

import argparse
import json
import os
from pathlib import Path
import resource
import secrets
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests/integration/perception"
sys.path.insert(0, str(TESTS))
from m10_parked_world_readiness import prepare_empty_world
from renderer_shutdown_v1 import shutdown
from runtime_restoration_v1 import sha, restore_component


def inspect_pair(module_dir, output, series):
    config = json.loads((series / "preparation-argv.json").read_text())
    original = json.loads((series / "pre-install.json").read_text())["files"]
    module = json.loads((module_dir / "manifest.json").read_text())
    engine = Path(config["owner"][0]).parents[3]
    source = Path(config["owner"][1]).parents[2]
    python = ROOT / "build/m10-perception/cuda-venv/bin/python"
    dxc_dir = ROOT / "build/m10-dxc-lifetime-v1"
    dxc = json.loads((dxc_dir / "manifest.json").read_text())
    if not all(sha(v["path"]) == v["sha256"] for v in original.values()):
        raise RuntimeError(
            "Shared runtime must match the recorded baseline before installation"
        )
    if (
        module["original_sha256"] != original["module"]["sha256"]
        or sha(module_dir / "libUE4Editor-Carla.so") != module["module_sha256"]
    ):
        raise ValueError("Inspection module identity differs from the build manifest")
    output.mkdir(parents=True, exist_ok=False)
    ini = Path(original["ini"]["path"])
    ini_backup = output / "original-GameUserSettings.ini"
    ini_backup.write_bytes(ini.read_bytes())
    probe = TESTS / "inspect_visual_scene_v1.py"
    record = dict(
        status="FAIL",
        stages={},
        restoration={},
        complete_scene_proof=False,
        native_started=False,
        module_sha256=module["module_sha256"],
        probe_sha256=sha(probe),
    )

    def save():
        (output / "result.json").write_text(json.dumps(record, indent=2) + "\n")

    def command(component, action):
        if component == "module":
            argv = [
                "python3",
                ROOT / "tools/carla/m7_nodrive/build_endurance.py",
                "--engine",
                engine,
                "--source",
                source,
                "--output",
                module_dir,
                "--" + action,
            ]
        else:
            argv = [
                "python3",
                ROOT / "tools/carla/m7_nodrive/build_dxc_lifetime.py",
                "--engine",
                engine,
                "--output",
                dxc_dir,
                "--" + action,
            ]
        with (output / f"{component}-{action}.log").open("x") as log:
            return subprocess.run(
                list(map(str, argv)), stdout=log, stderr=subprocess.STDOUT
            ).returncode

    def no_core_dump():
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    def run_role(role, port):
        stage = record["stages"][role] = {}
        directory = output / role
        directory.mkdir()
        env = dict(
            os.environ,
            STRATADRIVE_M10_VISUAL_INSPECT_KEY=secrets.token_hex(32),
            OMP_WAIT_POLICY="PASSIVE",
            PYTHONDONTWRITEBYTECODE="1",
        )
        env.pop("STRATADRIVE_M7_OWNER_KEY", None)
        args = [*config[role], "-StrataM10VisualInspect"]
        stage["argv"] = args
        with (directory / "server.log").open("x") as log:
            process = subprocess.Popen(
                args,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                preexec_fn=no_core_dump,
                start_new_session=True,
            )
            try:
                stage["readiness"] = prepare_empty_world(
                    python, port, directory, env, process, args[2]
                )
                invocation = [
                    python,
                    probe,
                    "--role",
                    role,
                    "--port",
                    str(port),
                    "--output",
                    directory / "inspect",
                ]
                if role == "renderer":
                    invocation += ["--catalog", output / "owner/inspect/result.json"]
                with (directory / "client.log").open("x") as client_log:
                    stage["client_exit"] = subprocess.run(
                        list(map(str, invocation)),
                        env=env,
                        stdout=client_log,
                        stderr=subprocess.STDOUT,
                        timeout=120,
                    ).returncode
            finally:
                stage["shutdown"] = shutdown(
                    process, directory / "shutdown", diagnostics=False
                )
                save()
        result = json.loads((directory / "inspect/result.json").read_text())
        if (
            stage["client_exit"]
            or stage["shutdown"]["server_exit"] != 130
            or stage["shutdown"].get("forced_stop")
            or result["errors"]
        ):
            raise RuntimeError(f"Inspect {role} result at {directory}")
        stage.update(frames=len(result["inspected"]), images=len(result["images"]))

    save()
    try:
        for name in ("module", "dxcompiler"):
            if command(name, "install"):
                raise RuntimeError(f"{name} installation failed")
        run_role("owner", 2200)
        run_role("renderer", 2300)
        record["status"] = "PASS_READ_ONLY_PAIR_INSPECTION"
    except Exception:
        record["error"] = traceback.format_exc()
    finally:
        for name, candidate in [
            ("dxcompiler", dxc["candidate_sha256"]),
            ("module", module["module_sha256"]),
        ]:
            try:
                item = original[name]
                record["restoration"][name] = restore_component(
                    item["path"],
                    item["sha256"],
                    candidate,
                    lambda: command(name, "restore"),
                )
            except Exception:
                record["restoration"][name] = dict(error=traceback.format_exc())
        ini.write_bytes(ini_backup.read_bytes())
        record["restored_hashes"] = {k: sha(v["path"]) for k, v in original.items()}
        if any(
            record["restored_hashes"][k] != v["sha256"] for k, v in original.items()
        ):
            record["status"] = "FAIL_RUNTIME_RESTORATION"
        save()
    print(
        json.dumps(
            {k: record[k] for k in ("status", "stages", "error") if k in record}
        ),
        flush=True,
    )
    return 0 if record["status"] == "PASS_READ_ONLY_PAIR_INSPECTION" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--series",
        type=Path,
        default=ROOT / "docs/test-plan/evidence/m10_cuda_resize_v1",
    )
    args = parser.parse_args()
    raise SystemExit(
        inspect_pair(
            args.module_dir.resolve(), args.output.resolve(), args.series.resolve()
        )
    )

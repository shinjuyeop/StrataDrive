"""Run an isolated prospective 2K quality capture and verify its original paired images."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import resource
import socket
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests/integration/perception"
sys.path.insert(0, str(TESTS))
from m10_parked_world_readiness import prepare_empty_world
from fresh_quality_2k_plan import validate_retained
from fresh_quality_2k_review import BASE, EXCLUSIONS, digest, read, review, write
from renderer_shutdown_v1 import shutdown
from runtime_restoration_v1 import restore_component, sha

SERIES = ROOT / "docs/test-plan/evidence/m10_cuda_resize_v1"
PYTHON = ROOT / "build/m10-perception/cuda-venv/bin/python"
PROBE = TESTS / "fresh_quality_2k_capture.py"
DXC = ROOT / "build/m10-dxc-lifetime-v1"
MODEL = ROOT / "build/m10-resolution-v2/models/dfine-960.onnx"
BASELINE = ROOT / "build/m10-perception/yolox.onnx"


def sources():
    paths = [
        BASE / "README.md",
        *(BASE / "plan").glob("*.json"),
        *EXCLUSIONS,
        ROOT / "profiles/perception-quality-protocol-v9.json",
        ROOT / "profiles/perception-source-compare-v1.json",
        ROOT / "build/m10-resolution-v2/models.json",
        MODEL,
        BASELINE,
        Path(read(SERIES / "component/release-manifest.json")["library"]["path"]),
        PROBE,
        Path(__file__),
        ROOT / "tools/m10_parked_world_readiness.py",
        TESTS / "fresh_quality_2k_review.py",
        TESTS / "fresh_quality_2k_plan.py",
        TESTS / "fresh_quality_2k_score.py",
        TESTS / "prepare_road_v9.py",
        TESTS / "prepare_quality_v9.py",
        TESTS / "camera_resolution_v1_common.py",
        TESTS / "quality_benchmark.py",
        TESTS / "quality_benchmark_v2.py",
        TESTS / "quality_benchmark_v3.py",
        TESTS / "run_resolution_v2.py",
        TESTS / "carla_camera_resolution_v1.py",
        TESTS / "quality_plan_v4.py",
        TESTS / "quality_sites_v9.py",
        TESTS / "quality_geometry_v4.py",
        TESTS / "quality_staging_v5.py",
        TESTS / "evaluate.py",
        SERIES / "pre-install.json",
        SERIES / "preparation-argv.json",
        ROOT / "profiles/perception-quality-template-v9.json",
        ROOT / "profiles/perception-class-calibration-candidates-v1.json",
        ROOT / "build/m10-source-compare-v1/native/libstrata_resize_2k_v1.so",
        DXC / "manifest.json",
        *sorted((ROOT / "physical_ai/perception").glob("*.py")),
    ]
    return {str(p.resolve().relative_to(ROOT)): sha(p) for p in sorted(set(paths))}


def freeze():
    validate_retained(BASE / "plan")
    result = dict(
        schema="m10-fresh-2k-quality-freeze-v1",
        files=sources(),
        created_utc=datetime.now(timezone.utc).isoformat(),
    )
    if (
        result["files"][str(MODEL.relative_to(ROOT))]
        != "b865ac0f2597afd6fcb9e887ed7738e98e7690ecb4d5cebf42724a3e6b384884"
        or result["files"][str(BASELINE.relative_to(ROOT))]
        != "c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063"
    ):
        raise ValueError("published candidate and baseline weights required")
    write(BASE / "freeze.json", result)


def allow(phase, partition):
    if read(BASE / "freeze.json")["files"] != sources():
        raise ValueError("fixed capture, scoring and model identities changed")
    if phase == "evaluation":
        # A clean model-free preparation for both partitions precedes evaluation.
        for part in ("development", "holdout"):
            if not any(
                read(p)["status"] == "PASS"
                for p in (BASE / "runs").glob(
                    "preparation-" + part + "-*/visibility.json"
                )
            ):
                raise ValueError(f"{part} has no passing model-free preparation")
    if phase == "evaluation" and partition == "holdout":
        from fresh_quality_2k_score import verify_nomination

        verify_nomination()


def run(phase, partition, attempt, port):
    allow(phase, partition)
    if (
        phase == "evaluation"
        and partition == "holdout"
        and any((BASE / "runs").glob("evaluation-holdout-*/dataset/rgb/*.bgra.z"))
    ):
        raise ValueError("holdout evaluation already acquired; preserve that attempt")
    output = BASE / "runs" / f"{phase}-{partition}-{attempt:02d}"
    config = read(SERIES / "preparation-argv.json")["renderer"]
    files = read(SERIES / "pre-install.json")["files"]
    if any(sha(o["path"]) != o["sha256"] for o in files.values()):
        raise RuntimeError("shared runtime differs from baseline")
    if (
        subprocess.run(
            ["pgrep", "-x", "UE4Editor"], stdout=subprocess.DEVNULL
        ).returncode
        == 0
    ):
        raise RuntimeError("another CARLA server owns the runtime")
    for candidate_port in range(port, port + 3):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", candidate_port))
    output.mkdir(parents=True, exist_ok=False)
    plan = BASE / "plan" / (phase + ".json")
    args = [
        s.replace("/Town03_Opt", "/Town04_Opt")
        if "/Maps/" in s
        else f"-carla-rpc-port={port}"
        if s.startswith("-carla-rpc-port=")
        else s
        for s in config
    ]
    client = list(
        map(
            str,
            [
                PYTHON,
                PROBE,
                "--port",
                port,
                "--plan",
                plan,
                "--output",
                output / "dataset",
                "--partition",
                partition,
            ],
        )
    )
    record = dict(
        status="FAIL",
        case=output.name,
        phase=phase,
        partition=partition,
        plan_sha256=digest(plan),
        freeze_sha256=digest(BASE / "freeze.json"),
        command=args,
        client=client,
        selection_sha256=digest(BASE / "nomination.json")
        if phase == "evaluation" and partition == "holdout"
        else None,
        errors=[],
        started_utc=datetime.now(timezone.utc).isoformat(),
    )
    ini = Path(files["ini"]["path"])
    backup = ini.read_bytes()
    engine = Path(args[0]).parents[3]
    dxc = read(DXC / "manifest.json")

    def install(action):
        with (output / ("dxc-" + action + ".log")).open("x") as log:
            return subprocess.run(
                list(
                    map(
                        str,
                        [
                            "python3",
                            ROOT / "tools/carla/m7_nodrive/build_dxc_lifetime.py",
                            "--engine",
                            engine,
                            "--output",
                            DXC,
                            "--" + action,
                        ],
                    )
                ),
                stdout=log,
                stderr=subprocess.STDOUT,
            ).returncode

    def no_core():
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    try:
        if (
            install("install")
            or sha(files["dxcompiler"]["path"]) != dxc["candidate_sha256"]
        ):
            raise RuntimeError("DXC lifecycle candidate identity")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        with (output / "server.log").open("x") as server_log:
            process = subprocess.Popen(
                args,
                stdout=server_log,
                stderr=subprocess.STDOUT,
                env=env,
                start_new_session=True,
                preexec_fn=no_core,
            )
            try:
                record["readiness"] = prepare_empty_world(
                    PYTHON, port, output, env, process, args[2]
                )
                with (output / "client.log").open("x") as log:
                    record["client_exit"] = subprocess.run(
                        client,
                        env=env,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        timeout=900,
                    ).returncode
            finally:
                record["shutdown"] = shutdown(process, output / "shutdown")
        if (
            record["client_exit"]
            or record["shutdown"]["server_exit"] != 130
            or record["shutdown"].get("forced_stop")
        ):
            raise RuntimeError("capture or server shutdown failed")
        record["status"] = "PASS_CAPTURE"
    except Exception:
        record["errors"].append(traceback.format_exc())
    finally:
        try:
            record["restoration"] = restore_component(
                files["dxcompiler"]["path"],
                files["dxcompiler"]["sha256"],
                dxc["candidate_sha256"],
                lambda: install("restore"),
            )
            if ini.read_bytes() != backup:
                ini.write_bytes(backup)
            record["restored"] = {k: sha(o["path"]) for k, o in files.items()}
            if any(record["restored"][k] != v["sha256"] for k, v in files.items()):
                raise RuntimeError("original runtime hash readback")
        except Exception:
            record["status"] = "FAIL_RESTORATION"
            record["errors"].append(traceback.format_exc())
        write(output / "server.json", record)
    if record["status"] != "PASS_CAPTURE":
        raise RuntimeError(f"inspect {output}/server.json")
    result = review(output)
    print(
        json.dumps(
            dict(case=output.name, status=result["status"], gates=result["gates"])
        ),
        flush=True,
    )
    return result["status"] == "PASS"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--phase", choices=("preparation", "evaluation"))
    parser.add_argument("--partition", choices=("development", "holdout"))
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument("--port", type=int, default=2400)
    a = parser.parse_args()
    if a.freeze:
        freeze()
    else:
        if a.phase is None or a.partition is None or a.attempt < 1:
            parser.error("case needs phase, partition and positive attempt")
        raise SystemExit(0 if run(a.phase, a.partition, a.attempt, a.port) else 1)

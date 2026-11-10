#!/usr/bin/env python3
"""Native camera upstream probes, fixed model replay and camera-only comparison."""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sys
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import numpy as np
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import read_json
from physical_ai.perception.camera_resolution_v1 import (
    SCALES,
    NativeDataset,
    NativeDetector,
    prepare,
    canonical,
    decode,
)
from physical_ai.perception.run import distribution
from camera_resolution_v1_common import (
    ROOT,
    check_freeze,
    check_selection,
    save_derived,
    require,
    write_new,
)
from check_model_screen_v1 import compare_top300, compare_detections
from run_resolution_v2 import quality, json_detections

MODELS = ROOT / "build/m10-resolution-v2/models.json"
MODEL = ROOT / "build/m10-resolution-v2/models/dfine-960.onnx"


def reference(base, run):
    import torch
    import torchvision.transforms as T
    from PIL import Image
    from export_model_screen_v2 import model_from_checkpoint
    from export_resolution_v1 import configure, state_hash

    check_freeze(base / "freeze.json")
    data = NativeDataset(run / "dataset/rgb.json")
    scale = data.scale
    require(
        read_json(run / "dataset/acceptance.json")["status"] == "PASS"
        and data.manifest["phase"] == "pilot",
        "accepted pilot before model",
    )
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    model, strict = model_from_checkpoint(
        "dfine-m", ROOT / "build/m10-model-screen-v2/upstream/dfine-m.pth"
    )
    configure(model, 960)
    state = state_hash(model, True)
    out = base / f"reference-{scale}"
    out.mkdir(exist_ok=False)
    rows = []
    for n, (source, frame) in enumerate(data.frames()):
        rgb = np.frombuffer(frame.rgb, np.uint8).reshape(frame.height, frame.width, 3)
        tensor = T.Compose([T.Resize((960, 960)), T.ToTensor()])(Image.fromarray(rgb))[
            None
        ]
        np.testing.assert_array_equal(tensor.numpy(), prepare(frame)["images"])
        with torch.inference_mode():
            raw = dict(
                zip(
                    ("labels", "boxes", "scores"),
                    [
                        t.numpy()
                        for t in model(
                            tensor, torch.tensor([[frame.width, frame.height]])
                        )
                    ],
                )
            )
        path = out / f"{n}.npz"
        np.savez_compressed(path, **raw)
        rows.append(
            dict(
                probe=n,
                rgb_sha256=source["rgb_sha256"],
                raw_sha256=sha256_file(path),
                tensor_sha256=hashlib.sha256(tensor.numpy().tobytes()).hexdigest(),
            )
        )
    require(
        state_hash(model, True) == state and len(rows) == 3,
        "unchanged state/probe denominator",
    )
    result = dict(
        status="PASS",
        scale=scale,
        rows=rows,
        strict_state_load=strict["strict_state_load"],
        nongeometric_state_sha256=state,
        rgb_manifest_sha256=sha256_file(data.path),
    )
    write_new(base / f"reference-{scale}.json", result)
    return result


def numeric(base, run):
    check_freeze(base / "freeze.json")
    data = NativeDataset(run / "dataset/rgb.json")
    scale = data.scale
    ref = read_json(base / f"reference-{scale}.json")
    require(ref["rgb_manifest_sha256"] == sha256_file(data.path), "native probe data")
    report = dict(
        schema="m10-camera-numeric-v1",
        status="PASS",
        started_utc=datetime.now(timezone.utc).isoformat(),
        scale=scale,
        rows=[],
        box_atol_canonical=0.1,
        score_atol=0.0001,
        cold_calls_excluded=0,
        rgb_manifest_sha256=sha256_file(data.path),
        freeze_sha256=sha256_file(base / "freeze.json"),
    )
    try:
        cpu, cuda = [
            NativeDetector(960, MODEL, MODELS, execution)
            for execution in ("cpu", "cuda")
        ]
    except Exception:
        report.update(
            status="FAIL",
            error=traceback.format_exc(),
            completed_utc=datetime.now(timezone.utc).isoformat(),
        )
        write_new(base / f"numeric-{scale}.json", report)
        return report
    raw_dir = base / f"numeric-{scale}-raw"
    raw_dir.mkdir(exist_ok=False)
    for n, (source, frame) in enumerate(data.frames()):
        row = dict(probe=n, rgb_sha256=source["rgb_sha256"], passed=False)
        try:
            feed = cpu.prepare(frame)
            require(
                hashlib.sha256(feed["images"].tobytes()).hexdigest()
                == ref["rows"][n]["tensor_sha256"],
                "independent native input tensor",
            )
            path = base / f"reference-{scale}/{n}.npz"
            require(
                sha256_file(path) == ref["rows"][n]["raw_sha256"],
                "native reference SHA",
            )
            with np.load(path) as arrays:
                expected = dict(arrays)
            values = [expected, cpu.raw(feed), cuda.raw(feed)]
            deltas = []
            row["raw_files"] = []
            for label, raw in zip(("reference", "cpu", "cuda"), values):
                cached = raw_dir / f"{n}-{label}.npz"
                np.savez_compressed(cached, **raw)
                row["raw_files"].append(
                    dict(file=str(cached.relative_to(base)), sha256=sha256_file(cached))
                )
            for a, b in zip(values, values[1:]):
                deltas.append(compare_top300(canonical(a, scale), canonical(b, scale)))
                compare_detections(
                    [asdict(d) for d in decode(a, scale)],
                    [asdict(d) for d in decode(b, scale)],
                )
            row.update(
                passed=True,
                deltas=deltas,
                providers=cuda.session.get_providers(),
                provider_options=cuda.session.get_provider_options(),
            )
        except Exception:
            row["error"] = traceback.format_exc()
            report["status"] = "FAIL"
        report["rows"].append(row)
    report["completed_utc"] = datetime.now(timezone.utc).isoformat()
    write_new(base / f"numeric-{scale}.json", report)
    return report


def select(base):
    check_freeze(base / "freeze.json")
    pilots = {}
    passed = []
    for scale in SCALES:
        runs = read_json(base / "pilot-runs.json")
        run = base / runs[str(scale)]
        acceptance = read_json(run / "dataset/acceptance.json")
        n = read_json(base / f"numeric-{scale}.json")
        if (
            acceptance["status"] == n["status"] == "PASS"
            and len(n["rows"]) == 3
            and all(r["passed"] for r in n["rows"])
        ):
            passed.append(scale)
        pilots[str(scale)] = dict(
            run=run.name,
            server_sha256=sha256_file(run / "server.json"),
            acceptance_sha256=sha256_file(run / "dataset/acceptance.json"),
            numeric_sha256=sha256_file(base / f"numeric-{scale}.json"),
        )
    require(1 in passed, "baseline640 numeric/technical gate required")
    result = dict(
        schema="m10-camera-source-selection-v1",
        created_utc=datetime.now(timezone.utc).isoformat(),
        pilots=pilots,
        selected_scale=max(passed),
        criterion="largest technical passing source; quality unseen",
        runtime_promotion=False,
    )
    write_new(base / "selection.json", result)
    check_selection(base)
    return result


def infer(base, run):
    check_selection(base)
    data = NativeDataset(run / "dataset/rgb.json")
    scale = data.scale
    require(
        data.manifest["phase"] == "comparison"
        and read_json(run / "dataset/acceptance.json")["status"] == "PASS",
        "accepted comparison",
    )
    out = base / f"comparison-{scale}-model"
    out.mkdir(exist_ok=False)
    (out / "raw").mkdir()
    report = dict(
        schema="m10-camera-model-run-v1",
        scale=scale,
        started_utc=datetime.now(timezone.utc).isoformat(),
        status="FAIL",
        rows=[],
        attempted=0,
        valid=0,
        admitted=0,
        errors=0,
        dataset_sha256=sha256_file(data.path),
        freeze_sha256=sha256_file(base / "freeze.json"),
        selection_sha256=sha256_file(base / "selection.json"),
        cold_calls_excluded=0,
    )
    start = time.monotonic_ns()
    model = NativeDetector(960, MODEL, MODELS)
    report["initialization_wall_ns"] = time.monotonic_ns() - start
    report["providers"] = model.session.get_providers()
    report["provider_options"] = model.session.get_provider_options()
    report["cpu_node_fallback_disabled"] = True
    for source, frame in data.frames():
        row = {k: source[k] for k in ("scene", "frame", "source_ns", "rgb_sha256")}
        row.update(valid=False, admitted=False, detections=None)
        report["attempted"] += 1
        begin = time.monotonic_ns()
        try:
            feed = model.prepare(frame)
            prepared = time.monotonic_ns()
            raw = model.raw(feed)
            inferred = time.monotonic_ns()
            detections = decode(raw, scale)
            done = time.monotonic_ns()
            path = out / "raw" / f"{len(report['rows']):04d}.npz"
            np.savez_compressed(path, **raw)
            row.update(
                valid=True,
                admitted=done - begin < 100_000_000,
                detections=json_detections(detections),
                elapsed_wall_ns=done - begin,
                preprocess_ns=prepared - begin,
                inference_ns=inferred - prepared,
                postprocess_ns=done - inferred,
                raw=str(path.relative_to(out)),
                raw_sha256=sha256_file(path),
            )
            report["valid"] += 1
            report["admitted"] += int(row["admitted"])
        except Exception:
            row.update(
                error=traceback.format_exc(),
                elapsed_wall_ns=time.monotonic_ns() - begin,
            )
            report["errors"] += 1
        report["rows"].append(row)
    report.update(
        status="PASS" if report["attempted"] == report["valid"] == 81 else "FAIL",
        finished_utc=datetime.now(timezone.utc).isoformat(),
        latency=distribution([r["elapsed_wall_ns"] for r in report["rows"]]),
    )
    write_new(out / "run.json", report)
    return report


def score(base, run):
    check_selection(base)
    data = NativeDataset(run / "dataset/rgb.json")
    scale = data.scale
    list_sources = [s for s, _ in data.frames()]
    gt = read_json(run / "dataset/evaluation-only-gt.json")
    meta = read_json(run / "dataset/benchmark.json")
    result = read_json(base / f"comparison-{scale}-model/run.json")
    require(
        result["dataset_sha256"] == sha256_file(data.path)
        and result["freeze_sha256"] == sha256_file(base / "freeze.json")
        and result["selection_sha256"] == sha256_file(base / "selection.json")
        and result["providers"][0] == "CUDAExecutionProvider"
        and result["cpu_node_fallback_disabled"]
        and result["cold_calls_excluded"] == 0,
        "model provenance",
    )
    require(
        len(result["rows"])
        == len(list_sources)
        == len(gt["frames"])
        == len(meta["scenes"])
        == 81,
        "full comparison denominator",
    )
    rows = []
    valid = admitted = 0
    for source, truth, scene, row in zip(
        list_sources, gt["frames"], meta["scenes"], result["rows"]
    ):
        require(
            all(
                row[k] == source[k]
                for k in ("scene", "frame", "source_ns", "rgb_sha256")
            )
            and row["scene"] == truth["scene"] == scene["scene"],
            "comparison row identity",
        )
        raw = None
        pred = []
        if row["valid"]:
            path = base / f"comparison-{scale}-model" / row["raw"]
            require(sha256_file(path) == row["raw_sha256"], "native model raw hash")
            with np.load(path) as arrays:
                raw = dict(arrays)
            pred = json_detections(decode(raw, scale))
            require(
                pred == row["detections"]
                and row["admitted"] == (row["elapsed_wall_ns"] < 100_000_000),
                "raw decode/deadline",
            )
            valid += 1
            admitted += int(row["admitted"])
        else:
            require(
                row["detections"] is None and row.get("error") and not row["admitted"],
                "errors are not empty success",
            )
        rows.append((scene, truth, pred, row["valid"], row["admitted"], None))
    require(
        (valid, admitted, 81 - valid)
        == (result["valid"], result["admitted"], result["errors"]),
        "model denominator",
    )
    return dict(
        schema="m10-camera-source-score-v1",
        scale=scale,
        source_dimensions=[640 * scale, 384 * scale],
        run_sha256=sha256_file(base / f"comparison-{scale}-model/run.json"),
        runtime_promotion=False,
        **quality(rows),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "command",
        choices=("prepare", "reference", "numeric", "select", "infer", "score"),
    )
    p.add_argument("base", type=Path)
    p.add_argument("--run", type=Path)
    a = p.parse_args()
    if a.command == "prepare":
        r = save_derived(a.run / "dataset/capture.json", a.base / "freeze.json")
    elif a.command == "reference":
        r = reference(a.base, a.run)
    elif a.command == "numeric":
        r = numeric(a.base, a.run)
    elif a.command == "select":
        r = select(a.base)
    elif a.command == "infer":
        r = infer(a.base, a.run)
    else:
        r = score(a.base, a.run)
        write_new(a.base / f"comparison-{r['scale']}-score.json", r)
    print(
        {
            k: r.get(k)
            for k in (
                "status",
                "scale",
                "frames",
                "micro",
                "absolute_quality",
                "selected_scale",
            )
        }
    )

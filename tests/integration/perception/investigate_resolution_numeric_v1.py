#!/usr/bin/env python3
"""Bounded native-cache and ORT-profile investigation; never consumes quality GT."""

import argparse
from datetime import datetime, timezone
from dataclasses import asdict
import hashlib
from itertools import islice
from pathlib import Path
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import numpy as np
from physical_ai.perception.contract import execution_profile, sha256_file
from physical_ai.perception.dataset import RgbDataset, read_json
from physical_ai.perception.resolution_v1 import ResolutionDetector, SIZES, decode
from resolution_v1_common import ROOT, PROBES, check_freeze, models, require, write_new
from check_model_screen_v1 import compare_top300, compare_detections


def freeze(base):
    check_freeze(base / "freeze.json")
    names = [
        "docs/test-plan/perception-resolution-v1-numeric-annex.md",
        "tests/integration/perception/investigate_resolution_numeric_v1.py",
    ]
    paths = [
        base / "freeze.json",
        base / "models.json",
        base / "numeric.json",
        base / "numeric-diagnostic.json",
        ROOT / "build/m10-quality-v9/numeric-reference-01/reference.json",
    ]
    paths += [
        ROOT / f"build/m10-quality-v9/numeric-reference-01/dfine-{n}.npz"
        for n in range(3)
    ]
    result = dict(
        schema="m10-resolution-numeric-annex-freeze-v1",
        created_utc=datetime.now(timezone.utc).isoformat(),
        sources={n: sha256_file(ROOT / n) for n in names},
        inputs={str(p.relative_to(ROOT)): sha256_file(p) for p in paths},
        profiles=["ORT_DISABLE_ALL", "ORT_ENABLE_BASIC"],
        holdout_access=False,
        quality_inference=False,
        box_atol=0.1,
        score_atol=0.0001,
    )
    write_new(base / "numeric-annex-freeze.json", result)
    return result


def check_annex(base):
    check_freeze(base / "freeze.json")
    f = read_json(base / "numeric-annex-freeze.json")
    for n, h in {**f["sources"], **f["inputs"]}.items():
        require(sha256_file(ROOT / n) == h, "numeric annex frozen input/source")
    return f


def reference(base, checkpoint):
    import torch
    from export_model_screen_v2 import model_from_checkpoint
    from export_resolution_v1 import state_hash, configure
    from copy import deepcopy

    check_annex(base)
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    model, strict = model_from_checkpoint("dfine-m", checkpoint)
    before = state_hash(model, True)
    saved = model.detector.decoder.anchors.detach().numpy().copy()
    regenerated = deepcopy(model)
    configure(regenerated, 640)
    fresh = regenerated.detector.decoder.anchors.detach().numpy()
    valid = np.isfinite(saved) & np.isfinite(fresh)
    checkpoint_state = torch.load(checkpoint, map_location="cpu", weights_only=True)[
        "model"
    ]
    report = dict(
        schema="m10-resolution-cached640-reference-v1",
        strict_state_load=strict["strict_state_load"],
        nongeometric_state_sha256=before,
        checkpoint_anchor_dtype=str(checkpoint_state["decoder.anchors"].dtype),
        cached_anchor_shape=list(saved.shape),
        cached_anchor_sha256=hashlib.sha256(saved.tobytes()).hexdigest(),
        regenerated_anchor_sha256=hashlib.sha256(fresh.tobytes()).hexdigest(),
        anchor_max_abs=float(np.max(np.abs(saved[valid] - fresh[valid]))),
        rows=[],
    )
    out = base / "cached640-reference"
    out.mkdir(exist_ok=False)
    for n, (source, frame) in enumerate(islice(RgbDataset(PROBES).frames(), 3)):
        feed = ResolutionDetector.prepare(type("Probe", (), dict(size=640))(), frame)
        with torch.inference_mode():
            raw = dict(
                zip(
                    ("labels", "boxes", "scores"),
                    [
                        t.numpy()
                        for t in model(
                            torch.from_numpy(feed["images"]),
                            torch.from_numpy(feed["orig_target_sizes"]),
                        )
                    ],
                )
            )
        with np.load(
            ROOT / f"build/m10-quality-v9/numeric-reference-01/dfine-{n}.npz"
        ) as arrays:
            old = dict(arrays)
        delta = compare_top300(old, raw)
        path = out / f"640-{n}.npz"
        np.savez_compressed(path, **raw)
        report["rows"].append(
            dict(
                probe=n,
                rgb_sha256=source["rgb_sha256"],
                sha256=sha256_file(path),
                old_v9_delta=delta,
            )
        )
    require(state_hash(model, True) == before, "cached reference state immutable")
    write_new(base / "cached640-reference.json", report)
    return report


def session(size, path, execution, profile):
    import onnxruntime as ort

    settings = execution_profile(execution)
    require(ort.__version__ == "1.23.2", "pinned ORT")
    opts = ort.SessionOptions()
    opts.intra_op_num_threads, opts.inter_op_num_threads = 4, 1
    opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    opts.graph_optimization_level = getattr(ort.GraphOptimizationLevel, profile)
    providers = ["CPUExecutionProvider"]
    if settings is not None:
        ort.preload_dlls(directory="")
        opts.add_session_config_entry("session.disable_cpu_ep_fallback", "1")
        providers = [
            (
                "CUDAExecutionProvider",
                {
                    k: settings[k]
                    for k in (
                        "device_id",
                        "use_tf32",
                        "cudnn_conv_algo_search",
                        "gpu_mem_limit",
                    )
                },
            )
        ]
    result = ort.InferenceSession(str(path), sess_options=opts, providers=providers)
    result.disable_fallback()
    if settings is not None:
        require(
            result.get_providers()[0] == "CUDAExecutionProvider"
            and all(
                result.get_provider_options()["CUDAExecutionProvider"].get(k)
                == settings[k]
                for k in (
                    "device_id",
                    "use_tf32",
                    "cudnn_conv_algo_search",
                    "gpu_mem_limit",
                )
            ),
            "exact CUDA settings",
        )
    else:
        require(result.get_providers() == ["CPUExecutionProvider"], "exact CPU session")
    return result


def check(base):
    annex = check_annex(base)
    _, manifest = models(base)
    control = read_json(base / "cached640-reference.json")
    probes = list(islice(RgbDataset(PROBES).frames(), 3))
    report = dict(
        schema="m10-resolution-numeric-investigation-v1",
        started_utc=datetime.now(timezone.utc).isoformat(),
        annex_sha256=sha256_file(base / "numeric-annex-freeze.json"),
        profiles=[],
        selected_profile=None,
        box_atol=0.1,
        score_atol=0.0001,
        quality_inference=False,
    )
    for profile in annex["profiles"]:
        result = dict(profile=profile, status="PASS", rows=[])
        for size in SIZES:
            cpu, cuda = [
                session(
                    size,
                    base / manifest["models"][str(size)]["path"],
                    execution,
                    profile,
                )
                for execution in ("cpu", "cuda")
            ]
            for n, (source, frame) in enumerate(probes):
                row = dict(
                    size=size, probe=n, rgb_sha256=source["rgb_sha256"], passed=False
                )
                try:
                    reference = (
                        base
                        / ("cached640-reference" if size == 640 else "reference")
                        / f"{size}-{n}.npz"
                    )
                    if size == 640:
                        require(
                            sha256_file(reference) == control["rows"][n]["sha256"],
                            "cached native reference",
                        )
                    with np.load(reference) as arrays:
                        raw = dict(arrays)
                    feed = ResolutionDetector.prepare(
                        type("Probe", (), dict(size=size))(), frame
                    )
                    values = [raw] + [
                        dict(zip(("labels", "boxes", "scores"), s.run(None, feed)))
                        for s in (cpu, cuda)
                    ]
                    row["deltas"] = []
                    for a, b in zip(values, values[1:]):
                        row["deltas"].append(compare_top300(a, b))
                        compare_detections(
                            [asdict(d) for d in decode(a)],
                            [asdict(d) for d in decode(b)],
                        )
                    row.update(passed=True, providers=cuda.get_providers())
                except Exception:
                    result["status"] = "FAIL"
                    row["error"] = traceback.format_exc()
                result["rows"].append(row)
            del cpu, cuda
        report["profiles"].append(result)
        if result["status"] == "PASS" and report["selected_profile"] is None:
            report["selected_profile"] = profile
    report["finished_utc"] = datetime.now(timezone.utc).isoformat()
    write_new(base / "numeric-investigation.json", report)
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("freeze", "reference", "check"))
    p.add_argument("base", type=Path)
    p.add_argument("--checkpoint", type=Path)
    a = p.parse_args()
    a.base = a.base.resolve()
    r = (
        freeze(a.base)
        if a.command == "freeze"
        else reference(a.base, a.checkpoint)
        if a.command == "reference"
        else check(a.base)
    )
    print(a.command, r.get("selected_profile", r.get("anchor_max_abs", "PASS")))

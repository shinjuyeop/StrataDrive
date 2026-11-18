"""Replay the exported RGB-only graph on original development pixels using CUDA ONNX Runtime."""

import argparse
from collections import Counter
from pathlib import Path
import hashlib

import numpy as np
import onnxruntime as ort
from PIL import Image
from physical_ai.perception.camera_resolution_v1 import unpack
from physical_ai.perception.contract import execution_profile
from physical_ai.perception.parking_candidate import detections
from fresh_quality_2k_review import BASE, digest, read, rgb_bytes, write
from evaluate import overlap
from quality_benchmark import relative
from quality_benchmark_v3 import measure
from run_resolution_v2 import quality


def load_session(bundle):
    path = bundle / "parking-dfine-960.onnx"
    spec = read(bundle / "manifest.json")
    if digest(path) != spec["model_sha256"]:
        raise ValueError("export identity")
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    options.add_session_config_entry("session.disable_cpu_ep_fallback", "1")
    settings = execution_profile("cuda")
    ort.preload_dlls(directory="")
    cuda = {
        k: settings[k]
        for k in ("device_id", "use_tf32", "cudnn_conv_algo_search", "gpu_mem_limit")
    }
    session = ort.InferenceSession(
        str(path), options, providers=[("CUDAExecutionProvider", cuda)]
    )
    session.disable_fallback()
    if session.get_providers()[0] != "CUDAExecutionProvider":
        raise ValueError("CUDA provider required")
    return session, spec


def run(root, output, bundle=None):
    output.mkdir(exist_ok=False)
    bundle = bundle or root / "export"
    session, spec = load_session(bundle)
    run_dir = BASE / "runs/evaluation-development-01"
    inp = read(run_dir / "images.json")["frames"]
    scenes = read(run_dir / "benchmark.json")["scenes"]
    gt = read(run_dir / "evaluation-only-gt.json")["frames"]
    reference = read(root / "occluded-shrink/development-predictions.json")
    policy = spec.get(
        "bus_policy", {"source": "original", "confidence": 0.5, "support": 0.0}
    )
    if spec.get("preserve_noncar") or (
        spec.get("original_bus") and policy["source"] == "original"
    ):
        preserved = {5} if spec.get("original_bus") else {0, 1, 3, 5, 7}
        prior = BASE.parents[3] / "build/m10-occlusion-transfer-v1"
        original = read(prior / "reference/development-predictions.json")
        adapted = read(prior / "car-score-01/development-predictions.json")
        for i, (ref, old, source) in enumerate(
            zip(reference, original, adapted, strict=True)
        ):
            if any(
                (ref["scene"], ref["rgb_sha256"]) != (r["scene"], r["rgb_sha256"])
                for r in (old, source)
            ):
                raise ValueError("reference decoder image mismatch")
            keep = [d for d in old["detections"] if d["class_id"] in preserved]
            if spec.get("original_bus"):
                path = prior / "car-score-01/queries" / f"{i:03d}.npz"
                if digest(path) != source["queries_sha256"]:
                    raise ValueError("adapted reference proposals changed")
                with np.load(path, allow_pickle=False) as query:
                    proposals = [
                        (int(k), b, float(sc))
                        for k, b, sc in zip(
                            query["labels"][0],
                            query["boxes"][0],
                            query["scores"][0],
                            strict=True,
                        )
                        if k in (5, 7)
                    ]
                keep = [
                    d
                    for d in keep
                    if d["score"] >= policy["confidence"]
                    and max(
                        (
                            sc
                            for k, b, sc in proposals
                            if k == 5 and overlap(d["box"], b) >= 0.4
                        ),
                        default=0,
                    )
                    >= policy["support"]
                    and max(
                        (
                            sc
                            for k, b, sc in proposals
                            if k == 7 and overlap(d["box"], b) >= 0.7
                        ),
                        default=0,
                    )
                    < policy.get("truck_veto", 2.0)
                ]
            ref["detections"] = [
                d for d in ref["detections"] if d["class_id"] not in preserved
            ] + keep
    reference_rows = []
    if len(inp) != 81:
        raise ValueError("development denominator")
    rows = []
    predictions = []
    diff = []
    for f, s, g, ref in zip(inp, scenes, gt, reference, strict=True):
        pixels = rgb_bytes(unpack(run_dir / "dataset", f["rgb_raw"], 2560, 1536))
        if (
            not f["scene"] == s["scene"] == g["scene"] == ref["scene"]
            or hashlib.sha256(pixels).hexdigest() != f["rgb_sha256"]
            or f["rgb_sha256"] != ref["rgb_sha256"]
        ):
            raise ValueError("original frame identity")
        rgb = Image.frombytes("RGB", (2560, 1536), pixels).resize(
            (960, 960), Image.Resampling.BILINEAR
        )
        tensor = np.ascontiguousarray(
            np.asarray(rgb, np.float32).transpose(2, 0, 1)[None] / 255
        )
        raw = dict(
            zip(
                spec["outputs"],
                session.run(spec["outputs"], {"images": tensor}),
                strict=True,
            )
        )
        pred = detections(raw, spec)
        rows.append((s, g, pred, True, False, None))
        reference_rows.append((s, g, ref["detections"], True, False, None))
        predictions.append(
            dict(scene=f["scene"], rgb_sha256=f["rgb_sha256"], detections=pred)
        )
        before, after = (
            measure(items, g["objects"], g["excluded"])[:2]
            for items in (ref["detections"], pred)
        )
        if before != after or Counter(d["class_id"] for d in pred) != Counter(
            d["class_id"] for d in ref["detections"]
        ):
            diff.append(f["scene"])
    card = {k: v for k, v in quality(rows).items() if k != "records"}
    protocol = read(BASE.parents[3] / "profiles/perception-quality-protocol-v9.json")
    comparison = relative(read(run_dir / "baseline/score.json"), card, protocol)
    write(output / "predictions.json", predictions)
    write(output / "score.json", card)
    write(
        output / "result.json",
        dict(
            onnx_sha256=spec["model_sha256"],
            ort=ort.__version__,
            provider=session.get_providers()[0],
            frames=len(inp),
            quality_matches_torch=card
            == {k: v for k, v in quality(reference_rows).items() if k != "records"},
            frame_class_count_or_match_differences=diff,
            absolute=card["absolute_quality"],
            relative=comparison,
            baseline_score_sha256=digest(run_dir / "baseline/score.json"),
            predictions_sha256=digest(output / "predictions.json"),
        ),
    )
    print(card["micro"], comparison, len(diff), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--bundle", type=Path)
    a = p.parse_args()
    run(a.root, a.output, a.bundle)

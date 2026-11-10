#!/usr/bin/env python3
"""Strict unchanged weights, native geometric caches and dynamic-path references."""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from itertools import islice
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import numpy as np
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import RgbDataset
from physical_ai.perception.resolution_v1 import (
    SIZES,
    CHECKPOINT_SHA,
    ORIGINAL_ONNX_SHA,
    prepare_rgb,
)
from export_model_screen_v2 import model_from_checkpoint
from check_model_screen_v1 import compare_top300
from run_model_screen_v1 import require, write_new


def state_hash(model, exclude_geometry=False):
    digest = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        if exclude_geometry and name in (
            "detector.decoder.anchors",
            "detector.decoder.valid_mask",
        ):
            continue
        a = tensor.detach().cpu().contiguous().numpy()
        digest.update(name.encode())
        digest.update(str((a.dtype.str, a.shape)).encode())
        digest.update(a.tobytes())
    return digest.hexdigest()


def configure(model, size, dynamic=False):
    from physical_ai.perception.resolution_v1 import validate_size

    validate_size(size)
    original = state_hash(model, True)
    encoder, decoder = model.detector.encoder, model.detector.decoder
    encoder.eval_spatial_size = None if dynamic else [size, size]
    decoder.eval_spatial_size = None if dynamic else [size, size]
    if not dynamic:
        encoder._reset_parameters()
        decoder.anchors, decoder.valid_mask = decoder._generate_anchors()
        require(
            decoder.anchors.shape[1]
            == sum((size // s) ** 2 for s in decoder.feat_strides),
            "native anchor denominator",
        )
        for idx in encoder.use_encoder_idx:
            require(
                getattr(encoder, f"pos_embed{idx}").shape[1]
                == (size // encoder.feat_strides[idx]) ** 2,
                "native positional denominator",
            )
    require(
        state_hash(model, True) == original, "learned or nongeometric state changed"
    )
    return dict(
        size=size,
        dynamic=dynamic,
        nongeometric_state_sha256=original,
        state_sha256=state_hash(model),
        anchor_shape=list(decoder.anchors.shape),
        eval_spatial_size=encoder.eval_spatial_size,
    )


def export(base, checkpoint, original):
    import torch
    import torchvision.transforms as T
    from PIL import Image
    import onnx
    from resolution_v1_common import check_freeze

    check_freeze(base / "freeze.json")
    require(
        sha256_file(checkpoint) == CHECKPOINT_SHA
        and sha256_file(original) == ORIGINAL_ONNX_SHA,
        "pinned model files",
    )
    out = base / "models"
    refs = base / "reference"
    out.mkdir(exist_ok=False)
    refs.mkdir(exist_ok=False)
    torch.set_num_threads(4)
    torch.manual_seed(20261110)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    model, strict = model_from_checkpoint("dfine-m", checkpoint)
    original_state = state_hash(model, True)
    probes = list(
        islice(
            RgbDataset(
                base.parent / "m10-quality-v9/preparation-development-data/rgb.json"
            ).frames(),
            3,
        )
    )
    manifest = dict(
        schema="m10-resolution-models-v1",
        started_utc=datetime.now(timezone.utc).isoformat(),
        freeze_sha256=sha256_file(base / "freeze.json"),
        checkpoint_sha256=CHECKPOINT_SHA,
        strict_state_load=strict["strict_state_load"],
        nongeometric_state_sha256=original_state,
        models={},
        references=[],
    )
    for size in SIZES:
        static = deepcopy(model)
        geometry = configure(static, size)
        dynamic = deepcopy(model)
        configure(dynamic, size, dynamic=True)
        if size == 640:
            import shutil

            shutil.copy2(original, out / f"dfine-{size}.onnx")
        else:
            with torch.inference_mode():
                torch.onnx.export(
                    static,
                    (torch.zeros(1, 3, size, size), torch.tensor([[640, 384]])),
                    str(out / f"dfine-{size}.onnx"),
                    opset_version=16,
                    input_names=["images", "orig_target_sizes"],
                    output_names=["labels", "boxes", "scores"],
                    do_constant_folding=True,
                )
        path = out / f"dfine-{size}.onnx"
        graph = onnx.load(path)
        onnx.checker.check_model(graph)
        require(
            not any(t.external_data for t in graph.graph.initializer)
            and {n.domain for n in graph.graph.node} <= {"", "ai.onnx"},
            "standard standalone ONNX",
        )
        manifest["models"][str(size)] = dict(
            size=size,
            path=str(path.relative_to(base)),
            sha256=sha256_file(path),
            bytes=path.stat().st_size,
            geometry=geometry,
            opset=16,
            operators=sorted({n.op_type for n in graph.graph.node}),
        )
        for n, (source, frame) in enumerate(probes):
            rgb = np.frombuffer(frame.rgb, np.uint8).reshape(384, 640, 3)
            native = T.Compose([T.Resize((size, size)), T.ToTensor()])(
                Image.fromarray(rgb)
            )[None]
            np.testing.assert_array_equal(
                native.numpy(), prepare_rgb(rgb, size)["images"]
            )
            with torch.inference_mode():
                results = [
                    dict(
                        zip(
                            ("labels", "boxes", "scores"),
                            [v.numpy() for v in m(native, torch.tensor([[640, 384]]))],
                        )
                    )
                    for m in (dynamic, static)
                ]
            delta = compare_top300(*results)
            target = refs / f"{size}-{n}.npz"
            np.savez_compressed(target, **results[0])
            manifest["references"].append(
                dict(
                    size=size,
                    probe=n,
                    rgb_sha256=source["rgb_sha256"],
                    tensor_sha256=hashlib.sha256(native.numpy().tobytes()).hexdigest(),
                    file=str(target.relative_to(base)),
                    sha256=sha256_file(target),
                    static_dynamic=delta,
                )
            )
        require(
            state_hash(static, True) == state_hash(dynamic, True) == original_state,
            "all variants have identical state",
        )
        del static, dynamic
    manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
    write_new(base / "models.json", manifest)
    return manifest


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for n in ("base", "checkpoint", "original"):
        p.add_argument("--" + n, type=Path, required=True)
    a = p.parse_args()
    r = export(a.base, a.checkpoint, a.original)
    print("PASS", len(r["models"]), "models", len(r["references"]), "native probes")

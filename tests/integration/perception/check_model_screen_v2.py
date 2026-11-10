#!/usr/bin/env python3
"""Three upstream FP32 references and complete CPU/CUDA/grid consistency probes."""

import argparse
from dataclasses import asdict
import importlib
from pathlib import Path
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import numpy as np
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import RgbDataset, read_json
from physical_ai.perception.model_screen_v2 import (
    CANDIDATES,
    THRESHOLDS,
    ScreenDetector,
    decode,
)
from check_model_screen_v1 import PROBES, compare_detections, compare_top300
from export_model_screen_v2 import CHECKPOINTS, VENDOR, model_from_checkpoint
from run_model_screen_v1 import write_new

ROOT = Path(__file__).resolve().parents[3]


def reference(output, models):
    import torch
    import torchvision.transforms as T
    from PIL import Image

    output.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    rows = []
    filenames = {
        "dfine-m": "dfine-m.pth",
        "rtv4-s": "rtv4-s.pth",
        "damo-s": "damoyolo_tinynasL25_S.pt",
    }
    frames = list(RgbDataset(PROBES).frames())[:3]
    for candidate in CHECKPOINTS:
        model, config = model_from_checkpoint(
            candidate,
            ROOT / "build/m10-model-screen-v2/upstream" / filenames[candidate],
        )
        backend = ScreenDetector(candidate, ROOT / models[candidate], "cpu")
        for i, (source, camera) in enumerate(frames):
            rgb = np.frombuffer(camera.rgb, np.uint8).reshape(384, 640, 3)
            if candidate == "damo-s":
                transform = importlib.import_module(
                    "damo.dataset.transforms.transforms"
                )
                preparation = transform.Compose(
                    [
                        transform.Resize(
                            (640, 640), target_size=(640, 640), keep_ratio=False
                        ),
                        transform.ToTensor(),
                        transform.Normalize([0.0, 0.0, 0.0], [1.0, 1.0, 1.0]),
                    ]
                )
                tensor, _ = preparation(np.asarray(Image.fromarray(rgb).convert("RGB")))
                inputs = (tensor[None],)
            else:
                tensor = T.Compose([T.Resize((640, 640)), T.ToTensor()])(
                    Image.fromarray(rgb)
                )[None]
                inputs = (tensor, torch.tensor([[640, 384]]))
            np.testing.assert_array_equal(
                inputs[0].numpy(), backend.prepare(camera)["images"]
            )
            with torch.inference_mode():
                values = model(*inputs)
            names = (
                ["scores", "boxes"]
                if candidate == "damo-s"
                else ["labels", "boxes", "scores"]
            )
            raw = dict(zip(names, (value.numpy() for value in values)))
            np.savez_compressed(output / f"{candidate}-{i}.npz", **raw)
            native = {}
            if candidate == "damo-s":
                official_nms = importlib.import_module(
                    "damo.utils.boxes"
                ).multiclass_nms
                for threshold in THRESHOLDS:
                    b, s, c = official_nms(
                        values[1][0], values[0][0], threshold, 0.7, 500
                    )
                    b = b.numpy()[:, :4] * np.array([1, 0.6, 1, 0.6], np.float32)
                    from physical_ai.perception.model_screen_v2 import select

                    native[str(threshold)] = [
                        asdict(d) for d in select(c.numpy(), s.numpy(), b, threshold)
                    ]
            rows.append(
                dict(
                    candidate=candidate,
                    probe=i,
                    rgb_sha256=source["rgb_sha256"],
                    native_detections=native,
                    strict_load=config["strict_state_load"],
                    checkpoint_sha256=config["checkpoint_sha256"],
                )
            )
    result = dict(
        status="PASS",
        rows=rows,
        probes=str(PROBES.relative_to(ROOT)),
        torch_version=torch.__version__,
        source=sha256_file(VENDOR / "upstream-files.json"),
    )
    write_new(output / "reference.json", result)
    return result


def numeric(output, reference_path, models):
    references = read_json(reference_path / "reference.json")
    report = dict(
        status="PASS",
        rows=[],
        failures=[],
        probes=str(PROBES.relative_to(ROOT)),
        reference_sha256=sha256_file(reference_path / "reference.json"),
        tolerances=dict(
            dense_raw_atol=0.003,
            dense_raw_rtol=0.003,
            box_atol_px=0.1,
            score_atol=0.0001,
        ),
    )
    frames = list(RgbDataset(PROBES).frames())[:3]
    for candidate in CANDIDATES:
        try:
            cpu, cuda = [
                ScreenDetector(candidate, ROOT / models[candidate], mode)
                for mode in ("cpu", "cuda")
            ]
            for i, (source, camera) in enumerate(frames):
                feed = cpu.prepare(camera)
                names = [o.name for o in cpu.session.get_outputs()]
                raw = [
                    dict(zip(names, backend.session.run(None, feed)))
                    for backend in (cpu, cuda)
                ]
                deltas = []
                pairs = [(raw[0], raw[1])]
                if candidate in CHECKPOINTS:
                    spec = next(
                        r
                        for r in references["rows"]
                        if r["candidate"] == candidate and r["probe"] == i
                    )
                    if spec["rgb_sha256"] != source["rgb_sha256"]:
                        raise ValueError("reference probe identity")
                    with np.load(
                        reference_path / f"{candidate}-{i}.npz", allow_pickle=False
                    ) as data:
                        expected = dict(data)
                    pairs.append((expected, raw[0]))
                for a, b in pairs:
                    if cpu.spec["family"] == "rtdetr":
                        deltas.append(compare_top300(a, b))
                    else:
                        for name in names:
                            np.testing.assert_allclose(
                                a[name], b[name], atol=0.003, rtol=0.003
                            )
                        deltas.append(
                            {
                                name: float(np.max(np.abs(a[name] - b[name])))
                                for name in names
                            }
                        )
                    for threshold in THRESHOLDS:
                        compare_detections(
                            [asdict(d) for d in cpu.decode(a, threshold)],
                            [asdict(d) for d in cpu.decode(b, threshold)],
                        )
                if candidate == "damo-s":
                    for threshold in THRESHOLDS:
                        compare_detections(
                            spec["native_detections"][str(threshold)],
                            [asdict(d) for d in decode(expected, "damo", threshold)],
                        )
                report["rows"].append(
                    dict(
                        candidate=candidate,
                        probe=i,
                        rgb_sha256=source["rgb_sha256"],
                        full_raw_deltas=deltas,
                        thresholds=list(THRESHOLDS),
                        status="PASS",
                    )
                )
            del cpu, cuda
        except Exception:
            report["status"] = "FAIL"
            report["failures"].append(
                dict(candidate=candidate, error=traceback.format_exc())
            )
    write_new(output, report)
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("reference", "numeric"))
    p.add_argument("--models", type=Path, required=True)
    p.add_argument("--reference", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    models = read_json(args.models)
    report = (
        reference(args.output, models)
        if args.action == "reference"
        else numeric(args.output, args.reference, models)
    )
    print(report["status"])
    if report["status"] != "PASS":
        sys.exit(1)

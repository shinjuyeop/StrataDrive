#!/usr/bin/env python3
"""Independent OpenCV/PyTorch references on accepted preparation RGB only."""

import argparse
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import cv2
import numpy as np
from PIL import Image
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.dataset import RgbDataset
from physical_ai.perception.model_screen_v1 import prepare_rgb
from quality_v9_common import check_preparation, require, write_new
from export_model_screen_v2 import model_from_checkpoint


def reference(base, baseline, checkpoint, output):
    import torch
    import torchvision.transforms as T

    check_preparation(base)
    require(
        (base / "preparation-reviewed.flag").exists(),
        "model-free visual review before inference",
    )
    output.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    model, config = model_from_checkpoint("dfine-m", checkpoint)
    require(
        sha256_file(baseline)
        == "c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063",
        "baseline reference identity",
    )
    net = cv2.dnn.readNetFromONNX(str(baseline))
    net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
    net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
    data = base / "preparation-development-data/rgb.json"
    rows = []
    for n, (source, frame) in enumerate(RgbDataset(data).frames()):
        if n == 3:
            break
        rgb = np.frombuffer(frame.rgb, np.uint8).reshape(384, 640, 3)
        padded = np.full((1, 3, 640, 640), 114.0, np.float32)
        padded[0, :, :384, :640] = rgb.transpose(2, 0, 1)
        net.setInput(padded)
        baseline_raw = net.forward()
        np.savez_compressed(output / f"baseline-{n}.npz", output=baseline_raw)
        tensor = T.Compose([T.Resize((640, 640)), T.ToTensor()])(Image.fromarray(rgb))[
            None
        ]
        np.testing.assert_array_equal(
            tensor.numpy(), prepare_rgb(rgb, "rtdetr")["images"]
        )
        with torch.inference_mode():
            labels, boxes, scores = model(tensor, torch.tensor([[640, 384]]))
        np.savez_compressed(
            output / f"dfine-{n}.npz",
            labels=labels.numpy(),
            boxes=boxes.numpy(),
            scores=scores.numpy(),
        )
        rows.append(
            dict(
                probe=n,
                rgb_sha256=source["rgb_sha256"],
                baseline_tensor_sha256=hashlib.sha256(padded.tobytes()).hexdigest(),
                dfine_tensor_sha256=hashlib.sha256(
                    tensor.numpy().tobytes()
                ).hexdigest(),
            )
        )
    require(len(rows) == 3, "reference probe denominator")
    report = dict(
        schema="m10-v9-upstream-reference-v1",
        status="PASS",
        dataset_sha256=sha256_file(data),
        rows=rows,
        baseline_sha256=sha256_file(baseline),
        checkpoint_sha256=config["checkpoint_sha256"],
        strict_state_load=config["strict_state_load"],
        torch_version=torch.__version__,
        opencv_version=cv2.__version__,
        inference_scope="Accepted preparation-development RGB only; no quality score or holdout inference",
    )
    write_new(output / "reference.json", report)
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("base", "baseline", "checkpoint", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    a = p.parse_args()
    print(reference(a.base, a.baseline, a.checkpoint, a.output)["status"])

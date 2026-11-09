"""Export the selected bound L6 checkpoint and retain independent numeric probes."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import sha256_file
from physical_ai.perception.domain_data_v1 import DomainDataset, write_json_new
from physical_ai.perception.training_v1 import (
    HEAD_TO_NATIVE,
    check_freeze,
    model,
    pack_sample,
    state_digest,
)


def export(run, data, out):
    import numpy as np
    import torch
    import onnx

    frozen = check_freeze(run / "freeze.json")
    result = json.loads((run / "result.json").read_text())
    if (
        result["status"] != "COMPLETE"
        or sha256_file(run / "best.pth") != result["best_checkpoint_sha256"]
    ):
        raise ValueError("completed checkpoint identity")
    checkpoint = torch.load(run / "best.pth", map_location="cpu", weights_only=True)
    if checkpoint["epoch"] != result["best"]["epoch"] or checkpoint[
        "freeze_sha256"
    ] != sha256_file(run / "freeze.json"):
        raise ValueError("checkpoint training lineage")
    if sha256_file(data / "dataset.json") != frozen["dataset_sha256"]:
        raise ValueError("export dataset identity")
    out.mkdir(parents=True, exist_ok=False)
    net = model()
    net.load_state_dict(checkpoint["model"], strict=True)
    if state_digest(net) != result["best"]["state_sha256"]:
        raise ValueError("selected tensor digest")
    net.eval()
    torch.set_num_threads(4)
    torch.onnx.export(
        net,
        torch.full((1, 3, 640, 640), 114.0),
        str(out / "model.onnx"),
        input_names=["images"],
        output_names=["output"],
        opset_version=11,
        do_constant_folding=True,
    )
    onnx.checker.check_model(onnx.load(out / "model.onnx"), full_check=True)
    manifest = dict(
        schema="m10-trained-model-v1",
        architecture="YOLOX-L-six-class",
        head_to_native=list(HEAD_TO_NATIVE),
        input=[1, 3, 640, 640],
        output=[1, 8400, 11],
        precision="float32",
        input_profile="rgb-unscaled-letterbox640-v1",
        model_sha256=sha256_file(out / "model.onnx"),
        model_bytes=(out / "model.onnx").stat().st_size,
        training_freeze_sha256=sha256_file(run / "freeze.json"),
        checkpoint_sha256=result["best_checkpoint_sha256"],
        state_sha256=result["best"]["state_sha256"],
        selected_epoch=result["best"]["epoch"],
        dataset_sha256=frozen["dataset_sha256"],
        runtime_promotion=False,
    )
    write_json_new(out / "manifest.json", manifest)
    validation = list(DomainDataset(data, "validation").samples())
    training = list(DomainDataset(data, "train").samples())
    generator = np.random.default_rng(20261109)
    y, x = np.mgrid[:384, :640]
    probes = [
        ("synthetic-zero", np.zeros((384, 640, 3), np.uint8)),
        ("synthetic-pad", np.full((384, 640, 3), 114, np.uint8)),
        (
            "synthetic-gradient",
            np.stack((x % 256, y % 256, (x + y) % 256), -1).astype(np.uint8),
        ),
        ("synthetic-random", generator.integers(0, 256, (384, 640, 3), dtype=np.uint8)),
    ]
    probes += [
        (im["scene"], rgb)
        for im, rgb, _ in [validation[i] for i in np.linspace(0, 266, 8, dtype=int)]
    ]
    probes += [
        (im["scene"], rgb)
        for im, rgb, _ in [training[i] for i in np.linspace(0, 812, 4, dtype=int)]
    ]
    net.cuda()
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cuda.matmul.allow_tf32 = False
    entries = []
    with torch.inference_mode():
        for i, (name, rgb) in enumerate(probes):
            tensor, _ = pack_sample(rgb, [])
            raw = net(torch.from_numpy(tensor[None]).cuda()).cpu().numpy()
            path = out / f"probe-{i:02d}.npz"
            np.savez_compressed(path, rgb=rgb, raw=raw)
            entries.append(dict(name=name, file=path.name, sha256=sha256_file(path)))
    write_json_new(
        out / "probes.json",
        dict(
            schema="m10-trained-numeric-probes-v1",
            probes=entries,
            manifest_sha256=sha256_file(out / "manifest.json"),
        ),
    )
    print(json.dumps(manifest), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run", type=Path)
    p.add_argument("data", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    export(a.run, a.data, a.output)

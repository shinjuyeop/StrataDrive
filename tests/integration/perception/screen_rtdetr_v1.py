#!/usr/bin/env python3
"""Load only the pinned upstream inference modules; never run setup/training code."""

import importlib
import hashlib
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
VENDOR = ROOT / "third_party/rtdetr-screen-v1"


def model_from_checkpoint(checkpoint):
    import torch

    if (
        hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest()
        != "2ace52184b620204004509b72752ac7bfe64aadaf7fc1d076b18df8ab5a5c77e"
    ):
        raise ValueError("pinned RT-DETR checkpoint identity")
    prefix = "stratadrive_rtdetr_v1"
    for suffix in ("", ".core", ".nn", ".nn.backbone", ".zoo", ".zoo.rtdetr"):
        name = prefix + suffix
        if name not in sys.modules:
            package = types.ModuleType(name)
            package.__path__ = [
                str(VENDOR / "src" / suffix.lstrip(".").replace(".", "/"))
            ]
            sys.modules[name] = package
    workspace = importlib.import_module(prefix + ".core.workspace")
    sys.modules[prefix + ".core"].register = workspace.register

    def cls(module, name):
        return getattr(importlib.import_module(prefix + module), name)

    # Explicitly instantiate the merged, pinned upstream R18 config. The complete
    # official COCO checkpoint is strict-loaded; pretrained=False avoids a second
    # backbone download, with no learned tensor substitutions.
    backbone = cls(".nn.backbone.presnet", "PResNet")(
        depth=18,
        variant="d",
        return_idx=[1, 2, 3],
        freeze_at=-1,
        freeze_norm=False,
        pretrained=False,
    )
    encoder = cls(".zoo.rtdetr.hybrid_encoder", "HybridEncoder")(
        in_channels=[128, 256, 512],
        hidden_dim=256,
        expansion=0.5,
        eval_spatial_size=[640, 640],
    )
    decoder = cls(".zoo.rtdetr.rtdetrv2_decoder", "RTDETRTransformerv2")(
        num_classes=80,
        feat_channels=[256, 256, 256],
        num_layers=3,
        num_points=[4, 4, 4],
        eval_spatial_size=[640, 640],
    )
    detector = cls(".zoo.rtdetr.rtdetr", "RTDETR")(backbone, encoder, decoder)
    state = torch.load(checkpoint, map_location="cpu", weights_only=True)
    detector.load_state_dict(state["ema"]["module"], strict=True)
    post = cls(".zoo.rtdetr.rtdetr_postprocessor", "RTDETRPostProcessor")(
        num_classes=80,
        use_focal_loss=True,
        num_top_queries=300,
        remap_mscoco_category=False,
    ).deploy()

    class Export(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.detector = detector.deploy()
            self.post = post

        def forward(self, images, orig_target_sizes):
            return self.post(self.detector(images), orig_target_sizes)

    return Export().eval()


if __name__ == "__main__":
    import argparse
    import torch
    import onnx

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    torch.set_num_threads(4)
    torch.manual_seed(20261110)
    model = model_from_checkpoint(args.checkpoint)
    with torch.inference_mode():
        torch.onnx.export(
            model,
            (torch.zeros(1, 3, 640, 640), torch.tensor([[640, 384]])),
            str(args.output),
            opset_version=16,
            input_names=["images", "orig_target_sizes"],
            output_names=["labels", "boxes", "scores"],
            do_constant_folding=True,
        )
    onnx.checker.check_model(onnx.load(args.output))
    print(
        hashlib.sha256(args.output.read_bytes()).hexdigest(), args.output.stat().st_size
    )

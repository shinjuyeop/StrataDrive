#!/usr/bin/env python3
"""Hash-checked official inference-only FP32 exports; no training entry points."""

import argparse
import copy
import hashlib
import importlib
import inspect
import json
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[3]
VENDOR = ROOT / "third_party/pretrained-screen-v2"
CHECKPOINTS = {
    "dfine-m": "b44a7586bf490858c7b8bce9e44bd025cb88724df9a07a8deb3ae1c12e608195",
    "rtv4-s": "238a3f6537bf3b75b55e73f91f9d4cec8d21259b4908b3f21896f3e038b5a3ee",
    "damo-s": "70ccc4b45efd4ebb5e180c77040ca26714aaa9559c2b609b69c1bb6199b4be63",
}


def package(name, path):
    if name not in sys.modules:
        mod = types.ModuleType(name)
        mod.__path__ = [str(path)]
        sys.modules[name] = mod
    return sys.modules[name]


def merge(dest, source):
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(dest.get(key), dict):
            merge(dest[key], value)
        else:
            dest[key] = copy.deepcopy(value)
    return dest


def yaml_config(path):
    import yaml

    current = yaml.safe_load(path.read_text())
    result = {}
    for include in current.pop("__include__", []):
        merge(result, yaml_config(path.parent / include))
    return merge(result, current)


def transformer(candidate, state):
    import torch

    is_v4 = candidate == "rtv4-s"
    folder, source = ("rtv4", "engine") if is_v4 else ("dfine", "src")
    root = VENDOR / folder
    prefix = "stratadrive_screen_v2_" + folder
    base = root / source
    suffixes = (
        ("", ".core", ".backbone", ".rtv4")
        if is_v4
        else ("", ".core", ".nn", ".nn.backbone", ".zoo", ".zoo.dfine")
    )
    for suffix in suffixes:
        package(prefix + suffix, base / suffix.lstrip(".").replace(".", "/"))
    workspace = importlib.import_module(prefix + ".core.workspace")
    sys.modules[prefix + ".core"].register = workspace.register
    path = (
        "configs/rtv4/rtv4_hgnetv2_s_coco.yml"
        if is_v4
        else "configs/dfine/dfine_hgnetv2_m_coco.yml"
    )
    config = yaml_config(root / path)
    decisions = {
        "config": path,
        "overrides": {"HGNetv2.pretrained": False},
        "constructors": {},
    }

    def make(module, name, **overrides):
        cls = getattr(importlib.import_module(prefix + module), name)
        values = copy.deepcopy(config.get(name, {}))
        for key in getattr(cls, "__share__", []):
            if key in config:
                values[key] = copy.deepcopy(config[key])
        values.update(overrides)
        signature = inspect.signature(cls)
        unknown = set(values) - set(signature.parameters)
        if unknown:
            raise ValueError(f"unresolved native configuration: {name}: {unknown}")
        decisions["constructors"][name] = values
        return cls(**values)

    backbone_module = ".backbone.hgnetv2" if is_v4 else ".nn.backbone.hgnetv2"
    zoo = ".rtv4" if is_v4 else ".zoo.dfine"
    backbone = make(backbone_module, "HGNetv2", pretrained=False)
    encoder = make(zoo + ".hybrid_encoder", "HybridEncoder")
    decoder = make(zoo + ".dfine_decoder", "DFINETransformer")
    model_name = "RTv4" if is_v4 else "DFINE"
    cls = getattr(
        importlib.import_module(prefix + zoo + (".rtv4" if is_v4 else ".dfine")),
        model_name,
    )
    detector = cls(backbone, encoder, decoder)
    detector.load_state_dict(state, strict=True)
    post = make(
        zoo + ".postprocessor",
        "PostProcessor" if is_v4 else "DFINEPostProcessor",
        remap_mscoco_category=False,
    ).deploy()

    class Export(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.detector = detector.deploy()
            self.post = post

        def forward(self, images, orig_target_sizes):
            return self.post(self.detector(images), orig_target_sizes)

    return Export().eval(), decisions


def damo(state):
    import torch

    root = VENDOR / "damo" / "damo"
    for suffix in (
        "",
        ".base_models",
        ".base_models.backbones",
        ".base_models.necks",
        ".base_models.heads",
        ".base_models.core",
        ".base_models.losses",
        ".utils",
        ".structures",
        ".dataset",
        ".dataset.transforms",
    ):
        package("damo" + suffix, root / suffix.lstrip(".").replace(".", "/"))
    utils = sys.modules["damo.utils"]
    utils.make_divisible = importlib.import_module(
        "damo.utils.model_utils"
    ).make_divisible
    utils.postprocess = importlib.import_module("damo.utils.boxes").postprocess
    # Official ModelScope damoyolo.py / configuration.json plus current upstream
    # backward-compatible legacy=True (81 learned channels, first80 published).
    config = {
        "backbone": dict(
            out_indices=(2, 4, 5),
            with_spp=True,
            use_focus=True,
            act="relu",
            reparam=True,
        ),
        "neck": dict(
            depth=1.0,
            hidden_ratio=0.75,
            in_channels=[128, 256, 512],
            out_channels=[128, 256, 512],
            act="relu",
            spp=False,
            block_name="BasicBlock_3x3_Reverse",
        ),
        "head": dict(
            num_classes=80,
            in_channels=[128, 256, 512],
            stacked_convs=0,
            reg_max=16,
            act="silu",
            nms_conf_thre=0.05,
            nms_iou_thre=0.7,
            legacy=True,
            nms=False,
        ),
        "preprocessing": dict(
            color="RGB",
            keep_ratio=False,
            image_mean=[0.0, 0.0, 0.0],
            image_std=[1.0, 1.0, 1.0],
            input_size=[640, 640],
        ),
    }
    structure = root / "base_models/backbones/nas_backbones/tinynas_L25_k1kx.txt"
    loader = importlib.import_module(
        "damo.base_models.backbones.tinynas_res"
    ).load_tinynas_net
    backbone = loader(
        types.SimpleNamespace(
            net_structure_str=structure.read_text().splitlines(), **config["backbone"]
        )
    )
    neck = importlib.import_module(
        "damo.base_models.necks.giraffe_fpn_btn"
    ).GiraffeNeckV2(**config["neck"])
    head = importlib.import_module("damo.base_models.heads.zero_head").ZeroHead(
        **config["head"]
    )

    class Export(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.backbone, self.neck, self.head = backbone, neck, head

        def forward(self, images):
            return self.head(self.neck(self.backbone(images)))

    model = Export()
    for layer in model.modules():
        if isinstance(layer, torch.nn.BatchNorm2d):
            layer.eps, layer.momentum = 1e-3, 0.03
    model.load_state_dict(state, strict=True)
    model.eval()
    repconv = importlib.import_module("damo.base_models.core.ops").RepConv
    for layer in list(model.modules()):
        if isinstance(layer, repconv):
            layer.switch_to_deploy()
    return model, config


def model_from_checkpoint(candidate, checkpoint):
    import torch

    if (
        hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest()
        != CHECKPOINTS[candidate]
    ):
        raise ValueError("pinned checkpoint identity")
    checkpoint = torch.load(checkpoint, map_location="cpu", weights_only=True)
    state = (
        checkpoint["ema"]["module"] if candidate == "rtv4-s" else checkpoint["model"]
    )
    model, config = (
        damo(state) if candidate == "damo-s" else transformer(candidate, state)
    )
    return model, dict(
        candidate=candidate,
        checkpoint_sha256=CHECKPOINTS[candidate],
        strict_state_load=True,
        tensor_count=len(state),
        native_configuration=config,
        training=False,
    )


if __name__ == "__main__":
    import torch
    import onnx

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", choices=CHECKPOINTS, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    torch.set_num_threads(4)
    torch.manual_seed(20261110)
    model, report = model_from_checkpoint(args.candidate, args.checkpoint)
    images = torch.zeros(1, 3, 640, 640)
    dense = args.candidate == "damo-s"
    inputs = (images,) if dense else (images, torch.tensor([[640, 384]]))
    with torch.inference_mode():
        values = model(*inputs)
        torch.onnx.export(
            model,
            inputs,
            str(args.output),
            opset_version=16,
            input_names=["images"] if dense else ["images", "orig_target_sizes"],
            output_names=["scores", "boxes"]
            if dense
            else ["labels", "boxes", "scores"],
            do_constant_folding=True,
        )
    onnx.checker.check_model(onnx.load(args.output))
    report.update(
        onnx_sha256=hashlib.sha256(args.output.read_bytes()).hexdigest(),
        onnx_bytes=args.output.stat().st_size,
        outputs=[dict(shape=list(v.shape), dtype=str(v.dtype)) for v in values],
        torch_version=torch.__version__,
        opset=16,
    )
    args.output.with_suffix(".export.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps(report, indent=2))

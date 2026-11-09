"""Explicit six-class training adaptor; optional torch is imported only by callers."""

from pathlib import Path
import hashlib
import json
import sys
import numpy as np
from .contract import sha256_file
from .yolox import postprocess

ROOT = Path(__file__).resolve().parents[2]
VENDOR = ROOT / "third_party/megvii-yolox-training-v1"
HEAD_TO_NATIVE = (0, 1, 2, 3, 5, 7)
PRETRAINED_SHA256 = "1e6b7fa6240375370b2a8a8eab9066b3cdd43fd1d0bfa8d2027fd3a51def2917"
PRETRAINED_BYTES = 434357141


def pack_sample(rgb, labels, flip=False):
    """Preserve every positive and transform half-open boxes without rounding."""
    if rgb.dtype != np.uint8 or rgb.shape != (384, 640, 3):
        raise ValueError("training RGB layout")
    if len(labels) > 100:
        raise ValueError("training label capacity; truncation forbidden")
    image = np.full((640, 640, 3), 114, np.float32)
    image[:384] = rgb[:, ::-1] if flip else rgb
    targets = np.zeros((100, 5), np.float32)
    for i, label in enumerate(labels):
        cls = label["native_class"]
        x, y, w, h = label["box"]
        if cls not in HEAD_TO_NATIVE or not all(np.isfinite([x, y, w, h])):
            raise ValueError("training label class/finite")
        if not (0 <= x < x + w <= 640 and 0 <= y < y + h <= 384):
            raise ValueError("training label bounds")
        cx = x + w / 2
        targets[i] = [
            HEAD_TO_NATIVE.index(cls),
            640 - cx if flip else cx,
            y + h / 2,
            w,
            h,
        ]
    return np.ascontiguousarray(image.transpose(2, 0, 1)), targets


def decode_six(raw):
    if (
        not isinstance(raw, np.ndarray)
        or raw.dtype != np.float32
        or raw.shape != (1, 8400, 11)
    ):
        raise ValueError("six-class raw tensor contract")
    # Use the existing finite/overflow/confidence/capacity/NMS contract, with
    # explicit native slots. Unused COCO channels are zero, never renumbered.
    expanded = np.zeros((1, 8400, 85), np.float32)
    expanded[:, :, :5] = raw[:, :, :5]
    expanded[:, :, np.array(HEAD_TO_NATIVE) + 5] = raw[:, :, 5:]
    return postprocess(expanded)


def vendor_identity():
    manifest = json.loads((VENDOR / "sources.json").read_text())
    for name, digest in manifest["files"].items():
        if sha256_file(VENDOR / name) != digest:
            raise ValueError("upstream source drift: " + name)
    return sha256_file(VENDOR / "sources.json")


def model(pretrained=None, six=True):
    vendor_identity()
    sys.path.insert(0, str(VENDOR / "source"))
    import torch
    from yolox.models import YOLOX, YOLOPAFPN, YOLOXHead

    net = YOLOX(YOLOPAFPN(depth=1.0, width=1.0), YOLOXHead(6 if six else 80, width=1.0))
    for module in net.modules():
        if isinstance(module, torch.nn.BatchNorm2d):
            module.eps, module.momentum = 1e-3, 0.03
    if pretrained is not None:
        data = Path(pretrained).read_bytes()
        if (
            len(data) != PRETRAINED_BYTES
            or hashlib.sha256(data).hexdigest() != PRETRAINED_SHA256
        ):
            raise ValueError("official pretrained bytes/hash")
        import io

        original = torch.load(io.BytesIO(data), map_location="cpu", weights_only=True)[
            "model"
        ]
        selected = {}
        for name, value in original.items():
            selected[name] = (
                value[list(HEAD_TO_NATIVE)].clone()
                if six and name.startswith("head.cls_preds.")
                else value
            )
        net.load_state_dict(selected, strict=True)
        # Independently verify every loaded tensor, including transplanted rows.
        for name, value in net.state_dict().items():
            if not torch.equal(value, selected[name].to(value.dtype)):
                raise ValueError("pretrained tensor transplant: " + name)
    net.head.decode_in_inference = False
    return net


def state_digest(net):
    h = hashlib.sha256()
    for name, tensor in sorted(net.state_dict().items()):
        a = tensor.detach().cpu().contiguous().numpy()
        h.update(
            name.encode() + str(a.dtype).encode() + str(a.shape).encode() + a.tobytes()
        )
    return h.hexdigest()


def check_freeze(path):
    value = json.loads(Path(path).read_text())
    for name, digest in value["sources"].items():
        if sha256_file(ROOT / name) != digest:
            raise ValueError("training source drift: " + name)
    return value

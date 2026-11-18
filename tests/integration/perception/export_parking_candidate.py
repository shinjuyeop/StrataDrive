"""Export the selected RGB-only D-FINE parking candidate to a fixed-shape ONNX graph."""

import argparse
from pathlib import Path
import onnx
import torch
from torch import nn
from torchvision.ops import box_convert
from occlusion_transfer_train import network, WEIGHTS
from parking_box_refinement import dimensions
from parking_occluded_queries import correction
from parking_overlap_calibration import ANCHOR, OVERLAP, models
from parking_region_verifier import (
    detector,
    digest,
    HEIGHT,
    read,
    WIDTH,
    write,
)


def aligned_features(feats, boxes):
    # Fixed two-sample-per-bin ROIAlign. Pack every ROI into the output grid of
    # one image so the existing CUDA GridSample operator can read it directly.
    center = (boxes[:, :2] + boxes[:, 2:]) / 2
    radius = (boxes[:, 2:] - boxes[:, :2]) * 0.85
    context = torch.cat((center - radius, center + radius), 1).clamp(0, 1)
    results = []
    for feat, roi, size in (
        (feats[0], boxes, 2),
        (feats[0], context, 2),
        (feats[1], boxes, 1),
    ):
        edge = 2 * size
        pos = (torch.arange(edge, device=boxes.device, dtype=boxes.dtype) + 0.5) / edge
        x = roi[:, :1] + (roi[:, 2:3] - roi[:, :1]) * pos
        y = roi[:, 1:2] + (roi[:, 3:] - roi[:, 1:2]) * pos
        points = torch.stack(
            (x[:, None, :].expand(-1, edge, -1), y[:, :, None].expand(-1, -1, edge)),
            dim=-1,
        )
        grid = (points * 2 - 1).reshape(1, -1, edge, 2)
        values = nn.functional.grid_sample(
            feat, grid, mode="bilinear", padding_mode="border", align_corners=False
        )
        pooled = (
            values.reshape(feat.shape[1], -1, size, 2, size, 2)
            .mean(dim=(3, 5))
            .permute(1, 0, 2, 3)
            .flatten(1)
        )
        results.append(
            nn.functional.layer_norm(pooled, (int(feat.shape[1]) * size * size,))
        )
    return torch.cat(results, dim=1)


class Candidate(nn.Module):
    def __init__(self, root, preserve_noncar, restore_bus):
        super().__init__()
        self.model = detector()
        self.restore_bus = restore_bus
        self.original_decoder = (
            network().detector.decoder if preserve_noncar or restore_bus else None
        )
        self.verify, self.loc, self.fraction = models(root)
        trial = root / "occluded-shrink"
        selected = read(trial / "selection.json")
        self.strength = selected["selected"]["scale"]
        if digest(trial / "correction.pt") != selected["weights"]:
            raise ValueError("occlusion checkpoint changed")
        weights = torch.load(trial / "correction.pt", weights_only=True)
        self.correction = correction(weights["weight"].shape[1])
        self.correction.load_state_dict(weights)

    def forward(self, images):
        feats = self.model.detector.encoder(self.model.detector.backbone(images))
        q = self.model.detector.decoder(feats)
        norm = box_convert(q["pred_boxes"][0], "cxcywh", "xyxy").clamp(0, 1)
        scale = images.new_tensor([WIDTH, HEIGHT, WIDTH, HEIGHT])
        raw = norm * scale
        x = aligned_features(feats, raw / scale).half().float()
        logits = 0.65 * self.verify(x).flatten() + 0.35 * q["pred_logits"][0, :, 2]
        d = self.loc(x).clamp(-1, 1) * self.fraction
        center, size = dimensions(raw)
        center = center + size * d[:, :2]
        size = size * d[:, 2:].exp()
        boxes = (
            torch.cat((center - size / 2, center + size / 2), 1)
            .clamp_min(0)
            .minimum(scale)
        )
        correction = self.correction(x).flatten().clamp(-1.5, 1.5) * self.strength
        target = torch.tensor([[WIDTH, HEIGHT]], device=images.device)
        if self.restore_bus:
            base = self.model.post(q, target)
            original = self.model.post(self.original_decoder(feats), target)
            return (*base, boxes, logits, correction, *original)
        base = self.model.post(
            self.original_decoder(feats) if self.original_decoder is not None else q,
            target,
        )
        return (*base, boxes, logits, correction)


def export(root, out, preserve_noncar=False, restore_bus=False):
    out.mkdir(parents=True, exist_ok=False)
    model = Candidate(root, preserve_noncar, restore_bus).eval()
    graph = out / "parking-dfine-960.onnx"
    names = ["labels", "boxes", "scores", "car_boxes", "car_logits", "adjacent_delta"]
    if restore_bus:
        names.extend(("original_labels", "original_boxes", "original_scores"))
    with torch.no_grad():
        torch.onnx.export(
            model,
            (torch.zeros((1, 3, 960, 960), device="cuda"),),
            str(graph),
            opset_version=16,
            input_names=["images"],
            output_names=names,
            do_constant_folding=True,
        )
    onnx.checker.check_model(str(graph))
    c = read(root / "occluded-shrink/protocol.json")["cutoffs"]
    write(
        out / "manifest.json",
        dict(
            model_sha256=digest(graph),
            preserve_noncar=preserve_noncar,
            original_bus=restore_bus,
            upstream_sha256=digest(WEIGHTS),
            input="images",
            shape=[1, 3, 960, 960],
            outputs=names,
            near=c["near"],
            ordinary=c["ordinary"],
            anchor=ANCHOR,
            overlap=OVERLAP,
            car_nms=0.55,
            verifier=digest(root / "fit/verifier.pt"),
            regressor=digest(root / "box-fit/regressor.pt"),
            correction=digest(root / "occluded-shrink/correction.pt"),
            pixel_input="Original RGB, Pillow bilinear to 960x960, float32 / 255.",
        ),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    p.add_argument("output", type=Path)
    classes = p.add_mutually_exclusive_group()
    classes.add_argument("--preserve-noncar", action="store_true")
    classes.add_argument("--restore-bus", action="store_true")
    args = p.parse_args()
    export(args.root, args.output, args.preserve_noncar, args.restore_bus)

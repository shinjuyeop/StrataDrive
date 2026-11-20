"""Export six independent copies of the registered D-FINE parking heads in one batch."""

import sys
from pathlib import Path
import torch
import onnx
from export_parking_candidate import (
    Candidate,
    box_convert,
    aligned_features,
    dimensions,
    WIDTH,
    HEIGHT,
)


class SixViews(Candidate):
    def forward(self, images):
        feats = self.model.detector.encoder(self.model.detector.backbone(images))
        q = self.model.detector.decoder(feats)
        scale = images.new_tensor([WIDTH, HEIGHT, WIDTH, HEIGHT])
        boxes, logits, deltas = [], [], []
        for i in range(6):
            norm = box_convert(q["pred_boxes"][i], "cxcywh", "xyxy").clamp(0, 1)
            raw = norm * scale
            x = (
                aligned_features([f[i : i + 1] for f in feats], raw / scale)
                .half()
                .float()
            )
            logits.append(
                0.65 * self.verify(x).flatten() + 0.35 * q["pred_logits"][i, :, 2]
            )
            d = self.loc(x).clamp(-1, 1) * self.fraction
            center, size = dimensions(raw)
            center = center + size * d[:, :2]
            size = size * d[:, 2:].exp()
            boxes.append(
                torch.cat((center - size / 2, center + size / 2), 1)
                .clamp_min(0)
                .minimum(scale)
            )
            deltas.append(self.correction(x).flatten().clamp(-1.5, 1.5) * self.strength)
        target = images.new_tensor([[WIDTH, HEIGHT]] * 6)
        return (
            *self.model.post(q, target),
            torch.stack(boxes),
            torch.stack(logits),
            torch.stack(deltas),
            *self.model.post(self.original_decoder(feats), target),
        )


def export(output):
    if output.exists():
        raise FileExistsError(output)
    with torch.no_grad():
        m = SixViews(Path("build/m10-parking-verifier-v1"), False, True).cuda().eval()
        names = [
            "labels",
            "boxes",
            "scores",
            "car_boxes",
            "car_logits",
            "adjacent_delta",
            "original_labels",
            "original_boxes",
            "original_scores",
        ]
        torch.onnx.export(
            m,
            torch.zeros((6, 3, 960, 960), device="cuda"),
            str(output),
            opset_version=16,
            input_names=["images"],
            output_names=names,
            do_constant_folding=True,
        )
    onnx.checker.check_model(str(output))


if __name__ == "__main__":
    export(Path(sys.argv[1]))

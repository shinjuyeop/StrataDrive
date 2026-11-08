"""V2 offline crop experiments; no live selection or changed model contract."""

from dataclasses import replace
import time
import cv2
import numpy as np

from .contract import MAX_DETECTIONS, PerceptionResult
from .quality_candidates import merge, restore_crop
from .yolox import YoloX, iou

CANDIDATES = ("baseline", "center-refine-v2", "vru-refine-v2")


def append_vru(base, crop):
    """Preserve every base box; add only nonduplicate crop person/two-wheelers."""
    if len(base) > 100 or len(crop) > 100:
        raise ValueError("candidate capacity")
    for d in tuple(base) + tuple(crop):
        d.validate()
    selected = list(base)
    for d in sorted(crop, key=lambda item: -item.score):
        if d.class_id not in (0, 1, 3):
            continue
        if any(
            p.class_id == d.class_id
            and float(iou(np.array(p.box), np.array([d.box]))[0]) > 0.5
            for p in selected
        ):
            continue
        selected.append(d)
        if len(selected) > MAX_DETECTIONS:
            raise ValueError("candidate output capacity")
    return tuple(selected)


class QualityCandidateV2:
    def __init__(self, model, candidate):
        if candidate not in CANDIDATES:
            raise ValueError("unknown v2 candidate")
        self.candidate = candidate
        self.detector = YoloX(model, execution="cuda")

    def infer(self, frame):
        base = self.detector.infer(frame)
        if self.candidate == "baseline":
            return base
        begin = time.monotonic_ns()
        pixels = np.frombuffer(frame.rgb, np.uint8).reshape(384, 640, 3)
        enlarged = cv2.resize(
            pixels[96:288, 160:480], (640, 384), interpolation=cv2.INTER_LINEAR
        )
        crop_frame = replace(frame, rgb=enlarged.tobytes())
        resize_ns = time.monotonic_ns() - begin
        crop = self.detector.infer(
            crop_frame
        )  # failure invalidates the entire candidate
        begin = time.monotonic_ns()
        restored = restore_crop(crop.detections)
        boxes = (
            append_vru(base.detections, restored)
            if self.candidate == "vru-refine-v2"
            else merge(base.detections + restored, vehicle_nms=False)
        )
        merged_ns = time.monotonic_ns() - begin
        result = PerceptionResult(
            frame.identity,
            boxes,
            base.preprocess_ns + crop.preprocess_ns + resize_ns,
            base.inference_ns + crop.inference_ns,
            base.postprocess_ns + crop.postprocess_ns + merged_ns,
        )
        result.validate()
        return result

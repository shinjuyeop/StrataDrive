"""Explicit offline quality experiments. Not selected by the live v1 worker.

All candidates keep the pinned weights, RGB contract and score threshold. They
must identify their separate experiment descriptor; no v1 runtime promotion.
"""

from dataclasses import replace
import time
import cv2
import numpy as np
from .contract import Detection, PerceptionResult, MAX_DETECTIONS
from .yolox import YoloX, iou

CANDIDATES = ("baseline", "vehicle-nms-v1", "center-refine-v1")


def merge(detections, *, vehicle_nms=True, same_class_nms=True):
    """Class NMS0.5 plus optional car/bus/truck NMS0.75; never merge VRUs."""
    if len(detections) > 200:
        raise ValueError("combined candidate capacity")
    for detection in detections:
        detection.validate()
    ordered = sorted(enumerate(detections), key=lambda item: (-item[1].score, item[0]))
    chosen = []
    for _, detection in ordered:
        suppressed = False
        for prior in chosen:
            same = same_class_nms and prior.class_id == detection.class_id
            vehicle = (
                vehicle_nms
                and prior.class_id != detection.class_id
                and prior.class_id in (2, 5, 7)
                and detection.class_id in (2, 5, 7)
            )
            if (same or vehicle) and float(
                iou(np.array(prior.box), np.array([detection.box]))[0]
            ) > (0.5 if same else 0.75):
                suppressed = True
                break
        if not suppressed:
            chosen.append(detection)
            if len(chosen) > MAX_DETECTIONS:
                raise ValueError("combined detection capacity")
    return tuple(chosen)


def restore_crop(detections):
    """Restore a fixed2x central crop to original pixels; discard crop cut-offs."""
    restored = []
    for detection in detections:
        detection.validate()
        x1, y1, x2, y2 = detection.box
        # Margin is in the resized640x384 crop coordinates, not source pixels.
        if x1 <= 2 or y1 <= 2 or x2 >= 638 or y2 >= 382:
            continue
        restored.append(
            Detection(
                detection.class_id,
                detection.score,
                (x1 / 2 + 160, y1 / 2 + 96, x2 / 2 + 160, y2 / 2 + 96),
            )
        )
    return tuple(restored)


class QualityCandidate:
    def __init__(self, model, candidate, execution="cuda"):
        if candidate not in CANDIDATES:
            raise ValueError("unknown quality candidate")
        self.candidate = candidate
        self.detector = YoloX(model, execution=execution)

    def infer(self, frame):
        base = self.detector.infer(frame)
        if self.candidate == "baseline":
            return base
        preprocess, inference, postprocess = (
            base.preprocess_ns,
            base.inference_ns,
            base.postprocess_ns,
        )
        before = time.monotonic_ns()
        if self.candidate == "center-refine-v1":
            image = np.frombuffer(frame.rgb, np.uint8).reshape(384, 640, 3)
            enlarged = cv2.resize(
                image[96:288, 160:480], (640, 384), interpolation=cv2.INTER_LINEAR
            )
            crop = replace(frame, rgb=enlarged.tobytes())
            preprocess += time.monotonic_ns() - before
            refined = self.detector.infer(crop)
            preprocess += refined.preprocess_ns
            inference += refined.inference_ns
            postprocess += refined.postprocess_ns
            before = time.monotonic_ns()
            detections = base.detections + restore_crop(refined.detections)
        else:
            detections = base.detections
        combined = merge(
            detections, same_class_nms=self.candidate == "center-refine-v1"
        )
        postprocess += time.monotonic_ns() - before
        result = PerceptionResult(
            frame.identity, combined, preprocess, inference, postprocess
        )
        result.validate()
        return result

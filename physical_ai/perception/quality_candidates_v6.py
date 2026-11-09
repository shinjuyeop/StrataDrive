"""Pinned L full/context experiment; private support never publishes detections."""

from dataclasses import replace
import time
import cv2
import numpy as np
from .contract import MODEL_SHA256
from .large_model_v6 import LargeYoloX, OfflineResultV6, LARGE_SHA256, INPUT_PROFILE
from .quality_candidates import merge, restore_crop
from .yolox import YoloX, image_health, preprocess, postprocess, GRIDS, STRIDES, iou

CANDIDATES = ("baseline", "large-v6", "large-context-v6")
MODELS = {c: MODEL_SHA256 if c == "baseline" else LARGE_SHA256 for c in CANDIDATES}
CLASSES = (0, 1, 2, 3, 5, 7)
BODY = (1, 2, 3, 5, 7)
POLICY = dict(
    crop_xywh=[160, 96, 320, 192],
    scale=2,
    crop_edge_margin_pixels=2,
    published_score_min=0.35,
    weak_score_min=0.1,
    support_iou_min=0.3,
    strong_crop_score=0.5,
    weak_crop_semantic_min=0.2,
    body_disagreement_iou_min=0.5,
    body_crop_override_score=0.5,
    verify_base_below=0.5,
    same_class_nms_iou=0.5,
    person_never_cross_class_suppressed=True,
    max_detections=100,
)


def weak_proposals(raw):
    postprocess(raw)  # Validate all anchors, including filtered low-confidence boxes.
    values = raw[0]
    centers = (values[:, :2].astype(np.float64) + GRIDS) * STRIDES
    sizes = np.exp(values[:, 2:4].astype(np.float64)) * STRIDES
    boxes = np.clip(
        np.concatenate((centers - sizes / 2, centers + sizes / 2), axis=1),
        (0, 0, 0, 0),
        (640, 384, 640, 384),
    )
    scores = values[:, 4:5].astype(np.float64) * values[:, [5 + c for c in CLASSES]]
    keep = (
        (np.max(scores, axis=1) >= POLICY["weak_score_min"])
        & (boxes[:, 0] < boxes[:, 2])
        & (boxes[:, 1] < boxes[:, 3])
    )
    return np.concatenate((boxes[keep], scores[keep]), axis=1)


def combine(base, cropped, weak, *, verify_base=True):
    if len(base) > 100 or len(cropped) > 100:
        raise ValueError("view capacity")
    for detection in tuple(base) + tuple(cropped):
        detection.validate()
        if detection.score < POLICY["published_score_min"]:
            raise ValueError("unqualified detection")
    weak = np.asarray(weak, dtype=np.float64)
    if (
        weak.ndim != 2
        or weak.shape[1:] != (10,)
        or len(weak) > 8400
        or not np.isfinite(weak).all()
    ):
        raise ValueError("weak support shape/finite/capacity")
    if len(weak) and (
        np.any(weak[:, :2] < 0)
        or np.any(weak[:, 2:4] > (640, 384))
        or np.any(weak[:, :2] >= weak[:, 2:4])
        or np.any(weak[:, 4:] < 0)
        or np.any(weak[:, 4:] > 1)
    ):
        raise ValueError("weak support range")
    added = []
    for d in cropped:
        if not len(weak):
            continue
        scores = weak[:, 4 + CLASSES.index(d.class_id)]
        minimum = (
            POLICY["weak_score_min"]
            if d.score >= POLICY["strong_crop_score"]
            else POLICY["weak_crop_semantic_min"]
        )
        if d.class_id in BODY and d.score >= POLICY["strong_crop_score"]:
            scores = np.max(weak[:, [4 + CLASSES.index(c) for c in BODY]], axis=1)
        if np.any(
            (scores >= minimum)
            & (iou(np.array(d.box), weak[:, :4]) >= POLICY["support_iou_min"])
        ):
            added.append(d)
    retained = []
    rejected_crops = set()
    for d in base:
        x1, y1, x2, y2 = d.box
        inside = 161 < x1 and 97 < y1 and x2 < 479 and y2 < 287
        if inside and d.class_id in BODY:
            rivals = [
                (n, p)
                for n, p in enumerate(added)
                if p.class_id in BODY
                and p.class_id != d.class_id
                and float(iou(np.array(d.box), np.array([p.box]))[0])
                > POLICY["body_disagreement_iou_min"]
            ]
            strong = [
                p for _, p in rivals if p.score >= POLICY["body_crop_override_score"]
            ]
            if strong:
                continue
            rejected_crops.update(n for n, _ in rivals)
        if (
            verify_base
            and inside
            and d.class_id in (0, 1, 3)
            and d.score < POLICY["verify_base_below"]
        ):
            if not any(
                p.class_id == d.class_id
                and float(iou(np.array(d.box), np.array([p.box]))[0])
                >= POLICY["support_iou_min"]
                for p in cropped
            ):
                continue
        retained.append(d)
    return merge(
        tuple(retained)
        + tuple(d for n, d in enumerate(added) if n not in rejected_crops),
        vehicle_nms=False,
    )


class QualityCandidateV6:
    def __init__(self, model, candidate, execution="cuda"):
        if candidate not in CANDIDATES:
            raise ValueError("unknown v6 candidate")
        self.candidate = candidate
        self.detector = (
            YoloX(model, execution)
            if candidate == "baseline"
            else LargeYoloX(model, execution)
        )

    def infer(self, frame):
        if self.candidate != "large-context-v6":
            r = self.detector.infer(frame)
            return OfflineResultV6(
                r.identity,
                r.detections,
                r.preprocess_ns,
                r.inference_ns,
                r.postprocess_ns,
                MODELS[self.candidate],
            )
        before = time.monotonic_ns()
        image_health(frame)
        tensor, ratio = preprocess(frame)
        prepared = time.monotonic_ns()
        raw = self.detector.session.run(["output"], {"images": tensor})[0]
        inferred = time.monotonic_ns()
        base = postprocess(raw, ratio)
        weak = weak_proposals(raw)
        processed = time.monotonic_ns()
        image = np.frombuffer(frame.rgb, np.uint8).reshape(384, 640, 3)
        enlarged = cv2.resize(
            image[96:288, 160:480], (640, 384), interpolation=cv2.INTER_LINEAR
        )
        resized = time.monotonic_ns()
        crop = self.detector.infer(replace(frame, rgb=enlarged.tobytes()))
        merging = time.monotonic_ns()
        detections = combine(base, restore_crop(crop.detections), weak)
        result = OfflineResultV6(
            frame.identity,
            detections,
            prepared - before + resized - processed + crop.preprocess_ns,
            inferred - prepared + crop.inference_ns,
            processed - inferred + crop.postprocess_ns + time.monotonic_ns() - merging,
            MODELS[self.candidate],
            INPUT_PROFILE,
        )
        result.validate()
        return result

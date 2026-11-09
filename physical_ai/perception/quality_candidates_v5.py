"""RGB-only multi-view candidates; immutable S/M weights, no live publication."""

from dataclasses import replace
import time
import cv2
import numpy as np

from .contract import MODEL_SHA256
from .quality_candidates import restore_crop
from .quality_candidates_v3 import (
    MediumYoloX,
    MEDIUM_SHA256,
    OfflineResult,
    INPUT_PROFILE,
)
from .yolox import YoloX, image_health, preprocess, postprocess, GRIDS, STRIDES, iou

CANDIDATES = ("baseline", "medium-vru-v5", "medium-consensus-v5")
MODELS = {c: MODEL_SHA256 if c == "baseline" else MEDIUM_SHA256 for c in CANDIDATES}
VRU = (0, 1, 3)
EXCLUSIVE = (1, 2, 3, 5, 7)
POLICY = dict(
    crop_xywh=[160, 96, 320, 192],
    scale=2,
    crop_edge_margin_pixels=2,
    published_score_min=0.35,
    same_class_nms_iou=0.5,
    weak_vru_score_min=0.10,
    weak_support_iou_min=0.30,
    semantic_support_min=0.20,
    strong_vru_score=0.75,
    verify_weak_base_vru_inside_crop=True,
    exclusive_body_classes=list(EXCLUSIVE),
    exclusive_iou_min=0.85,
    person_never_cross_class_suppressed=True,
    max_detections=100,
)


def weak_vru_proposals(raw):
    """Private support only: validated raw tensor, never publish low-score boxes."""
    # This also validates every box before any low-confidence filtering.
    postprocess(raw)
    values = raw[0]
    centers = (values[:, :2].astype(np.float64) + GRIDS) * STRIDES
    sizes = np.exp(values[:, 2:4].astype(np.float64)) * STRIDES
    boxes = np.clip(
        np.concatenate((centers - sizes / 2, centers + sizes / 2), axis=1),
        (0, 0, 0, 0),
        (640, 384, 640, 384),
    )
    support = values[:, 4:5].astype(np.float64) * values[:, [5 + c for c in VRU]]
    keep = (
        (np.max(support, axis=1) >= POLICY["weak_vru_score_min"])
        & (boxes[:, 0] < boxes[:, 2])
        & (boxes[:, 1] < boxes[:, 3])
    )
    return np.concatenate((boxes[keep], support[keep]), axis=1)


def combine(base, cropped, weak, *, consensus):
    """Keep full-image vehicles; add crop VRUs with optional independent support."""
    if len(base) > 100 or len(cropped) > 100:
        raise ValueError("view capacity")
    for detection in tuple(base) + tuple(cropped):
        detection.validate()
        if detection.score < POLICY["published_score_min"]:
            raise ValueError("unqualified published detection")
    weak = np.asarray(weak, dtype=np.float64)
    if (
        weak.ndim != 2
        or weak.shape[1:] != (7,)
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
        raise ValueError("weak support box")

    def supported(d):
        if not len(weak):
            return False
        scores = (
            np.max(weak[:, 4:], axis=1)
            if d.score >= POLICY["strong_vru_score"]
            else weak[:, 4 + VRU.index(d.class_id)]
        )
        minimum = (
            POLICY["weak_vru_score_min"]
            if d.score >= POLICY["strong_vru_score"]
            else POLICY["semantic_support_min"]
        )
        return np.any(
            (scores >= minimum)
            & (iou(np.array(d.box), weak[:, :4]) >= POLICY["weak_support_iou_min"])
        )

    added = [
        d for d in cropped if d.class_id in VRU and (not consensus or supported(d))
    ]
    retained = []
    for d in base:
        x1, y1, x2, y2 = d.box
        verifiable = 161 < x1 and 97 < y1 and x2 < 479 and y2 < 287
        if (
            consensus
            and d.class_id in VRU
            and d.score < POLICY["strong_vru_score"]
            and verifiable
        ):
            if not any(
                p.class_id == d.class_id
                and float(iou(np.array(d.box), np.array([p.box]))[0])
                >= POLICY["weak_support_iou_min"]
                for p in cropped
            ):
                continue
        retained.append(d)
    ordered = sorted(
        enumerate(tuple(retained) + tuple(added)),
        key=lambda item: (-item[1].score, item[0]),
    )
    chosen = []
    for _, detection in ordered:
        suppressed = False
        for prior in chosen:
            same = prior.class_id == detection.class_id
            exclusive = (
                consensus
                and not same
                and prior.class_id in EXCLUSIVE
                and detection.class_id in EXCLUSIVE
            )
            if (same or exclusive) and float(
                iou(np.array(prior.box), np.array([detection.box]))[0]
            ) > (POLICY["same_class_nms_iou"] if same else POLICY["exclusive_iou_min"]):
                suppressed = True
                break
        if not suppressed:
            chosen.append(detection)
            if len(chosen) > POLICY["max_detections"]:
                raise ValueError("combined capacity")
    return tuple(chosen)


class QualityCandidateV5:
    def __init__(self, model, candidate, execution="cuda"):
        if candidate not in CANDIDATES:
            raise ValueError("unknown v5 candidate")
        self.candidate = candidate
        self.detector = (
            YoloX(model, execution)
            if candidate == "baseline"
            else MediumYoloX(model, execution)
        )

    def infer(self, frame):
        if self.candidate == "baseline":
            r = self.detector.infer(frame)
            return OfflineResult(
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
        weak = (
            weak_vru_proposals(raw)
            if self.candidate == "medium-consensus-v5"
            else np.empty((0, 7))
        )
        processed = time.monotonic_ns()
        pixels = np.frombuffer(frame.rgb, np.uint8).reshape(384, 640, 3)
        enlarged = cv2.resize(
            pixels[96:288, 160:480], (640, 384), interpolation=cv2.INTER_LINEAR
        )
        resized = time.monotonic_ns()
        crop = self.detector.infer(replace(frame, rgb=enlarged.tobytes()))
        merging = time.monotonic_ns()
        detections = combine(
            base,
            restore_crop(crop.detections),
            weak,
            consensus=self.candidate == "medium-consensus-v5",
        )
        result = OfflineResult(
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

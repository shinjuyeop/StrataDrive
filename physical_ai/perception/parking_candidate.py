"""RGB-only decoding for the offline D-FINE parking candidate in 640 × 384 coordinates."""

import numpy as np
from .class_calibration_v1 import decode
from .resolution_car_v1 import VECTOR


def nms(boxes, scores, threshold, eligible):
    order = np.flatnonzero(eligible)
    order = order[np.argsort(-scores[order], kind="stable")]
    kept = []
    area = (boxes[:, 2:] - boxes[:, :2]).clip(0).prod(axis=1)
    while order.size:
        i = order[0]
        kept.append(i)
        other = order[1:]
        overlap = (
            (
                np.minimum(boxes[i, 2:], boxes[other, 2:])
                - np.maximum(boxes[i, :2], boxes[other, :2])
            )
            .clip(0)
            .prod(axis=1)
        )
        order = other[overlap <= threshold * (area[i] + area[other] - overlap)]
    return np.asarray(kept, dtype=np.int64)


def bus_evidence(raw):
    original = decode(
        {k: raw["original_" + k] for k in ("labels", "boxes", "scores")}, VECTOR
    )
    labels = raw["labels"].reshape(-1)
    boxes = raw["boxes"].reshape(-1, 4)
    scores = raw["scores"].reshape(-1)
    evidence = []
    for det in original:
        if det.class_id != 5:
            continue
        box = np.asarray(det.box)
        inter = (
            (np.minimum(box[2:], boxes[:, 2:]) - np.maximum(box[:2], boxes[:, :2]))
            .clip(0)
            .prod(axis=1)
        )
        union = (
            (box[2:] - box[:2]).prod()
            + (boxes[:, 2:] - boxes[:, :2]).clip(0).prod(axis=1)
            - inter
        )
        corroboration = float(
            scores[(labels == 5) & (inter >= 0.4 * union)].max(initial=0)
        )
        truck = float(scores[(labels == 7) & (inter >= 0.7 * union)].max(initial=0))
        evidence.append(
            (dict(class_id=5, score=det.score, box=list(det.box)), corroboration, truck)
        )
    return evidence


def select_buses(evidence, policy):
    return [
        d
        for d, support, truck in evidence
        if d["score"] >= policy["confidence"]
        and support >= policy["support"]
        and truck < policy.get("truck_veto", 2.0)
    ]


def detections(raw, spec):
    boxes, logits, delta = (
        raw[k] for k in ("car_boxes", "car_logits", "adjacent_delta")
    )
    if (
        boxes.shape != (300, 4)
        or logits.shape != (300,)
        or delta.shape != (300,)
        or not all(np.isfinite(x).all() for x in (boxes, logits, delta))
    ):
        raise ValueError("invalid car proposals")
    scores = 1 / (1 + np.exp(-np.clip(logits, -80, 80)))
    valid = (boxes[:, 2:] > boxes[:, :2]).all(axis=1)
    idx = nms(boxes, scores, spec["car_nms"], valid & (scores >= spec["anchor"]))
    near = np.zeros(len(scores), dtype=bool)
    if len(idx):
        overlap = (
            (
                np.minimum(boxes[:, None, 2:], boxes[None, idx, 2:])
                - np.maximum(boxes[:, None, :2], boxes[None, idx, :2])
            )
            .clip(0)
            .prod(axis=2)
        )
        overlap[idx, np.arange(len(idx))] = 0
        near = overlap.max(axis=1) >= spec["overlap"] * (
            boxes[:, 2:] - boxes[:, :2]
        ).clip(0).prod(axis=1).clip(1)
    change = near & (scores >= 0.1)
    scores[change] = 1 / (1 + np.exp(-np.clip(logits[change] + delta[change], -80, 80)))
    idx = nms(
        boxes,
        scores,
        spec["car_nms"],
        valid & (scores >= np.where(near, spec["near"], spec["ordinary"])),
    )
    cars = [
        dict(class_id=2, score=float(scores[i]), box=boxes[i].tolist()) for i in idx
    ]
    other = decode({k: raw[k] for k in ("labels", "boxes", "scores")}, VECTOR)
    if spec.get("original_bus"):
        policy = spec.get("bus_policy", {"confidence": 0.5, "support": 0.0})
        if policy.get("source", "original") == "original":
            cars.extend(select_buses(bus_evidence(raw), policy))
            other = [d for d in other if d.class_id != 5]
    return cars + [
        dict(class_id=d.class_id, score=d.score, box=list(d.box))
        for d in other
        if d.class_id != 2
    ]

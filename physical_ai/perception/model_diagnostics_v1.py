"""Descriptive native-output diagnostics; never changes primary detections or GT."""

import numpy as np

from .contract import CLASSES, HEIGHT, WIDTH
from .yolox import iou

FP_BUCKETS = (
    "same_class_duplicate_geometry",
    "other_class_positive_iou_ge_0p5",
    "same_class_positive_iou_0p1_to_0p5",
    "other_class_positive_iou_0p1_to_0p5",
    "no_positive_iou_ge_0p1",
)
FN_BUCKETS = (
    "matching_competition",
    "below_selected_confidence",
    "same_class_localization_overlap",
    "no_same_class_overlap_in_native_top300",
)


def overlaps(box, objects):
    if not objects:
        return np.empty(0, dtype=np.float64)
    return iou(
        np.asarray(box, dtype=np.float64),
        np.asarray([obj["box"] for obj in objects], dtype=np.float64),
    )


def strict_matching(predictions, objects):
    """Return prediction-to-GT identities using the existing primary greedy rule."""
    assigned, used = {}, set()
    counts = {str(c): dict(tp=0, fp=0, fn=0) for c in CLASSES}
    for index in sorted(
        range(len(predictions)), key=lambda n: -predictions[n]["score"]
    ):
        prediction = predictions[index]
        values = overlaps(prediction["box"], objects)
        eligible = [
            (float(values[n]), n)
            for n, obj in enumerate(objects)
            if n not in used and obj["class_id"] == prediction["class_id"]
        ]
        best, gt_index = max(
            eligible, default=(0.0, -1), key=lambda row: (row[0], -row[1])
        )
        key = str(prediction["class_id"])
        if best >= 0.5:
            used.add(gt_index)
            assigned[index] = gt_index
            counts[key]["tp"] += 1
        else:
            assigned[index] = None
            counts[key]["fp"] += 1
    for n, obj in enumerate(objects):
        if n not in used:
            counts[str(obj["class_id"])]["fn"] += 1
    return counts, assigned, used


def native_proposals(raw):
    """All exported top300 rows, including scores below the runtime/screen floor."""
    if set(raw) != {"labels", "boxes", "scores"}:
        raise ValueError("native DETR output names")
    labels, boxes, scores = (raw[k] for k in ("labels", "boxes", "scores"))
    if (
        labels.dtype != np.int64
        or labels.shape != (1, 300)
        or boxes.dtype != np.float32
        or boxes.shape != (1, 300, 4)
        or scores.dtype != np.float32
        or scores.shape != (1, 300)
        or not np.isfinite(boxes).all()
        or not np.isfinite(scores).all()
        or np.any(labels < 0)
        or np.any(labels >= 80)
        or np.any(scores < 0)
        or np.any(scores > 1)
        or np.any(boxes[:, :, 2:] < boxes[:, :, :2])
    ):
        raise ValueError("native DETR raw contract")
    result = []
    for n in range(300):
        box = np.clip(boxes[0, n], [0, 0, 0, 0], [WIDTH, HEIGHT, WIDTH, HEIGHT])
        if box[0] >= box[2] or box[1] >= box[3]:
            continue
        result.append(
            dict(
                native_index=n,
                class_id=int(labels[0, n]),
                score=float(scores[0, n]),
                box=list(map(float, box)),
            )
        )
    return result


def gt_attributes(obj):
    box = obj["box"]
    width, height = box[2] - box[0], box[3] - box[1]
    area = width * height
    return dict(
        box_width=width,
        box_height=height,
        box_area=area,
        box_size="lt32sq"
        if area < 32**2
        else "32sq_to96sq"
        if area < 96**2
        else "ge96sq",
        person_kind="rider13"
        if 13 in obj["semantic_tags"]
        else "other_person"
        if obj["class_id"] == 0
        else "not_person",
    )


def fp_evidence(prediction, objects, excluded, matched):
    values = overlaps(prediction["box"], objects)
    same = [
        n for n, obj in enumerate(objects) if obj["class_id"] == prediction["class_id"]
    ]
    other = [
        n for n, obj in enumerate(objects) if obj["class_id"] != prediction["class_id"]
    ]
    best_same = max((float(values[n]) for n in same), default=0.0)
    best_other = max((float(values[n]) for n in other), default=0.0)
    if best_same >= 0.5:
        if not any(n in matched and values[n] >= 0.5 for n in same):
            raise ValueError("FP has an available same-class primary match")
        bucket = FP_BUCKETS[0]
    elif best_other >= 0.5:
        bucket = FP_BUCKETS[1]
    elif best_same >= 0.1:
        bucket = FP_BUCKETS[2]
    elif best_other >= 0.1:
        bucket = FP_BUCKETS[3]
    else:
        bucket = FP_BUCKETS[4]
    relationships = [
        dict(
            gt_index=n,
            class_id=obj["class_id"],
            instance_id=obj["instance_id"],
            semantic_tags=obj["semantic_tags"],
            iou=float(values[n]),
            primary_matched=n in matched,
        )
        for n, obj in enumerate(objects)
        if values[n] >= 0.1
    ]
    rider_overlap = any(
        13 in obj["semantic_tags"] and values[n] >= 0.1 for n, obj in enumerate(objects)
    )
    same_actor_cross_class = any(
        a["instance_id"] == b["instance_id"] and a["class_id"] != b["class_id"]
        for a in relationships
        for b in relationships
    )
    return dict(
        bucket=bucket,
        prediction=prediction,
        max_same_class_iou=best_same,
        max_other_class_iou=best_other,
        relationships=relationships,
        max_excluded_iou=max(
            map(float, overlaps(prediction["box"], excluded)), default=0.0
        ),
        rider_overlap=rider_overlap,
        same_actor_cross_class_gt_overlap=same_actor_cross_class,
    )


def fn_evidence(obj, proposals, threshold):
    values = overlaps(obj["box"], proposals)
    same = [
        n
        for n, proposal in enumerate(proposals)
        if proposal["class_id"] == obj["class_id"]
    ]
    other = [
        n
        for n, proposal in enumerate(proposals)
        if proposal["class_id"] != obj["class_id"]
    ]
    supported = [n for n in same if values[n] >= 0.5]
    best_iou = max((float(values[n]) for n in same), default=0.0)
    best_support = max(
        supported,
        key=lambda n: (proposals[n]["score"], -proposals[n]["native_index"]),
        default=None,
    )
    support_score = None if best_support is None else proposals[best_support]["score"]
    bucket = (
        FN_BUCKETS[0]
        if support_score is not None and support_score >= threshold
        else FN_BUCKETS[1]
        if support_score is not None
        else FN_BUCKETS[2]
        if best_iou >= 0.1
        else FN_BUCKETS[3]
    )
    best_other = max(
        other,
        key=lambda n: (
            float(values[n]),
            proposals[n]["score"],
            -proposals[n]["native_index"],
        ),
        default=None,
    )
    best_same = max(
        same,
        key=lambda n: (
            float(values[n]),
            proposals[n]["score"],
            -proposals[n]["native_index"],
        ),
        default=None,
    )
    return dict(
        bucket=bucket,
        gt=obj,
        **gt_attributes(obj),
        max_same_class_iou=best_iou,
        max_same_class_support_score=support_score,
        same_class_support_below_0p1=support_score is not None and support_score < 0.1,
        best_same_class=None if best_same is None else proposals[best_same],
        highest_score_supported=None
        if best_support is None
        else proposals[best_support],
        max_other_class_iou=0.0 if best_other is None else float(values[best_other]),
        best_other_class=None if best_other is None else proposals[best_other],
    )


def maximum_matching(objects, proposals, score_floor=0.0):
    """Optimistic native-output recall bound with one proposal per GT at most."""
    adjacency = []
    for obj in objects:
        values = overlaps(obj["box"], proposals)
        adjacency.append(
            [
                n
                for n, p in enumerate(proposals)
                if p["class_id"] == obj["class_id"]
                and p["score"] >= score_floor
                and values[n] >= 0.5
            ]
        )
    owner = {}

    def augment(gt_index, visited):
        for proposal_index in adjacency[gt_index]:
            if proposal_index in visited:
                continue
            visited.add(proposal_index)
            if proposal_index not in owner or augment(owner[proposal_index], visited):
                owner[proposal_index] = gt_index
                return True
        return False

    for gt_index in range(len(objects)):
        augment(gt_index, set())
    matched = set(owner.values())
    return dict(
        matched_gt=sorted(matched),
        assignment={str(n): g for n, g in sorted(owner.items())},
    )

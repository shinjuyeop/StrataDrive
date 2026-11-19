"""GPU-local vehicle conflict checks and two-scale verification of unmatched small cars."""

from functools import lru_cache
from itertools import combinations

import numpy as np
import visible_car as visible
import bus_support as bus

from car_support import prior, recovery, typed
from multiview_detector import overlap
from physical_ai.perception.yolox import GRIDS, STRIDES
from quality_views import box_observations, paired_cars, yolo_raw
import small_car as tiles


def crop_geometry(box, minimum, horizontal, vertical):
    box = np.asarray(box)
    size = box[2:] - box[:2]
    width = min(640, max(minimum, horizontal * size[0], vertical * size[1]))
    extent = np.array([width, width * 0.6])
    origin = np.clip((box[:2] + box[2:] - extent) / 2, 0, [640, 384] - extent)
    rect = np.rint(np.r_[origin, origin + extent] * 4).astype(int)
    bounds = rect / 4
    ratio = np.tile((bounds[2:] - bounds[:2]) / [640, 384], 2)
    return rect, (box - np.tile(bounds[:2], 2)) / ratio


def appearance_veto(detector, box, threshold):
    features = prior.appearance_features(detector.views.rgb, box)
    app = detector.appearance_forest.probability([features])[0]
    if (app + 1) / 2 < threshold:
        return False
    rect, target = crop_geometry(box, 64, 4, 5.5)
    raw = detector.views.forward(rect)
    votes = {c: 0.0 for c in typed.TYPE}
    for prefix in ("original_", ""):
        ov = overlap(target, raw[prefix + "boxes"].reshape(-1, 4))
        labels = raw[prefix + "labels"].ravel()
        scores = raw[prefix + "scores"].ravel()
        keep = (ov >= 0.35) & (scores > 0.05)
        for c in votes:
            votes[c] = max(votes[c], float(scores[keep & (labels == c)].max(initial=0)))
    local = votes[2] / max(0.15, votes[2] + max(votes[5], votes[7]))
    return (app + local) / 2 >= threshold


def match_features(ov, conf):
    return [conf[ov >= t].max(initial=0) for t in (0.3, 0.5, 0.7)] + [
        (ov * conf).max(initial=0)
    ]


def type_features(detector, box):
    rect, target = crop_geometry(box, 55, 3.5, 5)
    raw = detector.views.forward(rect)
    values = []
    for prefix in ("original_", ""):
        ov = overlap(target, raw[prefix + "boxes"].reshape(-1, 4))
        labels = raw[prefix + "labels"].ravel()
        scores = raw[prefix + "scores"].ravel()
        for c in typed.TYPE:
            mask = labels == c
            values.extend(match_features(ov[mask], scores[mask]))
    raw = yolo_raw(detector.views, detector.yolo, rect)[0]
    centers = (raw[:, :2] + GRIDS) * STRIDES
    sizes = np.exp(raw[:, 2:4].astype(float)) * STRIDES
    ov = overlap(target, np.column_stack((centers - sizes / 2, centers + sizes / 2)))
    for c in typed.TYPE:
        values.extend(match_features(ov, raw[:, 4] * raw[:, 5 + c]))
    return values


def resolve_conflicts(detector, boxes):
    cars = [d for d in boxes if d["class_id"] == 2 and d["score"] >= 0.75]
    appearance = {}
    types = {}
    kept = []
    for d in boxes:
        if d["class_id"] == 7 and cars:
            covered, _, i = max(
                (prior.containment(d["box"], car["box"]), car["score"], i)
                for i, car in enumerate(cars)
            )
            if covered >= 0.65:
                if i not in appearance:
                    appearance[i] = appearance_veto(
                        detector, cars[i]["box"], typed.FIX["threshold"]
                    )
                if appearance[i]:
                    continue
            if covered >= 0.5:
                if i not in types:
                    types[i] = detector.vehicle_classifier.probability(
                        np.asarray([type_features(detector, cars[i]["box"])])
                    )[0]
                if types[i] >= recovery.FIX["threshold"]:
                    continue
        kept.append(d)
    return kept


def grid_rect(view):
    x, y, w, h = view
    return tuple(round(v) for v in (x * 2560, y * 1536, (x + w) * 2560, (y + h) * 1536))


CAR_WINDOWS = tuple(map(grid_rect, tiles.VIEWS))


def intersection_area(a, b):
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(
        0, min(a[3], b[3]) - max(a[1], b[1])
    )


# Candidate boxes use the 640x384 coordinate system.
WINDOW_BOXES = tuple(tuple(v / 4 for v in rect) for rect in CAR_WINDOWS)


@lru_cache(maxsize=1024)
def split_windows(windows):
    """Any pair of agreeing views touches the first group (a vertex cover)."""
    for size in range(len(windows), -1, -1):
        for independent in combinations(windows, size):
            if all(
                intersection_area(WINDOW_BOXES[i], WINDOW_BOXES[j]) == 0
                for i, j in combinations(independent, 2)
            ):
                return tuple(i for i in windows if i not in independent), independent


def could_supply_box(box, parent):
    # At IoU q a matching axis-aligned box can extend at most (1/q - 1)
    # times the original dimension beyond either edge. Its area is at most A/q.
    q = 0.55
    if prior.area(box) / q * bus.MASK["area_fraction"] < 25:
        return False
    w, h = box[2] - box[0], box[3] - box[1]
    dx, dy = (1 / q - 1) * w, (1 / q - 1) * h
    envelope = (box[0] - dx, box[1] - dy, box[2] + dx, box[3] + dy)
    for d in parent:
        if d["class_id"] not in (2, 3, 5, 7):
            continue
        p = d["box"]
        # Jaccard distance obeys the triangle inequality. The other member
        # is necessarily a duplicate at the registered IoU threshold.
        if tiles.iou(box, p) + q - 1 > 0.32 + 1e-10:
            return False
        if (
            p[0] <= envelope[0]
            and p[1] <= envelope[1]
            and p[2] >= envelope[2]
            and p[3] >= envelope[3]
        ):
            return False
    return True


def window_overlap(box, index, minimum):
    # An in-window box at IoU q must cover at least q of the original box.
    return intersection_area(box, WINDOW_BOXES[index]) + 1e-10 >= minimum * prior.area(
        box
    )


def confirm_cars(views, parent):
    seeds = [
        box
        for _, _, box in views.cars
        if not any(tiles.duplicate(box, d) for d in parent)
    ]
    windows = tuple(
        i
        for i, (x, y, r, b) in enumerate(WINDOW_BOXES)
        if any(
            x <= box[2] and box[0] <= r and y <= box[3] and box[1] <= b for box in seeds
        )
    )
    first, remaining = split_windows(windows)

    def observe(indices):
        cars = []
        for i in indices:
            rect = CAR_WINDOWS[i]
            _, found = box_observations(views.forward(rect), rect, False, i, False)
            cars.extend(found)
        return cars

    cars = observe(first)
    cutoff = visible.FIX["cutoff"]
    strong = [(i, b) for i, s, b in cars if s >= cutoff]
    if not any(could_supply_box(box, parent) for _, box in strong):
        return []
    # The remaining windows are mutually disjoint. Every strong pair must
    # include an already seen box. First finish finding all such pairs.
    paired_windows = [
        j for j in remaining if any(window_overlap(box, j, 0.55) for _, box in strong)
    ]
    cars.extend(observe(paired_windows))
    high = [
        d["box"]
        for d in paired_cars([c for c in cars if c[1] >= cutoff])
        if tiles.short_side(d["box"]) >= 5
        and not any(tiles.duplicate(d["box"], p) for p in parent)
    ]
    if not high:
        return []
    # The median short side also uses lower-score pairs. An unseen box can
    # either enter a winner's median or provide the second view for a known
    # box in that median. Retain every window that can do either.
    near = [box for _, _, box in cars if any(tiles.iou(box, h) >= 0.5 for h in high)]
    median_windows = [
        j
        for j in remaining
        if j not in paired_windows
        and (
            any(window_overlap(h, j, 0.5) for h in high)
            or any(window_overlap(box, j, 0.55) for box in near)
        )
    ]
    cars.extend(observe(median_windows))
    cars.sort(key=lambda item: item[0])
    return paired_cars(cars)

"""Evaluate native RGB crops once and share the resulting dual-head observations."""

import numpy as np

import bus_recall_fit as primary
import multiview_observations as obs
import small_car as tiles
from quality_features import PackedClassifier, proposals as predict_proposals
from quality_latency_cuda import Engine


def base_from_raw(image, model, raw, config, forward):
    base = primary.detections(raw, model.spec)
    people = [d for d in base if d["class_id"] == 0]
    zoom = people
    anchor = max(
        (d for d in base if d["class_id"] in (1, 3)),
        key=lambda d: d["score"],
        default=None,
    )
    if anchor:
        bounds = primary.crop_bounds(image.size, anchor["box"])
        local = primary.detections(forward(bounds), model.spec)
        zoom = primary.merge(people, local, bounds, image.size)
    buses = [d for d in base if d["class_id"] == 5]
    return (
        [d for d in base if d["class_id"] not in (0, 5)]
        + primary.recover(buses, primary.proposals(raw), obs.BUS)
        + primary.combine(people, zoom, config)
    )


def box_observations(raw, rect, flip, view, collect_other=True):
    x, y, r, b = rect
    scale = np.array([(r - x) / 2560, (b - y) / 1536] * 2)
    offset = np.array([x / 4, y / 4] * 2)
    cars = []
    others = []
    for head, prefix in enumerate(("", "original_")):
        labels = raw[prefix + "labels"].ravel()
        scores = raw[prefix + "scores"].ravel()
        boxes = raw[prefix + "boxes"].reshape(-1, 4)
        keep = (labels == 2) & (scores >= 0.25)
        if collect_other:
            keep |= np.isin(labels, obs.CLASSES) & (scores >= 0.09)
        for j in np.flatnonzero(keep):
            cls = int(labels[j])
            s = float(scores[j])
            box = boxes[j].astype(float)
            if flip:
                box[[0, 2]] = 640 - box[[2, 0]]
            if cls == 2:
                if min(box[0], box[1], 640 - box[2], 384 - box[3]) < 2:
                    continue
                box = box * scale + offset
                w, h = box[2:] - box[:2]
                if min(w, h) >= 4 and max(w, h) <= 40 and w * h >= 42:
                    cars.append((view, s, box.tolist()))
            else:
                box = box.clip([0, 0, 0, 0], [640, 384, 640, 384])
                if box[2] <= box[0] or box[3] <= box[1]:
                    continue
                if (
                    (x > 0 and box[0] < 2)
                    or (r < 2560 and box[2] > 638)
                    or (y > 0 and box[1] < 2)
                    or (b < 1536 and box[3] > 382)
                ):
                    continue
                others.append(
                    [
                        view,
                        head,
                        cls,
                        round(s, 6),
                        *np.round(box * scale + offset, 3).tolist(),
                    ]
                )
    return others, cars


def paired_cars(cars):
    out = []
    for view, s, b in cars:
        other = max(
            (sc for k, sc, q in cars if k != view and tiles.iou(b, q) >= 0.55),
            default=0.0,
        )
        if other:
            out.append(dict(class_id=2, score=min(s, other), box=b))
    return sorted(out, key=lambda d: -d["score"])


class Views:
    def __init__(self, model, crops, mode):
        self.model = model
        self.crops = crops
        self.mode = mode
        self.config = primary.read(primary.PERSON)["config"]
        self.count = 0
        self.classifiers = {
            c: PackedClassifier(m) for c, m in model.bundle["models"].items()
        }

    def forward(self, rect, flip=False):
        self.count += 1
        ptr = self.crops.crop(rect, flip)
        session = self.model.session
        names = self.model.spec["outputs"]
        if isinstance(session, Engine):
            out = session.device(names, ptr)
        else:
            bind = session.io_binding()
            bind.bind_input("images", "cuda", 0, np.float32, (1, 3, 960, 960), ptr)
            for name in names:
                bind.bind_output(name, "cpu")
            session.run_with_iobinding(bind)
            out = bind.copy_outputs_to_cpu()
        return dict(zip(names, out, strict=True))

    def prepare(self, image):
        self.rgb = self.crops.frame(image)
        self.count = 0
        rois = obs.VIEWS
        if self.mode == "compact":
            indices = (0, 3, 5, 6, 7, 8, 9)
        elif self.mode == "focus":
            indices = [0, 2, 3, 4]
        elif self.mode == "lite":
            indices = (0, 2, 3, 4)
        else:
            indices = range(len(rois))
        others = []
        self.cars = []
        for index in indices:
            x, y, r, b, flip = rois[index]
            rect = tuple(round(v) for v in (x * 2560, y * 1536, r * 2560, b * 1536))
            raw = self.forward(rect, flip)
            if index == 0:
                base = base_from_raw(image, self.model, raw, self.config, self.forward)
            local, cars = box_observations(raw, rect, flip, index)
            others.extend(local)
            self.cars.extend(cars)
            if self.mode == "focus" and index == 4:
                # Keep a zoom ahead even in apparently empty images. Schedule other
                # narrow windows from current-frame low-confidence vehicle/rider evidence.
                centers = [(roi[0] + roi[2]) * 320 for roi in rois[5:]]
                xs = [(v[4] + v[6]) / 2 for v in others if v[3] >= 0.09]
                xs.extend((box[0] + box[2]) / 2 for _, _, box in self.cars)
                chosen = {7}
                for cx in xs:
                    chosen.add(5 + int(np.argmin(np.abs(np.asarray(centers) - cx))))
                indices.extend(sorted(chosen))
        new = predict_proposals(
            self.model.bundle, self.rgb, dict(base=base, obs=others), self.classifiers
        )
        return base, new, others

    def small_cars(self, parent):
        if self.mode in ("native", "focus", "guided"):
            cars = []
            seeds = (
                [
                    box
                    for _, _, box in self.cars
                    if not any(tiles.duplicate(box, d) for d in parent)
                ]
                if self.mode == "guided" or self.mode == "focus"
                else []
            )
            for i, (x, y, w, h) in enumerate(tiles.VIEWS):
                rect = tuple(
                    round(v)
                    for v in (x * 2560, y * 1536, (x + w) * 2560, (y + h) * 1536)
                )
                if self.mode != "native":
                    left, top, right, bottom = rect
                    if not any(
                        left / 4 <= box[2]
                        and box[0] <= right / 4
                        and top / 4 <= box[3]
                        and box[1] <= bottom / 4
                        for box in seeds
                    ):
                        continue
                _, local = box_observations(self.forward(rect), rect, False, i, False)
                cars.extend(local)
        else:
            cars = self.cars
        return paired_cars(cars)


def yolo_raw(views, yolo, rect):
    ptr = views.crops.crop(rect, yolo=True)
    binding = yolo.session.io_binding()
    binding.bind_input("images", "cuda", 0, np.float32, (1, 3, 640, 640), ptr)
    binding.bind_output("output", "cpu")
    yolo.session.run_with_iobinding(binding)
    return binding.copy_outputs_to_cpu()[0]


def recognition(detector, box, cls, sufficient):
    """Only compute the confidence at IoU .5 used by the supplemental rules."""
    from multiview_detector import overlap
    from physical_ai.perception.yolox import GRIDS, STRIDES

    b = np.asarray(box)
    center = (b[:2] + b[2:]) / 2
    w = min(640, max(55, 3.5 * (b[2] - b[0]), 5 * (b[3] - b[1])))
    h = w * 0.6
    x, y = np.clip(center - [w / 2, h / 2], [0, 0], [640 - w, 384 - h])
    rect = np.rint(np.array([x, y, x + w, y + h]) * 4).astype(int)
    bounds = rect / 4
    target = (b - np.tile(bounds[:2], 2)) / np.tile(
        (bounds[2:] - bounds[:2]) / [640, 384], 2
    )
    raw = detector.views.forward(rect)
    conf = 0.0
    for prefix in ("", "original_"):
        boxes = raw[prefix + "boxes"].reshape(-1, 4)
        match = (raw[prefix + "labels"].ravel() == cls) & (
            overlap(target, boxes) >= 0.5
        )
        conf = max(conf, float(raw[prefix + "scores"].ravel()[match].max(initial=0)))
    if conf >= sufficient:
        return conf
    anchors = yolo_raw(detector.views, detector.yolo, rect)[0]
    centers = (anchors[:, :2] + GRIDS) * STRIDES
    sizes = np.exp(anchors[:, 2:4].astype(float)) * STRIDES
    boxes = np.column_stack((centers - sizes / 2, centers + sizes / 2))
    scores = anchors[:, 4] * anchors[:, 5 + cls]
    return max(conf, float(scores[overlap(target, boxes) >= 0.5].max(initial=0)))


def vehicle_candidates(image, detector, parent):
    """Run full-frame YOLOX once, and crop only candidates the frozen rules could add."""
    import bus_support as bus
    from car_support import explained

    raw = yolo_raw(detector.views, detector.yolo, (0, 0, 2560, 1536))
    ratio = 1.0
    cars = []
    buses = []
    car_policy = tiles.PARENT["policy"]
    for obj in bus.postprocess(raw, ratio):
        box = list(obj.box)
        candidate = dict(class_id=obj.class_id, score=obj.score, box=box)
        if obj.class_id == 2 and obj.score >= car_policy["full"]:
            # Maximal possible crop confidence leaves only unconditional overlap vetoes.
            if explained(dict(candidate, crop_car=1.0), parent):
                continue
            cars.append(
                dict(
                    candidate,
                    crop_car=recognition(
                        detector, box, 2, max(0.85, car_policy["crop"])
                    ),
                )
            )
        elif obj.class_id == 5 and obj.score >= detector.bus_policy["full"]:
            best = dict(candidate, appearance=1.0, crop_bus=1.0)
            if len(bus.add(parent, [best], detector.bus_policy)) == len(parent):
                continue
            app = bus.typed.probability(
                bus.features(detector.views.rgb, box), detector.bus_model
            )
            if app < detector.bus_policy["appearance"]:
                continue
            buses.append(
                dict(
                    candidate,
                    appearance=app,
                    crop_bus=recognition(detector, box, 5, detector.bus_policy["crop"]),
                )
            )
    return cars, buses


def expand(views, base, new, observations):
    from cycle_transfer import fused_metrics, regions, suggestions

    parent = fused_metrics(base, new)
    verified = new.get("1", [])
    local = []
    for bounds in regions(verified, parent):
        rect = np.rint(np.asarray(bounds) * 4).astype(int)
        out = views.forward(rect)
        scale = np.tile((rect[2:] - rect[:2]) / [2560, 1536], 2)
        offset = np.tile(rect[:2] / 4, 2)
        for prefix in ("", "original_"):
            labels = out[prefix + "labels"].ravel()
            scores = out[prefix + "scores"].ravel()
            boxes = out[prefix + "boxes"].reshape(-1, 4)
            for i in np.flatnonzero(np.isin(labels, (0, 1, 3)) & (scores >= 0.06)):
                box = boxes[i].clip([0, 0, 0, 0], [640, 384, 640, 384])
                if (
                    box[2] - box[0] < 2
                    or box[3] - box[1] < 2
                    or min(box[:2]) < 2
                    or box[2] > 638
                    or box[3] > 382
                ):
                    continue
                local.append(
                    dict(
                        class_id=int(labels[i]),
                        score=float(scores[i]),
                        box=(box * scale + offset).tolist(),
                    )
                )
    return parent, suggestions(verified, parent, observations, local)

"""Single-frame RGB inference and paired latency/quality replay for the frozen six-class candidate."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image

import bus_support as bus
import small_car as tiles
import visible_car as visible
from car_support import typed, recovery, prior
import car_support as support
from fresh_quality_2k_review import read
from multiview_detector import score_run
from physical_ai.perception.camera_resolution_v1 import unpack
from person_pair_candidate import dump


class Detector:
    def __init__(self, crops=None, mode="reference", engine=None):
        self.model, self.app, self.yolo = typed.sessions()
        self.direct = mode == "targeted"
        self.views = None
        if engine is not None:
            self.model.session = engine
        if crops is not None:
            from quality_views import Views

            self.views = Views(self.model, crops, mode)
        self.types = typed.classifier()
        if self.direct:
            from quality_features import PackedClassifier, PackedForest

            self.appearance_forest = PackedForest(self.app)
            self.vehicle_classifier = PackedClassifier(self.types)
            # Pay the float64 scorer's first-use cost during model initialization.
            self.vehicle_classifier.probability(
                np.zeros((1, self.types[0].n_features_in_))
            )
        self.bus_model = bus.classifier()
        self.bus_policy = read(bus.EVIDENCE / "selection.json")["policy"]

    def decode(self, bgra):
        if not self.direct:
            return Image.frombytes("RGB", (2560, 1536), bgra, "raw", "BGRX")
        import cv2

        pixels = np.frombuffer(bgra, np.uint8).reshape(1536, 2560, 4)
        return cv2.cvtColor(pixels, cv2.COLOR_BGRA2RGB, dst=self.views.rgb_buffer)

    def predict(self, image):
        start = time.perf_counter()
        checkpoints = {}
        last = start

        def stage(name):
            nonlocal last
            now = time.perf_counter()
            checkpoints[name] = (now - last) * 1000
            last = now

        base, new, obs = (
            self.views.prepare(image)
            if self.views
            else tiles.cycle.predict_raw(self.model, image)
        )
        stage("full_and_multiview")
        if self.views:
            from quality_views import expand

            fixed, proposals = expand(self.views, base, new, obs)
        else:
            fixed, proposals = tiles.cycle.expand(self.model, image, base, new, obs)
        ds = prior.restored_cycle(fixed, {"1": proposals})
        stage("rider_crops")
        if self.direct:
            from quality_vehicle_windows import resolve_conflicts

            ds = resolve_conflicts(self, ds)
        else:
            ds = prior.filter_detections(
                ds,
                prior.evidence(image, ds, self.model, self.app),
                typed.FIX["threshold"],
            )
            ds = prior.filter_detections(
                ds,
                typed.competition(image, ds, self.model, self.yolo, self.types),
                recovery.FIX["threshold"],
            )
        stage("vehicle_conflicts")
        if self.views:
            from quality_views import vehicle_candidates

            if support.EARLIER["threshold"] <= 1:
                raise ValueError("expected registered inactive legacy recovery")
            props, buses = vehicle_candidates(image, self, ds)
            parent = support.add(ds, props, tiles.PARENT["policy"])
        else:
            props = recovery.proposals(image, ds, self.model, self.yolo, self.types)
            parent = support.add(
                recovery.add(ds, props, support.EARLIER["threshold"]),
                props,
                tiles.PARENT["policy"],
            )
        stage("car_recovery")
        added = tiles.add(
            parent,
            self.views.small_cars(parent)
            if self.views
            else tiles.proposals(image, self.model),
            visible.FIX["cutoff"],
        )
        ds = visible.select_boxes(parent, added, bus.MASK)
        stage("small_car_crops")
        ds = bus.add(
            ds,
            buses
            if self.views
            else bus.proposals(image, self.model, self.yolo, self.bus_model),
            self.bus_policy,
        )
        stage("bus_recovery")
        return ds, checkpoints


def replay(detector, run, reference, output, limit=None):
    frames = read(run / "images.json")["frames"]
    if reference:
        with gzip.open(reference, "rt") as stream:
            refs = json.load(stream)
        if len(refs) != len(frames):
            raise ValueError("reference denominator")
    indices = (
        range(len(frames))
        if limit is None
        else np.linspace(0, len(frames) - 1, limit, dtype=int)
    )
    if limit is not None and not 0 < limit <= len(frames):
        raise ValueError("sample count must be within recorded frame count")
    rows = []
    for i in indices:
        f = frames[i]
        bgra = unpack(run / "dataset", f["rgb_raw"], 2560, 1536)
        raw_start = time.perf_counter()
        im = detector.decode(bgra)
        start = time.perf_counter()
        ds, times = detector.predict(im)
        stop = time.perf_counter()
        ms = (stop - start) * 1000
        raw_ms = (stop - raw_start) * 1000
        # Hashing is audit work and never feeds the detector or the timing window.
        key = hashlib.sha256(im.tobytes()).hexdigest()
        if key != f["rgb_sha256"] or (reference and key != refs[i]["rgb"]):
            raise ValueError("frame identity")
        rows.append(
            dict(
                rgb=key,
                base=ds,
                new={},
                elapsed_ms=ms,
                raw_to_boxes_ms=raw_ms,
                dfine_crop_calls=detector.views.count if detector.views else None,
                stages_ms=times,
                reference_equal=ds == refs[i]["detections"] if reference else None,
            )
        )
    result = dict(
        frames=len(rows),
        p50_ms=float(np.median([r["elapsed_ms"] for r in rows])),
        p95_ms=float(np.percentile([r["elapsed_ms"] for r in rows], 95)),
        within_100ms=sum(r["elapsed_ms"] <= 100 for r in rows),
        stage_mean_ms={
            k: float(np.mean([r["stages_ms"][k] for r in rows]))
            for k in rows[0]["stages_ms"]
        },
        rows=rows,
    )
    raw_ms = np.asarray([r["raw_to_boxes_ms"] for r in rows])
    result.update(
        raw_p50_ms=float(np.median(raw_ms)),
        raw_p95_ms=float(np.percentile(raw_ms, 95)),
        raw_within_100ms=int(np.sum(raw_ms <= 100)),
    )
    if limit is None:
        result["quality"] = score_run(run, rows, tiles.cycle.OFF)[0]
    dump(output, result)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--reference", type=Path)
    p.add_argument("--limit", type=int)
    p.add_argument(
        "--mode",
        choices=(
            "reference",
            "native",
            "shared",
            "compact",
            "lite",
            "focus",
            "guided",
            "targeted",
        ),
        default="reference",
    )
    p.add_argument("--library", type=Path)
    p.add_argument("--engine", type=Path)
    a = p.parse_args()
    from contextlib import ExitStack

    with ExitStack() as stack:
        crops = engine = None
        if a.mode != "reference":
            if not a.library:
                p.error("an optimized mode requires --library")
            from quality_latency_cuda import CropInput, Engine

            crops = stack.enter_context(CropInput(a.library))
            if a.engine:
                engine = stack.enter_context(Engine(a.engine))
        replay(Detector(crops, a.mode, engine), a.run, a.reference, a.output, a.limit)

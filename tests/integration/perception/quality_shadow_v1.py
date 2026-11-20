"""The registered six-class RTX 3090 detector, used only by the paired renderer."""

from contextlib import ExitStack, contextmanager
import hashlib
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[3]
REFERENCE = ROOT / "docs/test-plan/evidence/m10_quality_latency_v2/comparison.json"
ENGINE = ROOT / "build/m10-quality-latency-v1/dfine-fp16.plan"
LIBRARY = ENGINE.with_name("quality_crop_v2.so")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


VIEW_REGISTRATION = ROOT / "docs/test-plan/evidence/m10_quality_views_v3/verifier.json"


def fitted_verifier(indices):
    registration = json.loads(VIEW_REGISTRATION.read_text())
    if list(indices or ()) != registration["indices"]:
        raise ValueError("fitted verifier requires its registered view schedule")
    path = ROOT / registration["path"]
    if path.name != "verifier.joblib" or digest(path) != registration["sha256"]:
        raise ValueError("fitted view verifier hash")
    return path


def binding(indices=None, fitted=False, reuse_outputs=False):
    import sys

    sys.path.insert(0, str(ROOT / "tools"))
    import m10_bus_support_quality as current

    reference = json.loads(REFERENCE.read_text())["runs"]["run1"]["binding"].copy()
    del reference["startup_ms"]
    for name, expected in reference["source"].items():
        folder = (
            ROOT / "tools"
            if name == "m10_quality_latency.py"
            else Path(__file__).parent
        )
        if digest(folder / name) != expected:
            raise ValueError(f"changed quality candidate source: {name}")
    if (
        current.nomination() != json.loads(current.MARK.read_text())
        or digest(current.MARK) != reference["reference"]
        or digest(ENGINE) != reference["engine_sha256"]
        or digest(LIBRARY) != reference["library_sha256"]
    ):
        raise ValueError("quality candidate identity")
    if indices is not None:
        if (
            not indices
            or indices[0] != 0
            or list(indices) != sorted(set(indices))
            or any(type(i) is not int or not 0 <= i < 10 for i in indices)
        ):
            raise ValueError("expected unique ordered view indices starting at zero")
        reference.update(
            view_indices=list(indices),
            schedule_sha256=digest(
                Path(__file__).with_name("quality_view_schedule.py")
            ),
        )
    if fitted:
        path = fitted_verifier(indices)
        reference.update(
            view_verifier_sha256=digest(path),
            view_registration_sha256=digest(VIEW_REGISTRATION),
        )
    if reuse_outputs:
        if indices is None:
            raise ValueError("crop reuse requires a declared view schedule")
        reference["crop_reuse_sha256"] = digest(
            Path(__file__).with_name("quality_cached_views.py")
        )
    return reference


@contextmanager
def detector(indices=None, fitted=False, reuse_outputs=False):
    import cv2
    import tensorrt
    from quality_latency import Detector
    from quality_latency_cuda import CropInput, Engine

    spec = binding(indices, fitted, reuse_outputs)
    if tensorrt.__version__ != spec["tensorrt"]:
        raise ValueError("TensorRT version changed")
    cv2.setNumThreads(1)
    with ExitStack() as stack:
        crops = stack.enter_context(CropInput(LIBRARY))
        engine = stack.enter_context(Engine(ENGINE))
        model = Detector(crops, "targeted", engine)
        if indices is not None:
            from quality_view_schedule import ScheduledViews

            if fitted:
                from multiview_detector import load_verifier

                model.model.bundle = load_verifier(fitted_verifier(indices).parent)
            if reuse_outputs:
                from quality_cached_views import CachedFrameViews

                model.views = CachedFrameViews(model, indices)
            else:
                model.views = ScheduledViews(model, indices)
        # Model setup can configure OpenCV. Apply the worker's explicit CPU setting.
        cv2.setNumThreads(1)
        yield model, spec


def predict(model, bgra):
    start = time.monotonic_ns()
    image = model.decode(bgra)
    decoded = time.monotonic_ns()
    boxes, stages = model.predict(image)
    return dict(detections=boxes, decode_ns=decoded - start, stages_ms=stages)


def replay_boxes(folder, renderer, images):
    """Check every completed live result against a fresh inference on the retained BGRA."""
    from endurance_recording_v1 import RawReader

    reader = RawReader(folder)
    try:
        with detector(
            renderer["quality_binding"].get("view_indices"),
            "view_verifier_sha256" in renderer["quality_binding"],
            "crop_reuse_sha256" in renderer["quality_binding"],
        ) as (model, spec):
            if renderer.get("quality_binding") != spec:
                raise ValueError("renderer used another quality candidate")
            for row in renderer["inference"]:
                bgra = reader.read(images[row["renderer_frame"]])
                if predict(model, bgra)["detections"] != row["detections"]:
                    raise ValueError(
                        f"live box replay differs at frame {row['renderer_frame']}"
                    )
    finally:
        reader.close()
